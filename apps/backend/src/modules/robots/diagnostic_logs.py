from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime, timezone
import ipaddress
import os
from pathlib import Path
import re
import shlex
import threading
from typing import Any
from uuid import uuid4

import core.config as setting
from core.database import mongodb
from modules.robots.files.ssh_client import OpentronsSshClient

from core.logging import get_logger

logger = get_logger(__name__)


DIAGNOSTIC_FOLDER_OPTIONS: tuple[dict[str, Any], ...] = (
    {
        "key": "data",
        "label": "设备数据",
        "description": "/data、VERSION.json、Opentrons 配置和序列号",
        "default_selected": True,
        "command": """
            cp -r /data/* {diag}/data/
            cp -r /etc/VERSION.json {diag}/data/
            cp -r /tmp/.config/Opentrons {diag}/data/
            printf '%s\\n' "$DIAG_SERIAL" > {diag}/data/serial.txt
        """,
    },
    {
        "key": "server",
        "label": "服务数据",
        "description": "robot-server 与 system-server 的持久化数据",
        "default_selected": True,
        "command": """
            cp -r /var/lib/opentrons-robot-server/. {diag}/server/opentrons-robot-server/
            cp -r /var/lib/opentrons-system-server/. {diag}/server/opentrons-system-server/
        """,
    },
    {
        "key": "logs",
        "label": "系统日志",
        "description": "/var/log（不含 journal 目录）、journalctl 和 dmesg",
        "default_selected": True,
        "command": """
            find /var/log -mindepth 1 -maxdepth 1 ! -name journal -exec cp -r -- '{{}}' {diag}/logs/ \\;
            journalctl > {diag}/logs/journal.log
            dmesg > {diag}/logs/dmesg.log
        """,
    },
    {
        "key": "system",
        "label": "系统状态",
        "description": "主机、时间、进程、资源和 systemd 服务状态",
        "default_selected": True,
        "command": """
            hostname > {diag}/system/hostname.txt
            uname -a > {diag}/system/uname.txt
            date > {diag}/system/datetime.txt
            timedatectl >> {diag}/system/datetime.txt || true
            uptime > {diag}/system/uptime.txt || true
            ps aux > {diag}/system/psaux.txt
            top -c -b -n 10 > {diag}/system/top.txt
            free -wl -c 10 -s 10 > {diag}/system/free.txt
            systemctl status > {diag}/system/services_overview.txt
            systemctl status 'opentrons*' > {diag}/system/opentrons_services.txt || true
        """,
    },
    {
        "key": "network",
        "label": "网络信息",
        "description": "网卡、DNS、NTP 连通性和 releases.json",
        "default_selected": True,
        "command": """
            /sbin/ifconfig > {diag}/network/network.txt
            printf '\\n\\n' >> {diag}/network/network.txt
            /sbin/ip --details link show >> {diag}/network/network.txt
            printf '\\n\\n' >> {diag}/network/network.txt
            (nmcli dev list || nmcli dev show) 2>/dev/null | grep DNS >> {diag}/network/network.txt || true
            printf '\\n\\n' >> {diag}/network/network.txt
            ping -c 2 -w 2 time.google.com >> {diag}/network/network.txt || true
            ping -c 2 -w 2 ntp.tencent.com >> {diag}/network/network.txt || true
            ping -c 2 -w 2 time.amazonaws.cn >> {diag}/network/network.txt || true
            wget https://builds.opentrons.com/ot3-oe/releases.json -P {diag}/network/
        """,
    },
)

_OPTION_BY_KEY = {item["key"]: item for item in DIAGNOSTIC_FOLDER_OPTIONS}
_TASKS: dict[str, dict[str, Any]] = {}
_TASK_LOCK = threading.RLock()
_INDEX_LOCK = threading.Lock()
_INDEX_READY = False
_COORDINATOR_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="robot-log-batch")
_CLEANUP_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="robot-log-cleanup")
_CLEANUP_STOP_EVENT = threading.Event()
_PENDING_CLEANUP_LOCK = threading.Lock()
_PENDING_CLEANUP_RECORD_IDS: set[str] = set()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items() if key != "device_map"}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    return value


def _resolve_record_archive_path(record: dict[str, Any]) -> Path:
    archive_path = str(record.get("archive_path") or "").strip()
    if not archive_path:
        raise FileNotFoundError("该记录没有可下载的服务器 Log 文件")
    download_root = Path(setting.ROBOT_LOG_DOWNLOAD_DIR).resolve()
    resolved_path = Path(archive_path).resolve()
    if resolved_path == download_root or download_root not in resolved_path.parents:
        raise ValueError("Log 文件路径不在允许的服务器目录内")
    return resolved_path


