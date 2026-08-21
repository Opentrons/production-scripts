from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from api.models import (
    UploadDataRequest,
    UploadDataResponse,
    UploadFinishSettingResponse,
    UploadFinishSettingUpdateRequest,
    UploadRecordFailureRequest,
    UploadRecordFilterOptionsResponse,
    UploadRecordListResponse,
    UploadRecordStartRequest,
    UploadRecordStatsResponse,
)
from core.logging import get_logger
from modules.uploads import upload as upload_service
from modules.uploads import upload_records as upload_record_service
from modules.uploads import upload_settings as upload_settings_service


logger = get_logger(__name__)
router = APIRouter()
data_center_client_router = APIRouter()


@data_center_client_router.post("/upload-records/start", response_model=UploadDataResponse)
async def start_upload_record(payload: UploadRecordStartRequest):
    existing = await run_in_threadpool(
        upload_record_service.get_upload_record_by_idempotency_key,
        payload.idempotency_key,
    )
    record_id = await run_in_threadpool(
        upload_record_service.create_upload_record,
        None,
        None,
        csv_name=payload.csv_file_name,
        zip_name=payload.zip_file_name,
        source=payload.source,
        idempotency_key=payload.idempotency_key,
        csv_size=payload.csv_size,
        csv_sha256=payload.csv_sha256,
    )
    if not record_id:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Unable to create upload record",
                "success": False,
            },
        )
    return {
        "success": True,
        "record_id": record_id,
        "message": "Upload record created",
        "status": (existing or {}).get("status") or "running",
        "deduplicated": existing is not None,
    }


@data_center_client_router.post("/upload-records/{record_id}/fail", response_model=UploadDataResponse)
async def fail_upload_record(record_id: str, payload: UploadRecordFailureRequest):
    await run_in_threadpool(
        upload_record_service.mark_upload_record_failed,
        record_id,
        failure_stage=payload.failure_stage,
        failure_code=payload.failure_code,
        error=payload.message,
        error_detail=payload.detail,
    )
    return {
        "success": True,
        "record_id": record_id,
        "message": "Upload record marked as failed",
    }


@data_center_client_router.get("/upload-records/{record_id}")
async def get_upload_record_status(record_id: str):
    record = await run_in_threadpool(upload_record_service.get_upload_record, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail={"message": "Upload record not found"})
    return {
        "record_id": str(record.get("_id")),
        "status": record.get("status"),
        "job_enqueued": bool(record.get("job")),
        "progress_stage": record.get("progress_stage"),
        "progress_message": record.get("progress_message"),
        "attempt_count": record.get("attempt_count", 0),
        "max_attempts": record.get("max_attempts", 0),
        "next_retry_at": record.get("next_retry_at"),
        "upload_success": record.get("upload_success"),
        "database_success": record.get("database_success"),
        "notification_status": record.get("notification_status"),
        "failure_stage": record.get("failure_stage"),
        "failure_code": record.get("failure_code"),
        "error": record.get("error"),
        "error_detail": record.get("error_detail"),
    }


@router.get("/settings/upload/finish", response_model=UploadFinishSettingResponse)
async def get_upload_finish_settings():
    return await run_in_threadpool(upload_settings_service.get_upload_finish_settings)


@router.put("/settings/upload/finish", response_model=dict)
async def update_upload_finish_setting(payload: UploadFinishSettingUpdateRequest):
    payload_dict = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    try:
        return await run_in_threadpool(upload_settings_service.update_upload_finish_setting, payload_dict)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "message": str(exc),
                "success": False,
            },
        ) from exc


@data_center_client_router.post("/upload-data", response_model=UploadDataResponse)
async def upload_data(payload: UploadDataRequest):
    record_id = payload.record_id
    if not record_id:
        record_id = await run_in_threadpool(
            upload_record_service.create_upload_record,
            payload.csv_file_path,
            payload.zip_file_path,
            source="api",
        )
    try:
        queued = await run_in_threadpool(
            upload_record_service.enqueue_upload_record,
            record_id,
            csv_path=payload.csv_file_path,
            zip_path=payload.zip_file_path,
            meta=None,
        )
        if not queued:
            await run_in_threadpool(
                upload_record_service.mark_upload_record_failed,
                record_id,
                failure_stage="queue",
                failure_code="upload_enqueue_failed",
                error="Failed to enqueue upload task",
            )
            raise HTTPException(
                status_code=503,
                detail={"message": "Failed to enqueue upload task", "record_id": record_id},
            )
        return {
            "csv_file": payload.csv_file_path,
            "zip_file": payload.zip_file_path,
            "success": True,
            "record_id": record_id,
            "status": "queued",
            "message": "Upload task submitted",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error in upload-data: {str(exc)}", exc_info=True)
        await run_in_threadpool(
            upload_record_service.mark_upload_record_failed,
            record_id,
            failure_stage="request_processing",
            failure_code="server_unhandled_exception",
            error="Internal server error",
            error_detail=str(exc),
        )
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal server error",
                "error": str(exc),
            },
        )


@data_center_client_router.post("/upload-data/manual", response_model=UploadDataResponse)
async def upload_manual_data(
    csv_file: UploadFile = File(...),
    include_source_zip: bool = Form(False),
    all_files: bool = Form(False),
    meta: str | None = Form(None),
    record_id: str | None = Form(None),
    source_files: list[UploadFile] | None = File(None),
):
    try:
        return await upload_service.upload_manual_data(
            csv_file=csv_file,
            include_source_zip=include_source_zip,
            all_files=all_files,
            meta=meta,
            source_files=source_files,
            upload_record_id=record_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error in upload-data/manual: {str(exc)}", exc_info=True)
        upload_record_service.mark_upload_record_failed(
            record_id,
            failure_stage="request_processing",
            failure_code="server_unhandled_exception",
            error="Internal server error",
            error_detail=str(exc),
        )
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal server error",
                "error": str(exc),
            },
        )


@router.get("/upload-records", response_model=UploadRecordListResponse)
async def get_upload_records(
    page: int = 1,
    page_size: int = 20,
    record_id: str | None = None,
    status: str | None = None,
    model: str | None = None,
    barcode: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    return await run_in_threadpool(
        upload_record_service.get_upload_records,
        page=page,
        page_size=page_size,
        record_id=record_id,
        status=status,
        model=model,
        barcode=barcode,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/upload-record-stats", response_model=UploadRecordStatsResponse)
async def get_upload_record_stats(
    record_id: str | None = None,
    status: str | None = None,
    model: str | None = None,
    barcode: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    return await run_in_threadpool(
        upload_record_service.get_upload_record_stats,
        record_id=record_id,
        status=status,
        model=model,
        barcode=barcode,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/upload-record-filter-options", response_model=UploadRecordFilterOptionsResponse)
async def get_upload_record_filter_options():
    return await run_in_threadpool(upload_record_service.get_upload_record_filter_options)
