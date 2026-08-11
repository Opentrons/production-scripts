from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.concurrency import run_in_threadpool

from modules.protocol_monitor import service
from modules.protocol_monitor.models import (
    ProtocolMonitorDeviceCreate,
    ProtocolMonitorDeviceUpdate,
    ProtocolMonitorRoom,
    ProtocolMonitorRoomCreate,
    ProtocolMonitorRoomUpdate,
    ProtocolMonitorRoomsResponse,
    ProtocolMonitorStatusResponse,
)


router = APIRouter(prefix="/protocol-monitor", tags=["protocol-monitor"])


def _raise_service_error(exc: Exception) -> None:
    if isinstance(exc, KeyError):
        raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/rooms", response_model=ProtocolMonitorRoomsResponse)
async def list_rooms():
    try:
        return await run_in_threadpool(service.list_rooms)
    except Exception as exc:
        _raise_service_error(exc)


@router.post("/rooms", response_model=ProtocolMonitorRoom, status_code=status.HTTP_201_CREATED)
async def create_room(payload: ProtocolMonitorRoomCreate):
    try:
        return await run_in_threadpool(service.create_room, payload)
    except Exception as exc:
        _raise_service_error(exc)


@router.put("/rooms/{room_id}", response_model=ProtocolMonitorRoom)
async def update_room(room_id: str, payload: ProtocolMonitorRoomUpdate):
    try:
        return await run_in_threadpool(service.update_room, room_id, payload)
    except Exception as exc:
        _raise_service_error(exc)


@router.delete("/rooms/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room(room_id: str):
    try:
        await run_in_threadpool(service.delete_room, room_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as exc:
        _raise_service_error(exc)


@router.post("/rooms/{room_id}/devices", response_model=ProtocolMonitorRoom)
async def add_device(room_id: str, payload: ProtocolMonitorDeviceCreate):
    try:
        return await run_in_threadpool(service.add_device, room_id, payload)
    except Exception as exc:
        _raise_service_error(exc)


@router.put("/rooms/{room_id}/devices/{device_id}", response_model=ProtocolMonitorRoom)
async def update_device(
    room_id: str,
    device_id: str,
    payload: ProtocolMonitorDeviceUpdate,
):
    try:
        return await run_in_threadpool(service.update_device, room_id, device_id, payload)
    except Exception as exc:
        _raise_service_error(exc)


@router.delete("/rooms/{room_id}/devices/{device_id}", response_model=ProtocolMonitorRoom)
async def delete_device(room_id: str, device_id: str):
    try:
        return await run_in_threadpool(service.delete_device, room_id, device_id)
    except Exception as exc:
        _raise_service_error(exc)


@router.post("/rooms/{room_id}/status", response_model=ProtocolMonitorStatusResponse)
async def refresh_room_status(room_id: str):
    try:
        return await service.refresh_room_status(room_id)
    except Exception as exc:
        _raise_service_error(exc)
