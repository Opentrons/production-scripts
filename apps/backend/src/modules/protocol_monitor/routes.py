from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from modules.protocol_monitor import livestream, service
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


def _raise_livestream_error(exc: Exception) -> None:
    if isinstance(exc, (KeyError, ValueError)):
        _raise_service_error(exc)
    if isinstance(exc, livestream.LivestreamUpstreamError):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    raise HTTPException(status_code=503, detail="摄像头流暂时不可用") from exc


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


@router.post("/rooms/{room_id}/devices/{device_id}/livestream/enable")
async def enable_device_livestream(room_id: str, device_id: str):
    try:
        return await run_in_threadpool(livestream.enable, room_id, device_id)
    except Exception as exc:
        _raise_livestream_error(exc)


@router.post("/rooms/{room_id}/devices/{device_id}/livestream/{lease_id}/release")
async def release_device_livestream(room_id: str, device_id: str, lease_id: str):
    try:
        return await run_in_threadpool(livestream.release, room_id, device_id, lease_id)
    except Exception as exc:
        _raise_livestream_error(exc)


@router.get("/rooms/{room_id}/devices/{device_id}/livestream/{asset_path:path}")
async def proxy_device_livestream(
    room_id: str,
    device_id: str,
    asset_path: str,
    request: Request,
):
    try:
        lease_id = request.query_params.get("lease_id")
        livestream.touch(room_id, device_id, lease_id)
        asset = await run_in_threadpool(
            livestream.open_asset,
            room_id,
            device_id,
            asset_path,
            range_header=request.headers.get("Range"),
        )
        content_type = asset.response.headers.get("Content-Type") or "application/octet-stream"
        if asset.is_playlist:
            content = await run_in_threadpool(lambda: asset.response.content.decode("utf-8"))
            asset.response.close()
            proxy_base = request.url.path.rsplit("/livestream/", 1)[0] + "/livestream"
            rewritten = livestream.rewrite_playlist(content, asset, proxy_base, lease_id)
            return Response(
                content=rewritten,
                media_type="application/vnd.apple.mpegurl",
                headers={"Cache-Control": "no-store"},
            )

        response_headers = {
            key: value
            for key, value in {
                "Accept-Ranges": asset.response.headers.get("Accept-Ranges"),
                "Content-Length": asset.response.headers.get("Content-Length"),
                "Content-Range": asset.response.headers.get("Content-Range"),
                "Cache-Control": asset.response.headers.get("Cache-Control"),
            }.items()
            if value
        }
        return StreamingResponse(
            livestream.iter_asset_content(asset),
            status_code=asset.response.status_code,
            media_type=content_type,
            headers=response_headers,
        )
    except Exception as exc:
        _raise_livestream_error(exc)


@router.post("/rooms/{room_id}/status", response_model=ProtocolMonitorStatusResponse)
async def refresh_room_status(room_id: str):
    try:
        return await service.refresh_room_status(room_id)
    except Exception as exc:
        _raise_service_error(exc)
