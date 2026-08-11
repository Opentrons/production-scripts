from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ProtocolMonitorStatus = Literal["idle", "offline", "running"]


class ProtocolMonitorDevice(BaseModel):
    id: str
    name: str
    description: str = ""
    ip: str
    port: int = 31950
    created_at: str
    updated_at: str


class ProtocolMonitorDeviceStatus(BaseModel):
    device_id: str
    status: ProtocolMonitorStatus
    app_version: str | None = None
    run_status: str | None = None
    run_id: str | None = None
    protocol_id: str | None = None
    protocol_name: str | None = None
    checked_at: str
    error: str | None = None


class ProtocolMonitorRoom(BaseModel):
    id: str
    name: str
    devices: list[ProtocolMonitorDevice] = Field(default_factory=list)
    created_at: str
    updated_at: str


class ProtocolMonitorRoomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class ProtocolMonitorRoomUpdate(ProtocolMonitorRoomCreate):
    pass


class ProtocolMonitorDeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=300)
    ip: str = Field(min_length=1, max_length=255)
    port: int = Field(default=31950, ge=1, le=65535)


class ProtocolMonitorDeviceUpdate(ProtocolMonitorDeviceCreate):
    pass


class ProtocolMonitorRoomsResponse(BaseModel):
    rooms: list[ProtocolMonitorRoom] = Field(default_factory=list)
    storage: Literal["mongodb", "sqlite"]


class ProtocolMonitorStatusResponse(BaseModel):
    room_id: str
    statuses: list[ProtocolMonitorDeviceStatus] = Field(default_factory=list)
    checked_at: str