def _record_file_available(record: dict[str, Any]) -> bool:
    if record.get("file_deleted_at"):
        return False
    try:
        archive_path = _resolve_record_archive_path(record)
    except (FileNotFoundError, ValueError):
        return False
    return archive_path.is_file()


def _serialize_record(record: dict[str, Any]) -> dict[str, Any]:
    serialized = _serialize(record)
    serialized["file_available"] = _record_file_available(record)
    return serialized


def _serialize_task(task: dict[str, Any]) -> dict[str, Any]:
    serialized = _serialize(task)
    serialized["devices"] = [_serialize_record(record) for record in task.get("devices", [])]
    return serialized


def _truncate_command_output(value: str, limit: int = 8000) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n...（输出已截断）"


def _safe_name(value: str, fallback: str = "robot") -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "").strip()).strip("-._")
    return normalized[:80] or fallback


def _normalize_device(device: dict[str, Any]) -> dict[str, str]:
    ip = str(device.get("ip") or "").strip()
    try:
        ipaddress.ip_address(ip)
    except ValueError as exc:
        raise ValueError(f"无效设备 IP: {ip or '空'}") from exc
    return {
        "ip": ip,
        "name": str(device.get("name") or "").strip() or ip,
    }


def _get_collection():
    global _INDEX_READY
    if mongodb.client is None and not mongodb.connect():
        raise RuntimeError("MongoDB 连接失败，无法创建 Log 下载任务")
    collection = mongodb.get_database(setting.MESSAGE_COLLECTION)[setting.ROBOT_LOG_DOWNLOAD_COLLECTION]
    if not _INDEX_READY:
        with _INDEX_LOCK:
            if not _INDEX_READY:
                collection.create_index([("started_at", -1)])
                collection.create_index([("task_id", 1), ("started_at", -1)])
                collection.create_index([("robot_ip", 1), ("started_at", -1)])
                collection.create_index([("cleanup_status", 1), ("updated_at", 1)])
                _INDEX_READY = True
    return collection


def list_folder_options() -> dict[str, Any]:
    return {
        "folders": [
            {key: value for key, value in item.items() if key != "command"}
            for item in DIAGNOSTIC_FOLDER_OPTIONS
        ],
        "download_root": str(Path(setting.ROBOT_LOG_DOWNLOAD_DIR).resolve()),
        "max_concurrency": setting.ROBOT_LOG_DOWNLOAD_MAX_WORKERS,
    }


def _selected_folder_details(folder_keys: list[str]) -> list[dict[str, str]]:
    return [
        {
            "key": key,
            "label": str(_OPTION_BY_KEY[key]["label"]),
            "description": str(_OPTION_BY_KEY[key]["description"]),
        }
        for key in folder_keys
    ]


def create_download_task(
    *,
    devices: list[dict[str, Any]],
    folder_keys: list[str],
    concurrency: int,
) -> dict[str, Any]:
    collection = _get_collection()
    if not devices:
        raise ValueError("请至少选择一台设备")

    normalized_devices: list[dict[str, str]] = []
    seen_ips: set[str] = set()
    for raw_device in devices:
        device = _normalize_device(raw_device)
        if device["ip"] in seen_ips:
            continue
        seen_ips.add(device["ip"])
        normalized_devices.append(device)

    normalized_folder_keys = list(dict.fromkeys(str(key).strip() for key in folder_keys if str(key).strip()))
    invalid_keys = [key for key in normalized_folder_keys if key not in _OPTION_BY_KEY]
    if invalid_keys:
        raise ValueError(f"不支持的 Log 目录: {', '.join(invalid_keys)}")
    if not normalized_folder_keys:
        raise ValueError("请至少选择一个 Log 目录")

    worker_count = max(1, min(int(concurrency), setting.ROBOT_LOG_DOWNLOAD_MAX_WORKERS, len(normalized_devices)))
    task_id = uuid4().hex
    started_at = _utc_now()
    date_part = started_at.astimezone().strftime("%Y-%m-%d")
    folder_details = _selected_folder_details(normalized_folder_keys)
    records: list[dict[str, Any]] = []

    for device in normalized_devices:
        record_id = uuid4().hex
        local_folder_name = f"{_safe_name(device['name'])}_{_safe_name(device['ip'])}_{task_id[:8]}"
        server_directory = str(Path(setting.ROBOT_LOG_DOWNLOAD_DIR).resolve() / date_part / local_folder_name)
        records.append(
            {
                "_id": record_id,
                "task_id": task_id,
                "robot_ip": device["ip"],
                "device_name": device["name"],
                "selected_folders": deepcopy(folder_details),
                "server_directory": server_directory,
                "archive_path": None,
                "archive_name": None,
                "archive_size": 0,
                "file_available": False,
                "file_deleted_at": None,
                "remote_diag_path": None,
                "remote_archive_path": None,
                "cleanup_status": "not_started",
                "cleanup_attempts": 0,
                "cleanup_error": None,
                "cleanup_finished_at": None,
                "cleanup_only_failure": False,
                "status": "queued",
                "progress": 0,
                "current_step": "等待下载",
                "completed_steps": 0,
                "total_steps": len(normalized_folder_keys) + 2,
                "started_at": started_at,
                "downloaded_at": None,
                "finished_at": None,
                "updated_at": started_at,
                "error": None,
                "command_logs": [],
            }
        )

    collection.insert_many(deepcopy(records), ordered=True)
    task = {
        "task_id": task_id,
        "status": "queued",
        "concurrency": worker_count,
        "active_workers": 0,
        "folder_keys": normalized_folder_keys,
        "folders": folder_details,
        "total_devices": len(records),
        "completed_devices": 0,
        "successful_devices": 0,
        "warning_devices": 0,
        "failed_devices": 0,
        "progress": 0,
        "started_at": started_at,
        "finished_at": None,
        "devices": deepcopy(records),
        "device_map": {record["_id"]: index for index, record in enumerate(records)},
    }
    with _TASK_LOCK:
        _TASKS[task_id] = task

    try:
        _COORDINATOR_EXECUTOR.submit(
            _run_batch,
            task_id,
            deepcopy(normalized_devices),
            normalized_folder_keys,
            worker_count,
        )
    except Exception:
        collection.update_many(
            {"task_id": task_id},
            {"$set": {"status": "failed", "current_step": "任务启动失败", "updated_at": _utc_now()}},
        )
        with _TASK_LOCK:
            _TASKS.pop(task_id, None)
        raise
    return get_download_task(task_id)


