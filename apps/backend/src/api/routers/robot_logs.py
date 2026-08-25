from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response

import core.config as setting
from api.models import RobotLogDownloadRequest
from modules.robots import app_logs as app_logs_service
from modules.robots import diagnostic_logs as diagnostic_log_service
from modules.robots.api_client.client import OpentronsApiError


router = APIRouter()

@router.get("/robots/{ip}/logs/app-download")
async def download_robot_app_logs(ip: str, port: int = setting.ROBOT_HEALTH_PORT):
    """Download the robot's App log bundle as a zip."""
    try:
        zip_bytes, filename = await run_in_threadpool(
            app_logs_service.collect_opentrons_app_logs, ip, port
        )
    except OpentronsApiError as exc:
        raise HTTPException(status_code=502, detail={"message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/robots/log-downloads/folders")
async def list_robot_log_download_folders():
    return diagnostic_log_service.list_folder_options()


@router.post("/robots/log-downloads/tasks")
async def create_robot_log_download_task(request: RobotLogDownloadRequest):
    try:
        devices = [
            device.model_dump() if hasattr(device, "model_dump") else device.dict()
            for device in request.devices
        ]
        return await run_in_threadpool(
            diagnostic_log_service.create_download_task,
            devices=devices,
            folder_keys=request.folder_keys,
            concurrency=request.concurrency,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail={"message": str(exc)}) from exc


@router.get("/robots/log-downloads/tasks/{task_id}")
async def get_robot_log_download_task(task_id: str):
    try:
        return await run_in_threadpool(diagnostic_log_service.get_download_task, task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"message": "Log 下载任务不存在"}) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail={"message": str(exc)}) from exc


@router.get("/robots/log-downloads/records")
async def list_robot_log_download_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    robot_ip: str | None = Query(None),
):
    try:
        return await run_in_threadpool(
            diagnostic_log_service.list_download_records,
            page=page,
            page_size=page_size,
            robot_ip=robot_ip,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail={"message": str(exc)}) from exc


@router.get("/robots/log-downloads/records/{record_id}/file")
async def download_robot_server_log(record_id: str):
    try:
        file_path, filename = await run_in_threadpool(
            diagnostic_log_service.resolve_server_log_download,
            record_id,
        )
        return FileResponse(
            file_path,
            media_type="application/gzip",
            filename=filename,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"message": "Log 下载记录不存在"}) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc


@router.post("/robots/log-downloads/records/{record_id}/cleanup")
async def retry_robot_log_device_cleanup(record_id: str):
    try:
        return await run_in_threadpool(diagnostic_log_service.retry_record_cleanup, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"message": "Log 下载记录不存在"}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail={"message": str(exc)}) from exc


@router.delete("/robots/log-downloads/records/{record_id}/file")
async def delete_robot_server_log(record_id: str):
    try:
        return await run_in_threadpool(diagnostic_log_service.delete_server_log, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"message": "Log 下载记录不存在"}) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
