from __future__ import annotations

import asyncio
import ipaddress
import platform
import re
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from time import monotonic

import requests

import settings as setting

from api.services.logging import logger
from database.mongodb import mongodb


ROBOT_HEADERS = {
    "Content-Type": "application/json",
    "Opentrons-Version": "3",
}
robot_executor = ThreadPoolExecutor(max_workers=32)
LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
MAX_SCAN_HOSTS = 4096
SCAN_CACHE_VERSION = 1

_scan_scheduler_task: asyncio.Task | None = None
_scan_tasks: dict[str, asyncio.Task] = {}
_scan_execution_lock: asyncio.Lock | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def shutdown_robot_service() -> None:
    stop_robot_scan_scheduler()
    robot_executor.shutdown(wait=False, cancel_futures=True)


def _get_scan_execution_lock() -> asyncio.Lock:
    global _scan_execution_lock
    if _scan_execution_lock is None:
        _scan_execution_lock = asyncio.Lock()
    return _scan_execution_lock


def _normalize_scan_network(network: str | None) -> str:
    return (network or "").strip()


def build_robot_scan_cache_key(port: int, network: str | None = None) -> str:
    normalized_network = _normalize_scan_network(network) or "configured"
    return f"{int(port)}:{normalized_network}"


def get_robot_scan_cache_collection():
    if mongodb.client is None and not mongodb.connect():
        raise RuntimeError("MongoDB connection is not available")
    collection = mongodb.get_database(setting.MESSAGE_COLLECTION)[setting.ROBOT_SCAN_CACHE_COLLECTION]
    collection.create_index("cache_key", unique=True)
    collection.create_index("updated_at")
    return collection


def _empty_scan_result(port: int, network: str | None = None) -> dict:
    return {
        "total": 0,
        "online_count": 0,
        "offline_count": 0,
        "abnormal_count": 0,
        "scan_network": _normalize_scan_network(network),
        "server_ip": str(getattr(setting, "DATA_HANDLER_HOST", "") or ""),
        "gateway": "",
        "scan_gateways": [],
        "online_robots": [],
        "offline_robots": [],
        "abnormal_robots": [],
        "cached_at": None,
        "scan_started_at": None,
        "scan_duration_ms": None,
        "refreshing": False,
        "last_error": None,
        "port": int(port),
    }


def load_robot_scan_cache(port: int = setting.ROBOT_HEALTH_PORT, network: str | None = None) -> dict:
    cache_key = build_robot_scan_cache_key(port, network)
    collection = get_robot_scan_cache_collection()
    doc = collection.find_one({"cache_key": cache_key}, {"_id": 0})
    if not doc:
        return _empty_scan_result(port, network)

    result = dict(doc.get("result") or _empty_scan_result(port, network))
    result["cached_at"] = doc.get("updated_at")
    result["scan_started_at"] = doc.get("scan_started_at")
    result["scan_duration_ms"] = doc.get("scan_duration_ms")
    result["last_error"] = doc.get("last_error")
    result["refreshing"] = False
    return result


def save_robot_scan_cache(
    result: dict,
    *,
    port: int,
    network: str | None,
    scan_started_at: str,
    scan_duration_ms: int,
) -> dict:
    cache_key = build_robot_scan_cache_key(port, network)
    cached_at = _utc_now()
    stored_result = dict(result)
    stored_result.update(
        {
            "cached_at": cached_at,
            "scan_started_at": scan_started_at,
            "scan_duration_ms": scan_duration_ms,
            "refreshing": False,
            "last_error": None,
        }
    )
    collection = get_robot_scan_cache_collection()
    collection.update_one(
        {"cache_key": cache_key},
        {
            "$set": {
                "cache_key": cache_key,
                "cache_version": SCAN_CACHE_VERSION,
                "port": int(port),
                "network": _normalize_scan_network(network),
                "result": stored_result,
                "scan_started_at": scan_started_at,
                "scan_duration_ms": scan_duration_ms,
                "updated_at": cached_at,
                "last_error": None,
            },
            "$setOnInsert": {"created_at": cached_at},
        },
        upsert=True,
    )
    return stored_result


