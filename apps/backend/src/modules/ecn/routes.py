from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.concurrency import run_in_threadpool
from pymongo.errors import DuplicateKeyError

from core.google import GoogleDriverError
from modules.ecn.models import (
    EcnCreateRequest,
    EcnCreateResponse,
    EcnRecordsResponse,
    EcnSyncCheckResponse,
    EcnUpdateRequest,
    EcnRecord,
    EcnMonitorSettings,
    EcnRiskScanRequest,
    EcnRiskScanResult,
)
from modules.ecn.runtime import ecn_monitor_service, ecn_service
from modules.ecn.service import EcnConflictError, EcnValidationError


router = APIRouter(prefix="/information/ecn", tags=["ecn"])


@router.get("/monitor/settings", response_model=EcnMonitorSettings)
async def get_monitor_settings() -> EcnMonitorSettings:
    return EcnMonitorSettings.model_validate(ecn_monitor_service.get_settings())


@router.put("/monitor/settings", response_model=EcnMonitorSettings)
async def update_monitor_settings(payload: EcnMonitorSettings) -> EcnMonitorSettings:
    return EcnMonitorSettings.model_validate(ecn_monitor_service.save_settings(payload.model_dump()))


@router.get("/monitor/results", response_model=list[EcnRiskScanResult])
async def list_monitor_results(limit: int = Query(default=30, ge=1, le=100)) -> list[EcnRiskScanResult]:
    return [EcnRiskScanResult.model_validate(item) for item in ecn_monitor_service.list_results(limit)]


@router.post("/monitor/scan", response_model=EcnRiskScanResult)
async def run_monitor_scan(payload: EcnRiskScanRequest | None = None) -> EcnRiskScanResult:
    result = await run_in_threadpool(ecn_monitor_service.scan, payload.scan_items if payload else None, "manual")
    return EcnRiskScanResult.model_validate(result)


@router.get("", response_model=EcnRecordsResponse)
async def list_ecn_records(
    table: Literal["eng", "ipqc"] = Query(default="eng"),
    search: str = Query(default="", max_length=100),
    status: str = Query(default="", max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=10, le=100),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
) -> EcnRecordsResponse:
    try:
        return await run_in_threadpool(
            ecn_service.list_records,
            search=search,
            status=status,
            page=page,
            page_size=page_size,
            sort_order=sort_order,
            refresh_issued_dates=False,
            table=table,
        )
    except GoogleDriverError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/check-sync", response_model=EcnSyncCheckResponse)
async def check_ecn_sync(table: Literal["eng", "ipqc"] = Query(default="eng")) -> EcnSyncCheckResponse:
    try:
        return await run_in_threadpool(ecn_service.check_sync, table=table)
    except GoogleDriverError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/sync", response_model=EcnSyncCheckResponse)
async def sync_ecn(table: Literal["eng", "ipqc"] = Query(default="eng")) -> EcnSyncCheckResponse:
    try:
        return await run_in_threadpool(ecn_service.sync_from_google, table=table)
    except GoogleDriverError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("", response_model=EcnCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_ecn(payload: EcnCreateRequest, table: Literal["eng", "ipqc"] = Query(default="eng")) -> EcnCreateResponse:
    try:
        return await run_in_threadpool(ecn_service.create_ecn, payload, table=table)
    except EcnValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (EcnConflictError, DuplicateKeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except GoogleDriverError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/{record_id:path}", response_model=EcnRecord)
async def get_ecn_for_edit(record_id: str) -> EcnRecord:
    try:
        return await run_in_threadpool(ecn_service.get_record_for_edit, record_id)
    except EcnValidationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{record_id:path}", response_model=EcnRecord)
async def update_ecn(record_id: str, payload: EcnUpdateRequest) -> EcnRecord:
    try:
        return await run_in_threadpool(ecn_service.update_ecn, record_id, payload)
    except EcnValidationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except EcnConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except GoogleDriverError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.delete("/{record_id:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ecn(record_id: str) -> Response:
    try:
        await run_in_threadpool(ecn_service.delete_ecn, record_id)
    except EcnValidationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except EcnConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except GoogleDriverError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
