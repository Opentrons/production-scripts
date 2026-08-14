from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import ipaddress
from threading import RLock
from typing import Any
from uuid import uuid4

from pymongo.errors import DuplicateKeyError

import core.config as setting
from core.database import mongodb
from modules.protocol_monitor.models import (
    ProtocolMonitorDeviceCreate,
    ProtocolMonitorDeviceStatus,
    ProtocolMonitorDeviceUpdate,
    ProtocolMonitorRoom,
    ProtocolMonitorRoomCreate,
    ProtocolMonitorRoomUpdate,
    ProtocolMonitorRoomsResponse,
    ProtocolMonitorStatusResponse,
)
from modules.robots.api_client.client import OpentronsHttpClient


ACTIVE_RUN_STATUSES = {
    "running",
    "paused",
    "blocked-by-open-door",
    "stop-requested",
    "finishing",
    "awaiting-recovery",
    "awaiting-recovery-paused",
    "awaiting-recovery-blocked-by-open-door",
}

_LOCK = RLock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _get_collection():
    if setting.use_sqlite_persistence():
        from core.sqlite_store import get_platform_store

        return get_platform_store()[setting.PROTOCOL_MONITOR_ROOM_COLLECTION]
    if mongodb.client is None and not mongodb.connect():
        raise RuntimeError("MongoDB 连接失败，无法加载 Protocol 监控配置")
    return mongodb.get_database(setting.MESSAGE_COLLECTION)[setting.PROTOCOL_MONITOR_ROOM_COLLECTION]


def _storage_label() -> str:
    return "sqlite" if setting.use_sqlite_persistence() else "mongodb"


def _normalize_name(value: str, field: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field}不能为空")
    if len(normalized) > 80:
        raise ValueError(f"{field}不能超过 80 个字符")
    return normalized


def _normalize_description(value: str) -> str:
    normalized = str(value or "").strip()
    if len(normalized) > 300:
        raise ValueError("设备描述不能超过 300 个字符")
    return normalized


def _normalize_ip(value: str) -> str:
    normalized = str(value or "").strip()
    try:
        parsed = ipaddress.ip_address(normalized)
    except ValueError as exc:
        raise ValueError("设备 IP 地址无效") from exc
    if parsed.version != 4:
        raise ValueError("当前仅支持 IPv4 设备")
    return str(parsed)


def _serialize_room(document: dict[str, Any]) -> ProtocolMonitorRoom:
    payload = deepcopy(document)
    payload["id"] = str(payload.get("id") or payload.get("_id") or "")
    payload.pop("_id", None)
    payload.pop("name_key", None)
    return ProtocolMonitorRoom.model_validate(payload)


def _find_room_document(room_id: str) -> dict[str, Any]:
    document = _get_collection().find_one({"_id": room_id})
    if not document:
        raise KeyError("房间不存在")
    return document


def get_device(room_id: str, device_id: str) -> dict[str, Any]:
    document = _find_room_document(room_id)
    device = next(
        (item for item in document.get("devices") or [] if item.get("id") == device_id),
        None,
    )
    if not isinstance(device, dict):
        raise KeyError("设备不存在")
    return deepcopy(device)


def list_rooms() -> ProtocolMonitorRoomsResponse:
    collection = _get_collection()
    collection.create_index("name_key", unique=True)
    documents = list(collection.find({}).sort([("created_at", 1), ("name", 1)]))
    return ProtocolMonitorRoomsResponse(
        rooms=[_serialize_room(document) for document in documents],
        storage=_storage_label(),
    )


def create_room(payload: ProtocolMonitorRoomCreate) -> ProtocolMonitorRoom:
    name = _normalize_name(payload.name, "房间名称")
    now = _utc_now()
    room_id = _new_id("room")
    document = {
        "_id": room_id,
        "id": room_id,
        "name": name,
        "name_key": name.casefold(),
        "devices": [],
        "created_at": now,
        "updated_at": now,
    }
    try:
        with _LOCK:
            collection = _get_collection()
            collection.create_index("name_key", unique=True)
            collection.insert_one(document)
    except DuplicateKeyError as exc:
        raise ValueError("房间名称已存在") from exc
    return _serialize_room(document)