def _task_snapshot(task_id: str) -> dict[str, Any] | None:
    with _TASK_LOCK:
        task = _TASKS.get(task_id)
        return deepcopy(task) if task else None


def get_download_task(task_id: str) -> dict[str, Any]:
    task = _task_snapshot(task_id)
    if task is not None:
        return _serialize_task(task)

    collection = _get_collection()
    records = list(collection.find({"task_id": task_id}).sort("started_at", 1))
    if not records:
        raise KeyError(task_id)
    completed = sum(record.get("status") in {"success", "warning", "failed"} for record in records)
    success = sum(record.get("status") == "success" for record in records)
    warning = sum(record.get("status") == "warning" for record in records)
    failed = sum(record.get("status") == "failed" for record in records)
    progress = round(sum(int(record.get("progress") or 0) for record in records) / len(records))
    has_active_records = any(record.get("status") in {"queued", "running"} for record in records)
    task_status = (
        "running"
        if has_active_records
        else (
            "completed_with_errors"
            if failed
            else ("completed_with_warnings" if warning else "completed")
        )
    )
    finished_values = [
        record.get("finished_at") or record.get("downloaded_at") or record.get("updated_at")
        for record in records
        if record.get("finished_at") or record.get("downloaded_at") or record.get("updated_at")
    ]
    return _serialize_task(
        {
            "task_id": task_id,
            "status": task_status,
            "concurrency": None,
            "active_workers": 0,
            "folder_keys": [item.get("key") for item in records[0].get("selected_folders", [])],
            "folders": records[0].get("selected_folders", []),
            "total_devices": len(records),
            "completed_devices": completed,
            "successful_devices": success,
            "warning_devices": warning,
            "failed_devices": failed,
            "progress": progress,
            "started_at": min(record.get("started_at") for record in records),
            "finished_at": max(finished_values) if finished_values and not has_active_records else None,
            "devices": records,
        }
    )


