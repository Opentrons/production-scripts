from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from api.models import (
    UploadDataRequest,
    UploadDataResponse,
    UploadFinishSettingResponse,
    UploadFinishSettingUpdateRequest,
    UploadRecordFilterOptionsResponse,
    UploadRecordListResponse,
    UploadRecordStatsResponse,
)
from core.logging import get_logger
from modules.uploads import upload as upload_service
from modules.uploads import upload_records as upload_record_service
from modules.uploads import upload_settings as upload_settings_service


logger = get_logger(__name__)
router = APIRouter()
data_center_client_router = APIRouter()

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
    record_id = upload_record_service.create_upload_record(
        payload.csv_file_path,
        payload.zip_file_path,
        source="api",
    )
    try:
        return await run_in_threadpool(
            upload_service.upload_data,
            csv_path=payload.csv_file_path,
            zip_path=payload.zip_file_path,
            upload_record_id=record_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error in upload-data: {str(exc)}", exc_info=True)
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
    source_files: list[UploadFile] | None = File(None),
):
    try:
        return await upload_service.upload_manual_data(
            csv_file=csv_file,
            include_source_zip=include_source_zip,
            all_files=all_files,
            meta=meta,
            source_files=source_files,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error in upload-data/manual: {str(exc)}", exc_info=True)
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
