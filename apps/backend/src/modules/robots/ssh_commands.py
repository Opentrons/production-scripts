from __future__ import annotations

import ipaddress
import shlex
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import uuid4

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

import core.config as setting
from core.logging import get_logger

logger = get_logger(__name__)
from core.database import mongodb
from modules.robots.files.ssh_client import OpentronsSshClient


MAX_OUTPUT_CHARS = 200_000
_INDEX_LOCK = threading.Lock()
_INDEX_READY = False

BUILTIN_COMMANDS: tuple[dict[str, str], ...] = (
    {
        "id": "builtin-date",
        "name": "查看系统时间",
        "command": "date",
        "description": "显示设备当前日期、时间和时区",
        "source": "builtin",
        "tag": "general",
    },
    {
        "id": "builtin-hostname",
        "name": "查看主机名",
        "command": "hostname",
        "description": "显示设备主机名",
        "source": "builtin",
        "tag": "general",
    },
    {
        "id": "builtin-uptime",
        "name": "查看运行时间",
        "command": "uptime",
        "description": "显示设备运行时间和系统负载",
        "source": "builtin",
        "tag": "general",
    },
    {
        "id": "builtin-disk",
        "name": "查看磁盘空间",
        "command": "df -h",
        "description": "显示文件系统磁盘使用情况",
        "source": "builtin",
        "tag": "general",
    },
    {
        "id": "builtin-memory",
        "name": "查看内存",
        "command": "free -h",
        "description": "显示设备内存使用情况",
        "source": "builtin",
        "tag": "general",
    },
    {
        "id": "builtin-robot-server",
        "name": "查看 Robot Server 状态",
        "command": "systemctl status opentrons-robot-server --no-pager",
        "description": "显示 opentrons-robot-server 服务状态",
        "source": "builtin",
        "tag": "general",
    },
    {
        "id": "builtin-sync-server-time",
        "name": "同步服务器时间",
        "command": (
            "mount -o remount,rw / && timedatectl set-ntp false && "
            "timedatectl set-timezone Asia/Shanghai && "
            "timedatectl set-time \"$(date --date=\"@$DATE_EPOCH\" '+%Y-%m-%d %H:%M:%S')\" && "
            "date"
        ),
        "description": "将设备时区设为 Asia/Shanghai，同步服务器时间后读取设备 date",
        "source": "builtin",
        "tag": "risk",
    },
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_server_environment() -> dict[str, str]:
    now = datetime.now().astimezone()
    return {
        "DATE": now.strftime("%Y-%m-%d %H:%M:%S"),
        "DATE_EPOCH": str(int(now.timestamp())),
        "DATE_TIMEZONE": now.strftime("%Z%z") or str(now.tzinfo or ""),
    }


def _inject_server_environment(command: str, environment: dict[str, str]) -> str:
    assignments = "; ".join(
        f"{name}={shlex.quote(value)}"
        for name, value in environment.items()
    )
    exported_names = " ".join(environment)
    return f"{assignments}; export {exported_names}; {command}"


def _get_collection():
    global _INDEX_READY
    if mongodb.client is None and not mongodb.connect():
        raise RuntimeError("MongoDB 连接失败，无法加载 SSH 自定义命令")
    collection = mongodb.get_database(setting.MESSAGE_COLLECTION)[setting.ROBOT_SSH_COMMAND_COLLECTION]
    if not _INDEX_READY:
        with _INDEX_LOCK:
            if not _INDEX_READY:
                collection.create_index("name_key", unique=True)
                collection.create_index([("updated_at", -1)])
                _INDEX_READY = True
    return collection


def _normalize_command_fields(
    name: str,
    command: str,
    description: str = "",
    tag: str = "general",
) -> dict[str, str]:
    normalized_name = str(name or "").strip()
    normalized_command = str(command or "").strip()
    normalized_description = str(description or "").strip()
    normalized_tag = str(tag or "general").strip().lower()
    if not normalized_name:
        raise ValueError("命令名称不能为空")
    if len(normalized_name) > 80:
        raise ValueError("命令名称不能超过 80 个字符")
    if not normalized_command:
        raise ValueError("SSH 命令不能为空")
    if "\x00" in normalized_command:
        raise ValueError("SSH 命令不能包含空字符")
    if len(normalized_command) > 20000:
        raise ValueError("SSH 命令不能超过 20000 个字符")
    if len(normalized_description) > 500:
        raise ValueError("命令说明不能超过 500 个字符")
    if normalized_tag not in {"general", "risk"}:
        raise ValueError("命令属性只能是 general 或 risk")
    return {
        "name": normalized_name,
        "name_key": normalized_name.casefold(),
        "command": normalized_command,
        "description": normalized_description,
        "tag": normalized_tag,
    }


def _serialize_custom_command(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(document.get("_id") or ""),
        "name": str(document.get("name") or ""),
        "command": str(document.get("command") or ""),
        "description": str(document.get("description") or ""),
        "source": "custom",
        "tag": "risk" if document.get("tag") == "risk" else "general",
        "created_at": document.get("created_at"),
        "updated_at": document.get("updated_at"),
    }


def list_commands() -> dict[str, Any]:
    response: dict[str, Any] = {
        "builtin_commands": [dict(item) for item in BUILTIN_COMMANDS],
        "custom_commands": [],
        "database_available": True,
        "error": None,
    }
    try:
        documents = _get_collection().find({}).sort([("updated_at", -1), ("name", 1)])
        response["custom_commands"] = [_serialize_custom_command(document) for document in documents]
    except Exception as exc:
        logger.warning("Failed to load SSH custom commands: %s", exc)
        response["database_available"] = False
        response["error"] = str(exc)
    return response


def create_command(*, name: str, command: str, description: str = "", tag: str = "general") -> dict[str, Any]:
    fields = _normalize_command_fields(name, command, description, tag)
    now = _utc_now()
    document = {
        "_id": uuid4().hex,
        **fields,
        "created_at": now,
        "updated_at": now,
    }
    try:
        _get_collection().insert_one(document)
    except DuplicateKeyError as exc:
        raise ValueError(f"自定义命令名称已存在: {fields['name']}") from exc
    return _serialize_custom_command(document)


def update_command(
    command_id: str,
    *,
    name: str,
    command: str,
    description: str = "",
    tag: str = "general",
) -> dict[str, Any]:
    normalized_id = str(command_id or "").strip()
    if not normalized_id:
        raise KeyError("SSH 自定义命令不存在")
    fields = _normalize_command_fields(name, command, description, tag)
    fields["updated_at"] = _utc_now()
    try:
        document = _get_collection().find_one_and_update(
            {"_id": normalized_id},
            {"$set": fields},
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError as exc:
        raise ValueError(f"自定义命令名称已存在: {fields['name']}") from exc
    if document is None:
        raise KeyError("SSH 自定义命令不存在")
    return _serialize_custom_command(document)


def delete_command(command_id: str) -> dict[str, Any]:
    normalized_id = str(command_id or "").strip()
    result = _get_collection().delete_one({"_id": normalized_id})
    if not result.deleted_count:
        raise KeyError("SSH 自定义命令不存在")
    return {"success": True, "id": normalized_id}


def _truncate_output(value: str) -> tuple[str, bool]:
    if len(value) <= MAX_OUTPUT_CHARS:
        return value, False
    return value[:MAX_OUTPUT_CHARS] + "\n\n[输出过长，已截断]", True


def execute_command(
    *,
    ip: str,
    command: str,
    timeout: int = 30,
    server_environment: dict[str, str] | None = None,
) -> dict[str, Any]:
    normalized_ip = str(ip or "").strip()
    try:
        ipaddress.ip_address(normalized_ip)
    except ValueError as exc:
        raise ValueError(f"无效设备 IP: {normalized_ip or '空'}") from exc

    normalized_command = str(command or "").strip()
    if not normalized_command:
        raise ValueError("SSH 命令不能为空")
    if "\x00" in normalized_command:
        raise ValueError("SSH 命令不能包含空字符")
    if len(normalized_command) > 20000:
        raise ValueError("SSH 命令不能超过 20000 个字符")
    normalized_timeout = max(1, min(int(timeout), 300))
    environment = dict(server_environment) if server_environment is not None else _build_server_environment()
    remote_command = _inject_server_environment(normalized_command, environment)

    started_at = _utc_now()
    started = perf_counter()
    exit_code, stdout, stderr = OpentronsSshClient(normalized_ip).exec_command(
        remote_command,
        timeout=normalized_timeout,
    )
    duration_ms = round((perf_counter() - started) * 1000)
    stdout, stdout_truncated = _truncate_output(stdout)
    stderr, stderr_truncated = _truncate_output(stderr)
    return {
        "ip": normalized_ip,
        "command": normalized_command,
        "environment": environment,
        "success": exit_code == 0,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "output_truncated": stdout_truncated or stderr_truncated,
        "started_at": started_at,
        "finished_at": _utc_now(),
        "duration_ms": duration_ms,
    }


def execute_commands_batch(
    *,
    ips: list[str],
    command: str,
    timeout: int = 30,
    concurrency: int = 8,
) -> dict[str, Any]:
    normalized_ips: list[str] = []
    seen_ips: set[str] = set()
    for raw_ip in ips:
        normalized_ip = str(raw_ip or "").strip()
        try:
            ipaddress.ip_address(normalized_ip)
        except ValueError as exc:
            raise ValueError(f"无效设备 IP: {normalized_ip or '空'}") from exc
        if normalized_ip not in seen_ips:
            seen_ips.add(normalized_ip)
            normalized_ips.append(normalized_ip)
    if not normalized_ips:
        raise ValueError("请至少选择一台设备")

    normalized_command = str(command or "").strip()
    if not normalized_command:
        raise ValueError("SSH 命令不能为空")
    if "\x00" in normalized_command:
        raise ValueError("SSH 命令不能包含空字符")
    if len(normalized_command) > 20000:
        raise ValueError("SSH 命令不能超过 20000 个字符")

    normalized_timeout = max(1, min(int(timeout), 300))
    worker_count = max(1, min(int(concurrency), 20, len(normalized_ips)))

    def run_for_ip(ip: str) -> dict[str, Any]:
        started_at = _utc_now()
        started = perf_counter()
        environment = _build_server_environment()
        try:
            return execute_command(
                ip=ip,
                command=normalized_command,
                timeout=normalized_timeout,
                server_environment=environment,
            )
        except Exception as exc:
            return {
                "ip": ip,
                "command": normalized_command,
                "environment": environment,
                "success": False,
                "exit_code": None,
                "stdout": "",
                "stderr": "",
                "error": str(exc),
                "output_truncated": False,
                "started_at": started_at,
                "finished_at": _utc_now(),
                "duration_ms": round((perf_counter() - started) * 1000),
            }

    results_by_ip: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="ssh-batch") as executor:
        futures = {executor.submit(run_for_ip, ip): ip for ip in normalized_ips}
        for future in as_completed(futures):
            ip = futures[future]
            results_by_ip[ip] = future.result()

    results = [results_by_ip[ip] for ip in normalized_ips]
    success_count = sum(1 for result in results if result["success"])
    return {
        "results": results,
        "total": len(results),
        "success_count": success_count,
        "failed_count": len(results) - success_count,
        "concurrency": worker_count,
    }