def list_download_records(*, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    collection = _get_collection()
    normalized_page = max(1, int(page))
    normalized_page_size = max(1, min(100, int(page_size)))
    total = collection.count_documents({})
    cursor = (
        collection.find({})
        .sort("started_at", -1)
        .skip((normalized_page - 1) * normalized_page_size)
        .limit(normalized_page_size)
    )
    return {
        "records": [_serialize_record(record) for record in cursor],
        "total": total,
        "page": normalized_page,
        "page_size": normalized_page_size,
    }


def _recompute_task_locked(task: dict[str, Any]) -> None:
    devices = task["devices"]
    task["active_workers"] = sum(record["status"] == "running" for record in devices)
    task["completed_devices"] = sum(
        record["status"] in {"success", "warning", "failed"} for record in devices
    )
    task["successful_devices"] = sum(record["status"] == "success" for record in devices)
    task["warning_devices"] = sum(record["status"] == "warning" for record in devices)
    task["failed_devices"] = sum(record["status"] == "failed" for record in devices)
    task["progress"] = round(sum(int(record.get("progress") or 0) for record in devices) / len(devices))


def _update_record(task_id: str, record_id: str, **updates: Any) -> None:
    updates["updated_at"] = _utc_now()
    _get_collection().update_one({"_id": record_id}, {"$set": deepcopy(updates)})
    with _TASK_LOCK:
        task = _TASKS.get(task_id)
        if task is None:
            return
        index = task["device_map"][record_id]
        task["devices"][index].update(deepcopy(updates))
        _recompute_task_locked(task)


def _append_command_log(
    task_id: str,
    record_id: str,
    *,
    label: str,
    command: str,
) -> str:
    command_id = uuid4().hex
    entry = {
        "id": command_id,
        "label": label,
        "command": str(command).strip(),
        "status": "running",
        "started_at": _utc_now(),
        "finished_at": None,
        "output": "",
        "error": None,
    }
    with _TASK_LOCK:
        task = _TASKS.get(task_id)
        if task is None:
            return command_id
        index = task["device_map"][record_id]
        command_logs = task["devices"][index].setdefault("command_logs", [])
        command_logs.append(entry)
        persisted_logs = deepcopy(command_logs)
    _get_collection().update_one(
        {"_id": record_id},
        {"$set": {"command_logs": persisted_logs, "updated_at": _utc_now()}},
    )
    return command_id


def _finish_command_log(
    task_id: str,
    record_id: str,
    command_id: str,
    *,
    status: str,
    output: str = "",
    error: str | None = None,
) -> None:
    with _TASK_LOCK:
        task = _TASKS.get(task_id)
        if task is None:
            return
        index = task["device_map"][record_id]
        command_logs = task["devices"][index].setdefault("command_logs", [])
        for entry in command_logs:
            if entry.get("id") != command_id:
                continue
            entry.update(
                {
                    "status": status,
                    "finished_at": _utc_now(),
                    "output": _truncate_command_output(output),
                    "error": _truncate_command_output(error or "") or None,
                }
            )
            break
        persisted_logs = deepcopy(command_logs)
    _get_collection().update_one(
        {"_id": record_id},
        {"$set": {"command_logs": persisted_logs, "updated_at": _utc_now()}},
    )


def _set_task_status(task_id: str, status: str, *, finished: bool = False) -> None:
    with _TASK_LOCK:
        task = _TASKS.get(task_id)
        if task is None:
            return
        task["status"] = status
        if finished:
            task["finished_at"] = _utc_now()
        _recompute_task_locked(task)


def _run_remote(client: Any, script: str) -> tuple[str, str]:
    payload = "set -eE -o pipefail\n" + script
    command = f"bash -lc {shlex.quote(payload)}"
    _stdin, stdout, stderr = client.exec_command(
        command,
        timeout=setting.ROBOT_LOG_COMMAND_TIMEOUT_SECONDS,
    )
    exit_code = stdout.channel.recv_exit_status()
    output = stdout.read().decode("utf-8", errors="replace").strip()
    error = stderr.read().decode("utf-8", errors="replace").strip()
    if exit_code != 0:
        raise RuntimeError(error or output or f"远程命令失败（exit {exit_code}）")
    return output, error


def _run_logged_remote(
    task_id: str,
    record_id: str,
    client: Any,
    *,
    label: str,
    script: str,
) -> tuple[str, str]:
    payload = "set -eE -o pipefail\n" + str(script).strip()
    command_id = _append_command_log(
        task_id,
        record_id,
        label=label,
        command=payload,
    )
    try:
        output, error = _run_remote(client, script)
    except Exception as exc:
        _finish_command_log(
            task_id,
            record_id,
            command_id,
            status="failed",
            error=str(exc),
        )
        raise
    _finish_command_log(
        task_id,
        record_id,
        command_id,
        status="success",
        output=output,
        error=error or None,
    )
    return output, error


def _record_progress(
    task_id: str,
    record_id: str,
    *,
    current_step: str,
    completed_steps: int,
    total_steps: int,
    fractional_step: float = 0,
) -> None:
    progress = round(((completed_steps + max(0.0, min(1.0, fractional_step))) / total_steps) * 100)
    _update_record(
        task_id,
        record_id,
        progress=min(99, progress),
        current_step=current_step,
        completed_steps=completed_steps,
    )


def _cleanup_remote_download_artifacts(
    task_id: str,
    record_id: str,
    ssh: OpentronsSshClient,
    *,
    remote_diag: str,
    remote_archive: str,
) -> int:
    cleanup_script = _build_remote_cleanup_script(remote_diag, remote_archive)
    command_id: str | None = None
    try:
        command_id = _append_command_log(
            task_id,
            record_id,
            label="清理设备 /data 临时文件",
            command="set -eE -o pipefail\n" + cleanup_script.strip(),
        )
    except Exception as log_exc:
        logger.warning("Unable to persist robot cleanup command log: %s", log_exc)

    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            with ssh.connect() as (cleanup_client, _cleanup_sftp):
                output, error = _run_remote(cleanup_client, cleanup_script)
            if command_id:
                try:
                    _finish_command_log(
                        task_id,
                        record_id,
                        command_id,
                        status="success",
                        output=output or f"第 {attempt} 次清理成功，设备残留已移除",
                        error=error or None,
                    )
                except Exception as log_exc:
                    logger.warning("Unable to persist robot cleanup result: %s", log_exc)
            return attempt
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Robot log cleanup attempt %s failed for %s: %s",
                attempt,
                ssh.ip,
                exc,
            )

    cleanup_error = RuntimeError(f"设备临时文件清理失败（已重试 3 次）: {last_error}")
    if command_id:
        try:
            _finish_command_log(
                task_id,
                record_id,
                command_id,
                status="failed",
                error=str(cleanup_error),
            )
        except Exception as log_exc:
            logger.warning("Unable to persist robot cleanup failure: %s", log_exc)
    raise cleanup_error


