from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response

import core.config as setting
from api.models import RobotLogDownloadRequest
from modules.robots import app_log_analysis as app_log_analysis_service
from modules.robots import app_logs as app_logs_service
from modules.robots import diagnostic_logs as diagnostic_log_service
from modules.robots.api_client.client import OpentronsApiError


router = APIRouter()


@router.post("/robots/log-analyses/upload")
async def upload_robot_app_log_for_analysis(
    zip_file: UploadFile = File(...),
    robot_ip: str = Form("manual"),
    device_name: str | None = Form(None),
):
    """Analyze a user-provided App Log zip and persist a new analysis record."""
    archive_name = zip_file.filename or "uploaded-app-logs.zip"
    if not archive_name.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail={"message": "请上传 ZIP 格式的 App Log 文件"})
    try:
        zip_bytes = await zip_file.read()
        if not zip_bytes:
            raise ValueError("上传的 ZIP 文件为空")
        record = await run_in_threadpool(
            app_log_analysis_service.analyze_and_store_app_log_zip,
            zip_bytes,
            robot_ip=robot_ip.strip() or "manual",
            archive_name=archive_name,
            device_name=device_name.strip() if device_name else None,
        )
        return record
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail={"message": str(exc)}) from exc

@router.get("/robots/{ip}/logs/app-download")
async def download_robot_app_logs(
    ip: str,
    port: int = setting.ROBOT_HEALTH_PORT,
    analyze: bool = Query(False, description="Download 后分析 App Log 并写入 MongoDB"),
    device_name: str | None = Query(None, max_length=120),
):
    """Download the robot's App log bundle as a zip.

    When ``analyze=true``, the same zip is analyzed with ``analyze_logs`` and the
    compact result is stored in ``robot_app_log_analysis_records``. Analysis
    failures do not block the zip download.
    """
    try:
        zip_bytes, filename = await run_in_threadpool(
            app_logs_service.collect_opentrons_app_logs, ip, port
        )
    except OpentronsApiError as exc:
        raise HTTPException(status_code=502, detail={"message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"message": str(exc)}) from exc

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    if analyze:
        try:
            record = await run_in_threadpool(
                app_log_analysis_service.analyze_and_store_app_log_zip,
                zip_bytes,
                robot_ip=ip,
                archive_name=filename,
                device_name=device_name,
            )
            headers["X-App-Log-Analysis-Id"] = str(record.get("_id") or "")
            headers["X-App-Log-Analysis-Status"] = str(record.get("status") or "")
        except Exception:
            # Download must still succeed even if Mongo/analysis is unavailable.
            headers["X-App-Log-Analysis-Status"] = "failed"

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers=headers,
    )


@router.get("/robots/log-analyses/records")
async def list_robot_app_log_analysis_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    robot_ip: str | None = Query(None),
):
    try:
        return await run_in_threadpool(
            app_log_analysis_service.list_analysis_records,
            page=page,
            page_size=page_size,
            robot_ip=robot_ip,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail={"message": str(exc)}) from exc


@router.get("/robots/log-analyses/records/{record_id}")
async def get_robot_app_log_analysis_record(record_id: str):
    try:
        return await run_in_threadpool(app_log_analysis_service.get_analysis_record, record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"message": "App Log 分析记录不存在"}) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail={"message": str(exc)}) from exc


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