def update_room(room_id: str, payload: ProtocolMonitorRoomUpdate) -> ProtocolMonitorRoom:
    name = _normalize_name(payload.name, "房间名称")
    with _LOCK:
        collection = _get_collection()
        collection.create_index("name_key", unique=True)
        if not collection.find_one({"_id": room_id}):
            raise KeyError("房间不存在")
        try:
            collection.update_one(
                {"_id": room_id},
                {"$set": {"name": name, "name_key": name.casefold(), "updated_at": _utc_now()}},
            )
        except DuplicateKeyError as exc:
            raise ValueError("房间名称已存在") from exc
        updated = collection.find_one({"_id": room_id}) or {}
    return _serialize_room(updated)


def delete_room(room_id: str) -> None:
    with _LOCK:
        result = _get_collection().delete_one({"_id": room_id})
    if not result.deleted_count:
        raise KeyError("房间不存在")


def _device_payload(payload: ProtocolMonitorDeviceCreate | ProtocolMonitorDeviceUpdate) -> dict[str, Any]:
    return {
        "name": _normalize_name(payload.name, "设备名称"),
        "description": _normalize_description(payload.description),
        "ip": _normalize_ip(payload.ip),
        "port": int(payload.port),
    }


def add_device(room_id: str, payload: ProtocolMonitorDeviceCreate) -> ProtocolMonitorRoom:
    device_data = _device_payload(payload)
    with _LOCK:
        collection = _get_collection()
        document = _find_room_document(room_id)
        devices = list(document.get("devices") or [])
        if any(
            item.get("ip") == device_data["ip"] and int(item.get("port", 31950)) == device_data["port"]
            for item in devices
        ):
            raise ValueError("该设备已在当前房间中")
        now = _utc_now()
        device_id = _new_id("device")
        devices.append(
            {
                "id": device_id,
                **device_data,
                "created_at": now,
                "updated_at": now,
            }
        )
        collection.update_one(
            {"_id": room_id},
            {"$set": {"devices": devices, "updated_at": now}},
        )
        updated = collection.find_one({"_id": room_id}) or {}
    return _serialize_room(updated)


def update_device(
    room_id: str,
    device_id: str,
    payload: ProtocolMonitorDeviceUpdate,
) -> ProtocolMonitorRoom:
    device_data = _device_payload(payload)
    with _LOCK:
        collection = _get_collection()
        document = _find_room_document(room_id)
        devices = list(document.get("devices") or [])
        target = next((item for item in devices if item.get("id") == device_id), None)
        if target is None:
            raise KeyError("设备不存在")
        if any(
            item.get("id") != device_id
            and item.get("ip") == device_data["ip"]
            and int(item.get("port", 31950)) == device_data["port"]
            for item in devices
        ):
            raise ValueError("该设备已在当前房间中")
        target.update({**device_data, "updated_at": _utc_now()})
        now = _utc_now()
        collection.update_one(
            {"_id": room_id},
            {"$set": {"devices": devices, "updated_at": now}},
        )
        updated = collection.find_one({"_id": room_id}) or {}
    return _serialize_room(updated)


def delete_device(room_id: str, device_id: str) -> ProtocolMonitorRoom:
    with _LOCK:
        collection = _get_collection()
        document = _find_room_document(room_id)
        devices = list(document.get("devices") or [])
        remaining = [item for item in devices if item.get("id") != device_id]
        if len(remaining) == len(devices):
            raise KeyError("设备不存在")
        collection.update_one(
            {"_id": room_id},
            {"$set": {"devices": remaining, "updated_at": _utc_now()}},
        )
        updated = collection.find_one({"_id": room_id}) or {}
    return _serialize_room(updated)


