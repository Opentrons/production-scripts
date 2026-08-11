from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from core.sqlite_store import SqliteDocumentStore
from modules.protocol_monitor import service
from modules.protocol_monitor.models import (
    ProtocolMonitorDeviceCreate,
    ProtocolMonitorDeviceUpdate,
    ProtocolMonitorRoomCreate,
    ProtocolMonitorRoomUpdate,
)


@pytest.fixture
def monitor_collection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    collection = SqliteDocumentStore(tmp_path / "monitor.sqlite3")["protocol_monitor_rooms"]
    monkeypatch.setattr(service, "_get_collection", lambda: collection)
    monkeypatch.setattr(service, "_storage_label", lambda: "sqlite")
    return collection


def test_room_and_device_crud(monitor_collection) -> None:
    room = service.create_room(ProtocolMonitorRoomCreate(name="生产一室"))
    assert room.name == "生产一室"
    assert room.devices == []

    room = service.add_device(
        room.id,
        ProtocolMonitorDeviceCreate(
            name="Flex 01",
            description="装配线主测试设备",
            ip="192.168.6.11",
            port=31950,
        ),
    )
    assert len(room.devices) == 1
    assert room.devices[0].description == "装配线主测试设备"
    device_id = room.devices[0].id

    room = service.update_device(
        room.id,
        device_id,
        ProtocolMonitorDeviceUpdate(
            name="Flex A",
            description="Protocol 回归设备",
            ip="192.168.6.12",
            port=31950,
        ),
    )
    assert room.devices[0].name == "Flex A"
    assert room.devices[0].description == "Protocol 回归设备"
    assert room.devices[0].ip == "192.168.6.12"

    room = service.update_room(room.id, ProtocolMonitorRoomUpdate(name="生产二室"))
    assert room.name == "生产二室"
    assert service.list_rooms().rooms[0].id == room.id

    room = service.delete_device(room.id, device_id)
    assert room.devices == []
    service.delete_room(room.id)
    assert service.list_rooms().rooms == []


def test_rejects_duplicate_room_and_device(monitor_collection) -> None:
    room = service.create_room(ProtocolMonitorRoomCreate(name="Room A"))
    with pytest.raises(ValueError, match="房间名称已存在"):
        service.create_room(ProtocolMonitorRoomCreate(name="room a"))

    payload = ProtocolMonitorDeviceCreate(name="Flex", ip="192.168.6.11", port=31950)
    service.add_device(room.id, payload)
    with pytest.raises(ValueError, match="已在当前房间"):
        service.add_device(room.id, payload)


def test_rejects_invalid_device_ip(monitor_collection) -> None:
    room = service.create_room(ProtocolMonitorRoomCreate(name="Room A"))
    with pytest.raises(ValueError, match="IP 地址无效"):
        service.add_device(
            room.id,
            ProtocolMonitorDeviceCreate(name="Flex", ip="not-an-ip", port=31950),
        )


def test_existing_device_without_description_is_supported(monitor_collection) -> None:
    room = service.create_room(ProtocolMonitorRoomCreate(name="Legacy Room"))
    monitor_collection.update_one(
        {"_id": room.id},
        {
            "$set": {
                "devices": [
                    {
                        "id": "legacy-device",
                        "name": "Legacy Flex",
                        "ip": "192.168.6.20",
                        "port": 31950,
                        "created_at": room.created_at,
                        "updated_at": room.updated_at,
                    }
                ]
            }
        },
    )

    loaded = service.list_rooms().rooms[0]

    assert loaded.devices[0].description == ""


def test_device_status_maps_active_run_to_running(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def list_runs(self):
            return [
                {"id": "old", "status": "succeeded", "current": False},
                {
                    "id": "run-1",
                    "status": "paused",
                    "current": True,
                    "protocolId": "protocol-1",
                },
            ]

        def get_health(self):
            return {"api_version": "8.8.1", "server_version": "8.8.0"}

        def list_protocols(self):
            return [
                {
                    "id": "protocol-1",
                    "metadata": {"protocolName": "Production verification"},
                    "files": [{"name": "production_verification.py", "role": "main"}],
                }
            ]

    monkeypatch.setattr(service.setting, "use_sqlite_persistence", lambda: False)
    monkeypatch.setattr(service, "OpentronsHttpClient", FakeClient)

    status = service.check_device_status(
        {"id": "device-1", "ip": "192.168.6.11", "port": 31950}
    )

    assert status.status == "running"
    assert status.app_version == "8.8.1"
    assert status.run_status == "paused"
    assert status.run_id == "run-1"
    assert status.protocol_id == "protocol-1"
    assert status.protocol_name == "Production verification"


def test_device_status_maps_no_active_run_to_idle(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def list_runs(self):
            return [{"id": "run-1", "status": "succeeded", "current": False}]

        def get_health(self):
            return {"version": "8.7.1"}

    monkeypatch.setattr(service.setting, "use_sqlite_persistence", lambda: False)
    monkeypatch.setattr(service, "OpentronsHttpClient", FakeClient)

    status = service.check_device_status(
        {"id": "device-1", "ip": "192.168.6.11", "port": 31950}
    )

    assert status.status == "idle"
    assert status.app_version == "8.7.1"
    assert status.run_id is None


def test_device_status_maps_request_failure_to_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def list_runs(self):
            raise ConnectionError("unreachable")

        def get_health(self):
            return {"robot_server_version": "8.6.0"}

    monkeypatch.setattr(service.setting, "use_sqlite_persistence", lambda: False)
    monkeypatch.setattr(service, "OpentronsHttpClient", FakeClient)

    status = service.check_device_status(
        {"id": "device-1", "ip": "192.168.6.11", "port": 31950}
    )

    assert status.status == "offline"
    assert status.app_version == "8.6.0"
    assert status.error == "unreachable"


def test_refresh_room_status_returns_each_device(
    monitor_collection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    room = service.create_room(ProtocolMonitorRoomCreate(name="Room A"))
    room = service.add_device(
        room.id,
        ProtocolMonitorDeviceCreate(name="Flex 1", ip="192.168.6.11", port=31950),
    )
    room = service.add_device(
        room.id,
        ProtocolMonitorDeviceCreate(name="Flex 2", ip="192.168.6.12", port=31950),
    )

    monkeypatch.setattr(service.setting, "use_sqlite_persistence", lambda: True)
    result = asyncio.run(service.refresh_room_status(room.id))

    assert [item.status for item in result.statuses] == ["idle", "running"]
    assert [item.app_version for item in result.statuses] == ["8.3.0", "8.8.0"]
    assert result.statuses[1].protocol_name == "vacuum_manifold_stress_test.py"
    assert result.room_id == room.id