def _build_remote_cleanup_script(remote_diag: str, remote_archive: str) -> str:
    remote_root = setting.ROBOT_LOG_REMOTE_TEMP_ROOT.rstrip("/")
    expected_diag = re.compile(rf"{re.escape(remote_root)}/\.flex-diagnostics-[0-9a-f]{{32}}")
    if expected_diag.fullmatch(remote_diag) is None or remote_archive != f"{remote_diag}.tar.gz":
        raise ValueError("拒绝清理不属于 Log 下载任务的设备路径")
    return f"""
        rm -rf -- {shlex.quote(remote_diag)} {shlex.quote(remote_archive)}
        if [ -e {shlex.quote(remote_diag)} ] || [ -e {shlex.quote(remote_archive)} ]; then
            echo '设备诊断临时文件仍然存在' >&2
            exit 1
        fi
    """


def _refresh_task_after_deferred_cleanup(task_id: str) -> None:
    with _TASK_LOCK:
        task = _TASKS.get(task_id)
        if task is None:
            return
        _recompute_task_locked(task)
        if task["completed_devices"] == task["total_devices"]:
            task["status"] = (
                "completed_with_errors"
                if task["failed_devices"]
                else ("completed_with_warnings" if task["warning_devices"] else "completed")
            )


def _run_pending_cleanup(record: dict[str, Any], *, immediate: bool) -> None:
    record_id = str(record["_id"])
    task_id = str(record.get("task_id") or "")
    robot_ip = str(record.get("robot_ip") or "")
    remote_diag = str(record.get("remote_diag_path") or "")
    remote_archive = str(record.get("remote_archive_path") or "")
    attempt_count = int(record.get("cleanup_attempts") or 0)
    should_reschedule = False
    try:
        try:
            cleanup_script = _build_remote_cleanup_script(remote_diag, remote_archive)
        except ValueError as exc:
            _update_record(
                task_id,
                record_id,
                cleanup_status="invalid",
                cleanup_error=str(exc),
            )
            return
        if not immediate and _CLEANUP_STOP_EVENT.wait(setting.ROBOT_LOG_CLEANUP_RETRY_INTERVAL_SECONDS):
            return
        for _ in range(setting.ROBOT_LOG_CLEANUP_RETRY_ATTEMPTS):
            if _CLEANUP_STOP_EVENT.is_set():
                return
            attempt_count += 1
            try:
                ssh = OpentronsSshClient(robot_ip)
                with ssh.connect() as (cleanup_client, _cleanup_sftp):
                    _run_remote(
                        cleanup_client,
                        cleanup_script,
                    )
            except Exception as exc:
                _update_record(
                    task_id,
                    record_id,
                    cleanup_status="pending",
                    cleanup_attempts=attempt_count,
                    cleanup_error=_truncate_command_output(str(exc)),
                )
                if _CLEANUP_STOP_EVENT.wait(setting.ROBOT_LOG_CLEANUP_RETRY_INTERVAL_SECONDS):
                    return
                continue

            current_record = _get_download_record(record_id)
            updates: dict[str, Any] = {
                "cleanup_status": "success",
                "cleanup_attempts": attempt_count,
                "cleanup_error": None,
                "cleanup_finished_at": _utc_now(),
                "current_step": (
                    "下载完成，设备残留已清理"
                    if current_record.get("cleanup_only_failure")
                    else "下载失败，设备残留已清理"
                ),
            }
            if current_record.get("cleanup_only_failure"):
                updates.update({"status": "success", "error": None})
            _update_record(task_id, record_id, **updates)
            _refresh_task_after_deferred_cleanup(task_id)
            logger.info("Deferred robot log cleanup succeeded for %s record %s", robot_ip, record_id)
            return
        should_reschedule = True
    finally:
        with _PENDING_CLEANUP_LOCK:
            _PENDING_CLEANUP_RECORD_IDS.discard(record_id)
        if should_reschedule and not _CLEANUP_STOP_EVENT.is_set():
            try:
                _schedule_pending_cleanup(_get_download_record(record_id), immediate=False)
            except Exception as exc:
                logger.warning(
                    "Unable to reschedule pending robot log cleanup for %s record %s: %s",
                    robot_ip,
                    record_id,
                    exc,
                )