def _simulated_device_status(device: dict[str, Any]) -> ProtocolMonitorDeviceStatus:
    from modules.system.simulating_seed import find_fake_robot

    checked_at = _utc_now()
    robot = find_fake_robot(str(device["ip"]), int(device.get("port", 31950)))
    if not robot or robot.get("service_status") != "normal":
        return ProtocolMonitorDeviceStatus(
            device_id=str(device["id"]),
            status="offline",
            app_version=str(
                (robot or {}).get("api_version") or (robot or {}).get("version") or ""
            )
            or None,
            checked_at=checked_at,
            error=str((robot or {}).get("error") or "设备离线"),
        )
    if str(device["ip"]).endswith(".12"):
        return ProtocolMonitorDeviceStatus(
            device_id=str(device["id"]),
            status="running",
            app_version=str(robot.get("api_version") or robot.get("version") or "")
            or None,
            run_status="running",
            run_id="sim-run-001",
            protocol_id="sim-protocol-001",
            protocol_name="vacuum_manifold_stress_test.py",
            checked_at=checked_at,
        )
    return ProtocolMonitorDeviceStatus(
        device_id=str(device["id"]),
        status="idle",
        app_version=str(robot.get("api_version") or robot.get("version") or "") or None,
        checked_at=checked_at,
    )


def _app_version(health: Any) -> str | None:
    payload = health.get("data") if isinstance(health, dict) and "data" in health else health
    if not isinstance(payload, dict):
        return None
    for key in ("api_version", "server_version", "version", "robot_server_version"):
        value = payload.get(key)
        if isinstance(value, (str, int, float)) and str(value).strip():
            return str(value).strip()
    return None


def _protocol_display_name(protocol: Any) -> str | None:
    if not isinstance(protocol, dict):
        return None
    metadata = protocol.get("metadata")
    if isinstance(metadata, dict):
        for key in ("protocolName", "name", "title"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    files = protocol.get("files")
    if isinstance(files, list) and files:
        first_file = files[0]
        if isinstance(first_file, dict):
            value = first_file.get("name")
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def check_device_status(device: dict[str, Any]) -> ProtocolMonitorDeviceStatus:
    if setting.use_sqlite_persistence():
        return _simulated_device_status(device)

    checked_at = _utc_now()
    client = OpentronsHttpClient(
        str(device["ip"]),
        int(device.get("port", 31950)),
        timeout=4,
    )
    try:
        app_version = _app_version(client.get_health())
    except Exception as exc:
        return ProtocolMonitorDeviceStatus(
            device_id=str(device["id"]),
            status="offline",
            checked_at=checked_at,
            error=str(exc),
        )

    try:
        runs = client.list_runs()
    except Exception as exc:
        return ProtocolMonitorDeviceStatus(
            device_id=str(device["id"]),
            status="offline",
            app_version=app_version,
            checked_at=checked_at,
            error=str(exc),
        )

    active_run = next(
        (
            run
            for run in runs
            if isinstance(run, dict)
            and str(run.get("status") or "").casefold() in ACTIVE_RUN_STATUSES
            and bool(run.get("current", True))
        ),
        None,
    )
    if active_run is None:
        return ProtocolMonitorDeviceStatus(
            device_id=str(device["id"]),
            status="idle",
            app_version=app_version,
            checked_at=checked_at,
        )
    protocol_id = str(active_run.get("protocolId") or "") or None
    protocol_name = _protocol_display_name(active_run)
    if protocol_id and not protocol_name:
        try:
            protocol = next(
                (
                    item
                    for item in client.list_protocols()
                    if isinstance(item, dict) and str(item.get("id") or "") == protocol_id
                ),
                None,
            )
            protocol_name = _protocol_display_name(protocol)
        except Exception:
            protocol_name = None
    return ProtocolMonitorDeviceStatus(
        device_id=str(device["id"]),
        status="running",
        app_version=app_version,
        run_status=str(active_run.get("status") or "running"),
        run_id=str(active_run.get("id") or "") or None,
        protocol_id=protocol_id,
        protocol_name=protocol_name,
        checked_at=checked_at,
    )


async def refresh_room_status(room_id: str) -> ProtocolMonitorStatusResponse:
    room = _find_room_document(room_id)
    devices = list(room.get("devices") or [])
    statuses = await asyncio.gather(
        *(asyncio.to_thread(check_device_status, device) for device in devices)
    )
    return ProtocolMonitorStatusResponse(
        room_id=room_id,
        statuses=list(statuses),
        checked_at=_utc_now(),
    )