def record_robot_scan_failure(
    error: str,
    *,
    port: int,
    network: str | None,
    scan_started_at: str,
    scan_duration_ms: int,
) -> None:
    cache_key = build_robot_scan_cache_key(port, network)
    failed_at = _utc_now()
    collection = get_robot_scan_cache_collection()
    collection.update_one(
        {"cache_key": cache_key},
        {
            "$set": {
                "cache_key": cache_key,
                "cache_version": SCAN_CACHE_VERSION,
                "port": int(port),
                "network": _normalize_scan_network(network),
                "scan_started_at": scan_started_at,
                "scan_duration_ms": scan_duration_ms,
                "last_error": error,
                "last_failed_at": failed_at,
            },
            "$setOnInsert": {
                "created_at": failed_at,
                "updated_at": None,
                "result": _empty_scan_result(port, network),
            },
        },
        upsert=True,
    )


def is_robot_scan_refreshing(port: int = setting.ROBOT_HEALTH_PORT, network: str | None = None) -> bool:
    task = _scan_tasks.get(build_robot_scan_cache_key(port, network))
    return task is not None and not task.done()


async def refresh_robot_scan_cache(
    port: int = setting.ROBOT_HEALTH_PORT,
    network: str | None = None,
) -> dict | None:
    scan_started_at = _utc_now()
    started = monotonic()
    async with _get_scan_execution_lock():
        try:
            result = await scan_robots(port=port, network=network)
            duration_ms = round((monotonic() - started) * 1000)
            cached_result = await asyncio.to_thread(
                save_robot_scan_cache,
                result,
                port=port,
                network=network,
                scan_started_at=scan_started_at,
                scan_duration_ms=duration_ms,
            )
            logger.info(
                "Robot scan cache refreshed: key=%s online=%s duration_ms=%s",
                build_robot_scan_cache_key(port, network),
                cached_result.get("online_count", 0),
                duration_ms,
            )
            return cached_result
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            duration_ms = round((monotonic() - started) * 1000)
            error = str(exc)
            logger.error("Robot scan cache refresh failed: %s", error, exc_info=True)
            try:
                await asyncio.to_thread(
                    record_robot_scan_failure,
                    error,
                    port=port,
                    network=network,
                    scan_started_at=scan_started_at,
                    scan_duration_ms=duration_ms,
                )
            except Exception:
                logger.error("Failed to persist robot scan error", exc_info=True)
            return None


def _handle_scan_task_done(cache_key: str, task: asyncio.Task) -> None:
    if _scan_tasks.get(cache_key) is task:
        _scan_tasks.pop(cache_key, None)
    try:
        task.result()
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.error("Unhandled robot scan refresh task error", exc_info=True)


def trigger_robot_scan_refresh(
    port: int = setting.ROBOT_HEALTH_PORT,
    network: str | None = None,
) -> bool:
    cache_key = build_robot_scan_cache_key(port, network)
    existing_task = _scan_tasks.get(cache_key)
    if existing_task is not None and not existing_task.done():
        return False

    task = asyncio.create_task(
        refresh_robot_scan_cache(port=port, network=network),
        name=f"robot-scan-{cache_key}",
    )
    _scan_tasks[cache_key] = task
    task.add_done_callback(lambda completed, key=cache_key: _handle_scan_task_done(key, completed))
    return True


async def _robot_scan_scheduler() -> None:
    interval = max(1, int(setting.ROBOT_SCAN_INTERVAL_SECONDS))
    while True:
        trigger_robot_scan_refresh(port=setting.ROBOT_HEALTH_PORT)
        await asyncio.sleep(interval)


def start_robot_scan_scheduler() -> None:
    global _scan_scheduler_task
    if _scan_scheduler_task is not None and not _scan_scheduler_task.done():
        return
    _scan_scheduler_task = asyncio.create_task(
        _robot_scan_scheduler(),
        name="robot-scan-scheduler",
    )
    logger.info("Robot scan scheduler started, interval=%ss", setting.ROBOT_SCAN_INTERVAL_SECONDS)


