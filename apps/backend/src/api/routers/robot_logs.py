from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from api.models import RobotLogDownloadRequest
from modules.robots import diagnostic_logs as diagnostic_log_service


router = APIRouter()

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
):
    try:
        return await run_in_threadpool(
            diagnostic_log_service.list_download_records,
            page=page,
            page_size=page_size,
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