def _schedule_pending_cleanup(record: dict[str, Any], *, immediate: bool = False) -> bool:
    record_id = str(record["_id"])
    with _PENDING_CLEANUP_LOCK:
        if record_id in _PENDING_CLEANUP_RECORD_IDS:
            return False
        _PENDING_CLEANUP_RECORD_IDS.add(record_id)
    try:
        _CLEANUP_EXECUTOR.submit(_run_pending_cleanup, deepcopy(record), immediate=immediate)
    except Exception:
        with _PENDING_CLEANUP_LOCK:
            _PENDING_CLEANUP_RECORD_IDS.discard(record_id)
        raise
    return True


def resume_pending_diagnostic_log_cleanups() -> int:
    try:
        collection = _get_collection()
        records = list(collection.find({"cleanup_status": "pending"}))
    except Exception as exc:
        logger.warning("Unable to resume pending robot log cleanups: %s", exc)
        return 0
    scheduled = 0
    for record in records:
        if record.get("remote_diag_path") and record.get("remote_archive_path"):
            scheduled += int(_schedule_pending_cleanup(record, immediate=True))
    if scheduled:
        logger.info("Resumed %s pending robot log cleanup task(s)", scheduled)
    return scheduled


def retry_record_cleanup(record_id: str) -> dict[str, Any]:
    record = _get_download_record(record_id)
    if not record.get("remote_diag_path") or not record.get("remote_archive_path"):
        raise ValueError("该记录没有可重试的设备残留路径")
    _update_record(
        str(record.get("task_id") or ""),
        str(record["_id"]),
        cleanup_status="pending",
        cleanup_error=None,
    )
    refreshed = _get_download_record(record_id)
    scheduled = _schedule_pending_cleanup(refreshed, immediate=True)
    return {"success": True, "record_id": str(record["_id"]), "scheduled": scheduled}