def stop_robot_scan_scheduler() -> None:
    global _scan_scheduler_task
    if _scan_scheduler_task is not None:
        _scan_scheduler_task.cancel()
        _scan_scheduler_task = None
    for task in list(_scan_tasks.values()):
        task.cancel()
    _scan_tasks.clear()


def get_scan_gateway_collection():
    if mongodb.client is None and not mongodb.connect():
        raise RuntimeError("MongoDB connection is not available")
    collection = mongodb.get_database(setting.MESSAGE_COLLECTION)[setting.ROBOT_SCAN_GATEWAY_COLLECTION]
    collection.create_index("gateway", unique=True)
    return collection


def normalize_scan_gateway(gateway: str) -> str:
    value = (gateway or "").strip()
    try:
        ip = ipaddress.IPv4Address(value)
    except Exception as exc:
        raise ValueError("扫描网关必须是有效 IPv4 地址") from exc
    return str(ip)


def build_gateway_scan_targets(gateway: str) -> tuple[list[str], str]:
    gateway_ip = normalize_scan_gateway(gateway)
    prefix, suffix_text = gateway_ip.rsplit(".", 1)
    suffix = int(suffix_text)
    start_suffix = suffix + 1
    if start_suffix > 255:
        raise ValueError("扫描网关不能是网段最后一个地址")
    targets = [f"{prefix}.{index}" for index in range(start_suffix, 256)]
    return targets, f"{prefix}.{start_suffix}-255"


