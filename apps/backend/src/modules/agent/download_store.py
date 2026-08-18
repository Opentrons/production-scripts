from __future__ import annotations

import ipaddress
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from core import config
from modules.agent import attachment_store
from modules.robots import opentrons_control


DOWNLOAD_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


class AgentDownloadError(ValueError):
    pass


class AgentDownloadNotFoundError(AgentDownloadError):
    pass


def _root() -> Path:
    return Path(config.AGENT_ATTACHMENT_DIR) / "downloads"


def _request_path(request_id: str) -> Path:
    if not DOWNLOAD_ID_PATTERN.fullmatch(str(request_id or "")):
        raise AgentDownloadNotFoundError("下载链接不存在或已过期")
    return _root() / f"{request_id}.json"


def cleanup_expired() -> None:
    root = _root()
    if not root.is_dir():
        return
    now = time.time()
    for request_path in root.glob("*.json"):
        try:
            payload = json.loads(request_path.read_text(encoding="utf-8"))
            expired = float(payload.get("expires_at_timestamp") or 0) <= now
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            expired = True
        if expired:
            request_path.unlink(missing_ok=True)


def _normalize_robot_ip(value: str) -> str:
    normalized = str(value or "").strip()
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError as exc:
        raise AgentDownloadError(f"无效设备 IP: {normalized or '空'}") from exc
    if address.version != 4:
        raise AgentDownloadError("测试数据下载仅支持 IPv4 设备")
    return str(address)


def create_robot_testing_data_request(ip: str, paths: list[str]) -> dict[str, Any]:
    owner_id = attachment_store.current_attachment_owner()
    normalized_ip = _normalize_robot_ip(ip)
    normalized_paths = opentrons_control._normalize_testing_data_paths(paths)
    if len(normalized_paths) > 500:
        raise AgentDownloadError("单次最多下载 500 个测试数据路径")

    cleanup_expired()
    root = _root()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    request_id = uuid4().hex
    request_path = _request_path(request_id)
    temporary_path = root / f".{request_id}.json.tmp"
    created_at = datetime.now(timezone.utc)
    expires_at_timestamp = created_at.timestamp() + config.AGENT_ATTACHMENT_TTL_SECONDS
    filename = f"testing-data-{normalized_ip.replace('.', '-')}.zip"
    payload = {
        "id": request_id,
        "kind": "robot_testing_data",
        "owner_id": owner_id,
        "ip": normalized_ip,
        "paths": normalized_paths,
        "filename": filename,
        "created_at": created_at.isoformat(),
        "expires_at": datetime.fromtimestamp(expires_at_timestamp, tz=timezone.utc).isoformat(),
        "expires_at_timestamp": expires_at_timestamp,
    }
    try:
        temporary_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temporary_path.chmod(0o600)
        os.replace(temporary_path, request_path)
        request_path.chmod(0o600)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        request_path.unlink(missing_ok=True)
        raise
    return {
        "download_id": request_id,
        "download_url": f"/api/agent/downloads/testing-data/{request_id}",
        "filename": filename,
        "ip": normalized_ip,
        "paths": normalized_paths,
        "selected_count": len(normalized_paths),
        "expires_at": payload["expires_at"],
    }


def resolve_robot_testing_data_request(request_id: str, owner_id: str) -> dict[str, Any]:
    cleanup_expired()
    request_path = _request_path(request_id)
    try:
        payload = json.loads(request_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AgentDownloadNotFoundError("下载链接不存在或已过期") from exc
    if not isinstance(payload, dict) or payload.get("kind") != "robot_testing_data":
        raise AgentDownloadNotFoundError("下载链接不存在或已过期")
    if payload.get("owner_id") != owner_id:
        raise AgentDownloadNotFoundError("下载链接不存在或已过期")
    if float(payload.get("expires_at_timestamp") or 0) <= time.time():
        request_path.unlink(missing_ok=True)
        raise AgentDownloadNotFoundError("下载链接不存在或已过期")
    return payload