def _download_device(
    task_id: str,
    record: dict[str, Any],
    folder_keys: list[str],
) -> None:
    record_id = record["_id"]
    robot_ip = record["robot_ip"]
    total_steps = record["total_steps"]
    local_directory = Path(record["server_directory"])
    local_directory.mkdir(parents=True, exist_ok=True)
    remote_token = uuid4().hex
    remote_root = setting.ROBOT_LOG_REMOTE_TEMP_ROOT
    remote_diag = f"{remote_root}/.flex-diagnostics-{remote_token}"
    remote_archive = f"{remote_root}/.flex-diagnostics-{remote_token}.tar.gz"
    completed_steps = 0
    partial_path: Path | None = None
    final_path: Path | None = None
    archive_name: str | None = None
    downloaded_at: datetime | None = None
    operation_error: Exception | None = None
    cleanup_error: Exception | None = None
    cleanup_attempts = 0

    _update_record(
        task_id,
        record_id,
        status="running",
        current_step="连接设备",
        progress=1,
        remote_diag_path=remote_diag,
        remote_archive_path=remote_archive,
        cleanup_status="not_started",
        cleanup_attempts=0,
        cleanup_error=None,
        cleanup_finished_at=None,
        cleanup_only_failure=False,
    )
    ssh = OpentronsSshClient(robot_ip)
    try:
        with ssh.connect() as (client, sftp):
            serial_output, _ = _run_logged_remote(
                task_id,
                record_id,
                client,
                label="初始化诊断目录",
                script=f"""
                    DIAG_SERIAL=$(hostnamectl --static 2>/dev/null || hostname)
                    export DIAG_SERIAL
                    mkdir -p {shlex.quote(remote_diag)}/{{data,logs,system,network,server}}
                    mkdir -p {shlex.quote(remote_diag)}/server/opentrons-robot-server
                    mkdir -p {shlex.quote(remote_diag)}/server/opentrons-system-server
                    printf '%s' "$DIAG_SERIAL"
                """,
            )
            serial = _safe_name(serial_output.splitlines()[-1] if serial_output else record["device_name"])

            for folder_key in folder_keys:
                option = _OPTION_BY_KEY[folder_key]
                _record_progress(
                    task_id,
                    record_id,
                    current_step=f"收集{option['label']}",
                    completed_steps=completed_steps,
                    total_steps=total_steps,
                )
                command = str(option["command"]).format(diag=shlex.quote(remote_diag))
                _run_logged_remote(
                    task_id,
                    record_id,
                    client,
                    label=f"收集{option['label']}",
                    script=f"DIAG_SERIAL={shlex.quote(serial)}\nexport DIAG_SERIAL\n{command}",
                )
                completed_steps += 1
                _record_progress(
                    task_id,
                    record_id,
                    current_step=f"已收集{option['label']}",
                    completed_steps=completed_steps,
                    total_steps=total_steps,
                )

            _record_progress(
                task_id,
                record_id,
                current_step="生成诊断压缩包",
                completed_steps=completed_steps,
                total_steps=total_steps,
            )
            _run_logged_remote(
                task_id,
                record_id,
                client,
                label="生成诊断压缩包",
                script=f"tar -zcf {shlex.quote(remote_archive)} -C {shlex.quote(remote_diag)} .",
            )
            completed_steps += 1
            timestamp = _utc_now().astimezone().strftime("%Y_%m_%d_%H_%M_%S")
            archive_name = f"{serial}_{timestamp}_diag.tar.gz"
            final_path = local_directory / archive_name
            partial_path = local_directory / f".{archive_name}.part"
            last_download_progress = -1

            def handle_download_progress(transferred: int, total: int) -> None:
                nonlocal last_download_progress
                percent = round((transferred / total) * 100) if total else 0
                if percent == last_download_progress or (percent < 100 and percent % 2):
                    return
                last_download_progress = percent
                _record_progress(
                    task_id,
                    record_id,
                    current_step=f"下载压缩包 {percent}%",
                    completed_steps=completed_steps,
                    total_steps=total_steps,
                    fractional_step=percent / 100,
                )

            sftp_command_id = _append_command_log(
                task_id,
                record_id,
                label="下载压缩包到服务器",
                command=f"sftp.get {shlex.quote(remote_archive)} {shlex.quote(str(partial_path))}",
            )
            try:
                sftp.get(remote_archive, str(partial_path), callback=handle_download_progress)
            except Exception as exc:
                _finish_command_log(
                    task_id,
                    record_id,
                    sftp_command_id,
                    status="failed",
                    error=str(exc),
                )
                raise
            _finish_command_log(
                task_id,
                record_id,
                sftp_command_id,
                status="success",
                output=f"已下载到 {partial_path}",
            )
            os.replace(partial_path, final_path)
            downloaded_at = _utc_now()
    except Exception as exc:
        operation_error = exc
        logger.error("Robot diagnostic log download failed for %s: %s", robot_ip, exc, exc_info=True)
    finally:
        try:
            _update_record(
                task_id,
                record_id,
                current_step="清理设备临时文件",
                progress=99 if operation_error is None else 100,
                cleanup_status="running",
            )
        except Exception as progress_exc:
            logger.warning("Unable to update robot cleanup progress for %s: %s", robot_ip, progress_exc)
        try:
            cleanup_attempts = _cleanup_remote_download_artifacts(
                task_id,
                record_id,
                ssh,
                remote_diag=remote_diag,
                remote_archive=remote_archive,
            ) or 1
        except Exception as exc:
            cleanup_error = exc
            cleanup_attempts = 3
        if partial_path and partial_path.exists():
            try:
                partial_path.unlink()
            except OSError as partial_cleanup_exc:
                logger.warning("Local partial log cleanup failed for %s: %s", robot_ip, partial_cleanup_exc)

    if operation_error is not None or cleanup_error is not None:
        cleanup_only_warning = operation_error is None and cleanup_error is not None
        error_parts = []
        if operation_error is not None:
            error_parts.append(str(operation_error))
        if operation_error is not None and cleanup_error is not None:
            error_parts.append(f"设备残留清理失败: {cleanup_error}")
        finished_at = _utc_now()
        _update_record(
            task_id,
            record_id,
            status="warning" if cleanup_only_warning else "failed",
            progress=100,
            current_step=(
                "下载完成，设备残留待清理"
                if operation_error is None
                else (
                    "下载失败，设备残留待清理"
                    if cleanup_error is not None
                    else "下载失败，设备残留已清理"
                )
            ),
            archive_path=str(final_path) if final_path and final_path.is_file() else None,
            archive_name=archive_name if final_path and final_path.is_file() else None,
            archive_size=final_path.stat().st_size if final_path and final_path.is_file() else 0,
            file_available=bool(final_path and final_path.is_file()),
            file_deleted_at=None,
            completed_steps=total_steps if operation_error is None else completed_steps,
            downloaded_at=downloaded_at,
            error=_truncate_command_output("\n".join(error_parts)) or None,
            finished_at=finished_at,
            cleanup_status="pending" if cleanup_error is not None else "success",
            cleanup_attempts=cleanup_attempts,
            cleanup_error=_truncate_command_output(str(cleanup_error)) if cleanup_error else None,
            cleanup_finished_at=None if cleanup_error is not None else finished_at,
            cleanup_only_failure=cleanup_only_warning,
        )
        if cleanup_error is not None:
            try:
                _schedule_pending_cleanup(_get_download_record(record_id), immediate=False)
            except Exception as schedule_exc:
                logger.warning(
                    "Unable to schedule pending robot log cleanup for %s: %s",
                    robot_ip,
                    schedule_exc,
                )
        return

    assert final_path is not None and archive_name is not None and downloaded_at is not None
    _update_record(
        task_id,
        record_id,
        status="success",
        progress=100,
        current_step="下载完成，设备残留已清理",
        completed_steps=total_steps,
        archive_path=str(final_path),
        archive_name=archive_name,
        archive_size=final_path.stat().st_size,
        file_available=True,
        file_deleted_at=None,
        downloaded_at=downloaded_at,
        finished_at=downloaded_at,
        error=None,
        cleanup_status="success",
        cleanup_attempts=cleanup_attempts,
        cleanup_error=None,
        cleanup_finished_at=_utc_now(),
        cleanup_only_failure=False,
    )