def _format_scan_gateway_doc(doc: dict) -> dict:
    gateway = str(doc.get("gateway", ""))
    try:
        _, scan_range = build_gateway_scan_targets(gateway)
    except ValueError:
        scan_range = ""
    return {
        "gateway": gateway,
        "scan_range": scan_range,
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


def list_scan_gateways() -> dict:
    collection = get_scan_gateway_collection()
    cursor = collection.find({}, {"_id": 0}).sort("gateway", 1)
    return {"gateways": [_format_scan_gateway_doc(doc) for doc in cursor]}


def add_scan_gateway(gateway: str) -> dict:
    normalized_gateway = normalize_scan_gateway(gateway)
    build_gateway_scan_targets(normalized_gateway)
    now = _utc_now()
    collection = get_scan_gateway_collection()
    collection.update_one(
        {"gateway": normalized_gateway},
        {
            "$set": {
                "gateway": normalized_gateway,
                "updated_at": now,
            },
            "$setOnInsert": {
                "created_at": now,
            },
        },
        upsert=True,
    )
    doc = collection.find_one({"gateway": normalized_gateway}, {"_id": 0}) or {"gateway": normalized_gateway}
    return _format_scan_gateway_doc(doc)


def delete_scan_gateway(gateway: str) -> dict:
    normalized_gateway = normalize_scan_gateway(gateway)
    collection = get_scan_gateway_collection()
    result = collection.delete_one({"gateway": normalized_gateway})
    return {"deleted": result.deleted_count > 0, "gateway": normalized_gateway}


def get_local_ip_and_prefix() -> tuple:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
            connection.connect(("8.8.8.8", 80))
            local_ip = connection.getsockname()[0]
        parts = local_ip.rsplit(".", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return "192.168.1", local_ip
    except Exception:
        return "192.168.1", "unknown"


def get_local_ip() -> str:
    prefix, suffix = get_local_ip_and_prefix()
    if suffix == "unknown":
        return ""
    return f"{prefix}.{suffix}"


def resolve_server_scan_ip() -> str:
    configured_host = str(getattr(setting, "DATA_HANDLER_HOST", "") or "").strip()
    host = configured_host.split(":", 1)[0]

    if host and host.lower() not in LOCAL_HOSTS:
        try:
            resolved_host = socket.gethostbyname(host)
            ipaddress.IPv4Address(resolved_host)
            return resolved_host
        except Exception as exc:
            logger.warning(f"Failed to resolve configured server host {host}: {exc}")

    local_ip = get_local_ip()
    if local_ip:
        return local_ip

    gateway_ip = get_gateway_ip()
    if gateway_ip:
        return gateway_ip
    return "192.168.1.1"


def get_scan_prefix_from_server() -> tuple[str, str]:
    server_ip = resolve_server_scan_ip()
    try:
        ipaddress.IPv4Address(server_ip)
        return server_ip.rsplit(".", 1)[0], server_ip
    except Exception:
        logger.warning(f"Invalid server IP for robot scan: {server_ip}")
        return "192.168.1", server_ip


def _dedupe_targets(targets: list[str]) -> list[str]:
    return list(dict.fromkeys(targets))


def resolve_scan_targets(network: str | None = None) -> tuple[list[str], str, str, list[str]]:
    server_ip = resolve_server_scan_ip()
    value = (network or "").strip()
    if not value:
        try:
            gateway_docs = list_scan_gateways()["gateways"]
        except RuntimeError as exc:
            logger.warning(f"Robot scan gateway lookup unavailable, falling back to local network: {exc}")
            gateway_docs = []
        if gateway_docs:
            targets: list[str] = []
            scan_ranges: list[str] = []
            gateways: list[str] = []
            for gateway_doc in gateway_docs:
                gateway_targets, gateway_range = build_gateway_scan_targets(gateway_doc["gateway"])
                targets.extend(gateway_targets)
                scan_ranges.append(gateway_range)
                gateways.append(gateway_doc["gateway"])
            targets = _dedupe_targets(targets)
            if len(targets) > MAX_SCAN_HOSTS:
                raise ValueError(f"一次最多扫描 {MAX_SCAN_HOSTS} 个地址")
            return targets, ", ".join(scan_ranges), server_ip, gateways

        ip_prefix, server_ip = get_scan_prefix_from_server()
        return [f"{ip_prefix}.{index}" for index in range(1, 256)], f"{ip_prefix}.1-255", server_ip, []

    if "-" in value:
        start_text, end_text = [part.strip() for part in value.split("-", 1)]
        start_ip = ipaddress.IPv4Address(start_text)
        end_ip = ipaddress.IPv4Address(end_text)
        if int(end_ip) < int(start_ip):
            raise ValueError("扫描网段结束 IP 不能小于起始 IP")
        count = int(end_ip) - int(start_ip) + 1
        if count > MAX_SCAN_HOSTS:
            raise ValueError(f"一次最多扫描 {MAX_SCAN_HOSTS} 个地址")
        return [str(ipaddress.IPv4Address(int(start_ip) + index)) for index in range(count)], value, server_ip, []

    if "/" in value:
        network_obj = ipaddress.IPv4Network(value, strict=False)
        hosts = [str(ip) for ip in network_obj.hosts()]
        if len(hosts) > MAX_SCAN_HOSTS:
            raise ValueError(f"一次最多扫描 {MAX_SCAN_HOSTS} 个地址")
        return hosts, str(network_obj), server_ip, []

    parts = value.split(".")
    if len(parts) == 3 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts):
        return [f"{value}.{index}" for index in range(1, 256)], f"{value}.1-255", server_ip, []

    ipaddress.IPv4Address(value)
    return [value], value, server_ip, []


def get_gateway_ip() -> str:
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["ipconfig"],
                capture_output=True,
                text=True,
                timeout=5,
                encoding="gbk",
                errors="ignore",
            )
            lines = result.stdout.split("\n")
            for index, line in enumerate(lines):
                line = line.strip()
                if "默认网关" in line or "Default Gateway" in line:
                    ip = line.split(":")[-1].strip() if ":" in line else ""
                    if ip and re.match(r"\d+\.\d+\.\d+\.\d+", ip):
                        return ip
                    if index + 1 < len(lines):
                        next_line = lines[index + 1].strip()
                        ip = next_line.split(":")[-1].strip() if ":" in next_line else ""
                        if ip and re.match(r"\d+\.\d+\.\d+\.\d+", ip):
                            return ip
            local_prefix, _ = get_local_ip_and_prefix()
            return f"{local_prefix}.1"

        try:
            result = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                match = re.search(r"default via (\d+\.\d+\.\d+\.\d+)", result.stdout)
                if match:
                    return match.group(1)
        except Exception:
            pass
        try:
            result = subprocess.run(["route", "-n"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if line.startswith("0.0.0.0") or line.startswith("default"):
                        parts = line.split()
                        if len(parts) >= 2 and re.match(r"\d+\.\d+\.\d+\.\d+", parts[1]):
                            return parts[1]
        except Exception:
            pass
        try:
            with open("/proc/net/route", "r") as route_file:
                for line in route_file:
                    parts = line.strip().split("\t")
                    if len(parts) >= 3 and parts[1] == "00000000":
                        return socket.inet_ntoa(bytes.fromhex(parts[2]))
        except Exception:
            pass
        return "192.168.1.1"
    except Exception as exc:
        logger.warning(f"Failed to get gateway IP: {exc}")
        return "192.168.1.1"


def _pick_field(data: dict, *keys: str):
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def _merge_robot_health_fields(robot_info: dict, data: dict) -> None:
    if not isinstance(data, dict):
        return
    robot_info["name"] = _pick_field(data, "name", "robot_name") or robot_info.get("name")
    robot_info["serial_number"] = (
        _pick_field(data, "serialNumber", "serial_number", "robot_serial")
        or robot_info.get("serial_number")
    )
    robot_info["robot_type"] = (
        _pick_field(data, "robotType", "robot_type")
        or robot_info.get("robot_type")
    )
    robot_info["version"] = (
        _pick_field(data, "server_version", "version", "robot_server_version")
        or robot_info.get("version")
    )
    robot_info["api_version"] = (
        _pick_field(data, "api_version", "opentrons_api_version")
        or robot_info.get("api_version")
    )
    robot_info["fw_version"] = (
        _pick_field(data, "fw_version", "firmware_version")
        or robot_info.get("fw_version")
    )


def _is_port_open(
    ip: str,
    port: int,
    timeout: float = setting.ROBOT_SCAN_CONNECT_TIMEOUT_SECONDS,
) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def check_robot_health_sync(ip: str, port: int = 31950) -> dict:
    url = f"http://{ip}:{port}/health"
    robot_info = {
        "ip": ip,
        "port": port,
        "online": False,
        "service_status": "unknown",
        "version": None,
        "name": None,
        "robot_type": None,
        "serial_number": None,
        "error": None,
        "api_version": None,
        "fw_version": None,
        "health_fetch_failed": False,
    }
    health_detail_error: str | None = None

    if not _is_port_open(ip, port):
        robot_info["error"] = "connection timeout"
        return robot_info

    try:
        response = requests.get(
            url,
            headers=ROBOT_HEADERS,
            timeout=setting.ROBOT_SCAN_HTTP_TIMEOUT_SECONDS,
        )
        if response.status_code != 200:
            robot_info["online"] = True
            robot_info["service_status"] = "error"
            robot_info["error"] = f"/health HTTP {response.status_code}"
            try:
                _merge_robot_health_fields(robot_info, response.json())
            except Exception:
                pass
            return robot_info

        robot_info["online"] = True
        robot_info["service_status"] = "normal"
        try:
            _merge_robot_health_fields(robot_info, response.json())
        except Exception as exc:
            health_detail_error = f"解析 /health 响应失败: {exc}"

        health_url = f"http://{ip}:{port}/robot/health"
        try:
            health_response = requests.get(
                health_url,
                headers=ROBOT_HEADERS,
                timeout=setting.ROBOT_SCAN_HTTP_TIMEOUT_SECONDS,
            )
            if health_response.status_code == 200:
                _merge_robot_health_fields(robot_info, health_response.json())
            else:
                health_detail_error = f"/robot/health HTTP {health_response.status_code}"
        except Exception as exc:
            health_detail_error = f"/robot/health 请求失败: {exc}"

        if health_detail_error:
            robot_info["health_fetch_failed"] = True
            robot_info["error"] = f"部分详细信息获取失败: {health_detail_error}"
            logger.warning(f"Robot {ip} health detail incomplete: {health_detail_error}")
    except Exception as exc:
        robot_info["error"] = str(exc)
        robot_info["service_status"] = "error"
        robot_info["online"] = True

    return robot_info


def execute_robot_command_sync(
    ip: str,
    port: int,
    method: str,
    path: str,
    body: dict | None = None,
    timeout: int = 10,
) -> dict:
    normalized_path = path if path.startswith("/") else f"/{path}"
    url = f"http://{ip}:{port}{normalized_path}"
    result = {
        "ip": ip,
        "success": False,
        "status_code": None,
        "response": None,
        "error": None,
    }
    try:
        response = requests.request(
            method=method.upper(),
            url=url,
            headers=ROBOT_HEADERS,
            json=body if body is not None else None,
            timeout=timeout,
        )
        result["status_code"] = response.status_code
        result["success"] = 200 <= response.status_code < 300
        try:
            result["response"] = response.json()
        except Exception:
            result["response"] = response.text
        if not result["success"]:
            result["error"] = f"HTTP {response.status_code}"
    except Exception as exc:
        result["error"] = str(exc)
    return result


async def execute_robot_commands_batch(
    ips: list[str],
    port: int,
    method: str,
    path: str,
    body: dict | None = None,
    timeout: int = 10,
) -> list[dict]:
    loop = asyncio.get_running_loop()
    tasks = [
        loop.run_in_executor(
            robot_executor,
            execute_robot_command_sync,
            ip,
            port,
            method,
            path,
            body,
            timeout,
        )
        for ip in ips
    ]
    return list(await asyncio.gather(*tasks))


async def scan_robots(port: int = setting.ROBOT_HEALTH_PORT, network: str | None = None) -> dict:
    try:
        ip_list, scan_network, server_ip, scan_gateways = resolve_scan_targets(network)
    except ValueError as exc:
        raise ValueError(f"无效扫描网段: {exc}") from exc
    except RuntimeError as exc:
        raise ValueError(str(exc)) from exc

    gateway_ip = get_gateway_ip()
    logger.info(
        f"Scanning network: {scan_network} "
        f"from server {server_ip}, gateway {gateway_ip}"
    )

    loop = asyncio.get_running_loop()
    tasks = [
        loop.run_in_executor(robot_executor, check_robot_health_sync, ip, port)
        for ip in ip_list
    ]
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks),
            timeout=max(1, setting.ROBOT_SCAN_MAX_DURATION_SECONDS),
        )
    except asyncio.TimeoutError as exc:
        for task in tasks:
            task.cancel()
        raise RuntimeError(
            f"设备扫描超过 {setting.ROBOT_SCAN_MAX_DURATION_SECONDS} 秒，已终止本次刷新"
        ) from exc

    online_robots = [robot for robot in results if robot["online"]]
    offline_robots = [robot for robot in results if not robot["online"]]
    abnormal_robots = [
        robot for robot in online_robots
        if robot.get("service_status") != "normal"
    ]
    return {
        "total": len(results),
        "online_count": len(online_robots),
        "offline_count": len(offline_robots),
        "abnormal_count": len(abnormal_robots),
        "scan_network": scan_network,
        "server_ip": server_ip,
        "gateway": gateway_ip,
        "scan_gateways": scan_gateways,
        "online_robots": online_robots,
        "offline_robots": offline_robots,
        "abnormal_robots": abnormal_robots,
    }


def get_robot_detail(ip: str, port: int = setting.ROBOT_HEALTH_PORT) -> dict:
    return check_robot_health_sync(ip, port)