def _run_batch(
    task_id: str,
    devices: list[dict[str, str]],
    folder_keys: list[str],
    concurrency: int,
) -> None:
    _set_task_status(task_id, "running")
    task = _task_snapshot(task_id)
    if task is None:
        return
    records_by_ip = {record["robot_ip"]: record for record in task["devices"]}
    futures: list[Future[None]] = []
    with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix=f"robot-log-{task_id[:6]}") as executor:
        for device in devices:
            futures.append(executor.submit(_download_device, task_id, records_by_ip[device["ip"]], folder_keys))
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                logger.error("Unhandled robot log worker error: %s", exc, exc_info=True)

    final_task = _task_snapshot(task_id)
    failed = int(final_task.get("failed_devices") or 0) if final_task else len(devices)
    warning = int(final_task.get("warning_devices") or 0) if final_task else 0
    final_status = (
        "completed_with_errors"
        if failed
        else ("completed_with_warnings" if warning else "completed")
    )
    _set_task_status(task_id, final_status, finished=True)


def _get_download_record(record_id: str) -> dict[str, Any]:
    record = _get_collection().find_one({"_id": str(record_id).strip()})
    if record is None:
        raise KeyError(record_id)
    return record


def resolve_server_log_download(record_id: str) -> tuple[Path, str]:
    record = _get_download_record(record_id)
    archive_path = _resolve_record_archive_path(record)
    if record.get("file_deleted_at") or not archive_path.is_file():
        raise FileNotFoundError("服务器 Log 文件不存在或已删除")
    filename = str(record.get("archive_name") or archive_path.name)
    return archive_path, filename


def delete_server_log(record_id: str) -> dict[str, Any]:
    record = _get_download_record(record_id)
    archive_path = _resolve_record_archive_path(record)
    already_deleted = bool(record.get("file_deleted_at")) or not archive_path.exists()
    if archive_path.exists():
        if not archive_path.is_file():
            raise ValueError("服务器 Log 路径不是文件")
        archive_path.unlink()

    server_directory = str(record.get("server_directory") or "").strip()
    if server_directory:
        try:
            directory = Path(server_directory).resolve()
            download_root = Path(setting.ROBOT_LOG_DOWNLOAD_DIR).resolve()
            if download_root in directory.parents:
                directory.rmdir()
        except OSError:
            pass

    deleted_at = _utc_now()
    _update_record(
        str(record.get("task_id") or ""),
        str(record["_id"]),
        file_available=False,
        file_deleted_at=deleted_at,
    )
    return {
        "success": True,
        "record_id": str(record["_id"]),
        "already_deleted": already_deleted,
        "deleted_path": str(archive_path),
        "file_deleted_at": deleted_at.isoformat(),
    }


def shutdown_diagnostic_log_service() -> None:
    _CLEANUP_STOP_EVENT.set()
    _COORDINATOR_EXECUTOR.shutdown(wait=False, cancel_futures=True)
    _CLEANUP_EXECUTOR.shutdown(wait=False, cancel_futures=True)
