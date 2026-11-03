from __future__ import annotations

import logging
import sqlite3
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.background import BackgroundTask

from modules.auth.dependencies import require_platform_access
from modules.auth.store import AuthUser
from .service import ConflictError, NotFoundError, TestFailureService, get_service
from .analysis import FailureAnalysisService, get_analysis_service
from .report_links import RoutedReportLinkService, get_report_link_service


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/defect-search/test-failures", tags=["test-failures"], dependencies=[Depends(require_platform_access)])


def require_editor(user: AuthUser = Depends(require_platform_access)) -> AuthUser:
    if user.role == "viewer":
        raise HTTPException(status_code=403, detail="只读账号不能扫描报告或保存测试返修确认")
    return user


class ConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=4000)
    version: str = Field(min_length=1, max_length=128)


class AnalysisRequest(BaseModel):
    """Analysis always uses the indexed report, never client supplied paths."""
    model_config = ConfigDict(extra="forbid")
    report_revision: str = Field(min_length=1, max_length=128)
    force: bool = False


async def _call(function, *args, **kwargs):
    try:
        return await run_in_threadpool(function, *args, **kwargs)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (sqlite3.Error, OSError) as exc:
        logger.warning("Test failure storage unavailable: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="测试失败记录暂时不可用，请稍后重试") from exc


@router.get("/devices")
async def list_devices(
    q: str = Query(default="", max_length=500), product: str = Query(default="", max_length=200),
    date_from: str = "", date_to: str = "", mode: str = Query(default="", max_length=100),
    kind: str = Query(default="", max_length=100), confirmation: Literal["all", "pending", "confirmed"] = "all",
    page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
    service: TestFailureService = Depends(get_service),
):
    return await _call(service.list_devices, q=q, product=product, date_from=date_from, date_to=date_to, mode=mode, kind=kind, confirmation=confirmation, page=page, page_size=page_size)


@router.get("/scan")
def scan_status(service: TestFailureService = Depends(get_service)):
    return service.scan_status()


@router.post("/scan", status_code=202)
def scan_reports(_user: AuthUser = Depends(require_editor), service: TestFailureService = Depends(get_service)):
    return service.request_scan()


@router.get("/reports/{report_id}")
async def report_detail(report_id: str, service: TestFailureService = Depends(get_service)):
    return await _call(service.get_report, report_id)


@router.get("/reports/{report_id}/analysis")
async def analysis_status(report_id: str, service: FailureAnalysisService = Depends(get_analysis_service)):
    return await _call(service.status, report_id)


@router.get("/reports/{report_id}/report-link")
async def report_link(
    report_id: str, service: TestFailureService = Depends(get_service),
    links: RoutedReportLinkService = Depends(get_report_link_service),
):
    report = await _call(service.repository.get_report, report_id)
    return await _call(links.lookup, report)


@router.post("/reports/{report_id}/report-link", status_code=202)
async def refresh_report_link(
    report_id: str, _user: AuthUser = Depends(require_editor),
    service: TestFailureService = Depends(get_service),
    links: RoutedReportLinkService = Depends(get_report_link_service),
):
    report = await _call(service.repository.get_report, report_id)
    return await _call(links.lookup, report, force=True)


@router.post("/reports/{report_id}/analysis", status_code=202)
async def analyze_failure(
    report_id: str, response: Response, body: AnalysisRequest,
    _user: AuthUser = Depends(require_editor), service: FailureAnalysisService = Depends(get_analysis_service),
):
    result = await _call(service.request, report_id, body.report_revision, force=body.force)
    if result["status"] != "running":
        response.status_code = 200
    return result


@router.get("/reports/{report_id}/attachments/{kind}/preview")
async def preview_attachment(report_id: str, kind: Literal["json", "log", "encoder"], service: TestFailureService = Depends(get_service)):
    return await _call(service.preview_attachment, report_id, kind)


@router.get("/reports/{report_id}/attachments/{kind}")
async def download_attachment(report_id: str, kind: Literal["json", "log", "encoder"], service: TestFailureService = Depends(get_service)):
    handle, filename = await _call(service.open_attachment, report_id, kind)

    def chunks():
        try:
            while chunk := handle.read(256 * 1024):
                yield chunk
        finally:
            handle.close()

    media_type = {"json": "application/json", "log": "text/plain", "encoder": "text/csv"}[kind]
    return StreamingResponse(chunks(), media_type=media_type, background=BackgroundTask(handle.close), headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename, safe='')}",
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
    })


@router.get("/devices/{device_id}/confirmations")
async def confirmations(device_id: str, service: TestFailureService = Depends(get_service)):
    return await _call(service.list_confirmations, device_id)


@router.post("/devices/{device_id}/confirmations", status_code=201)
async def confirm(device_id: str, body: ConfirmationRequest, user: AuthUser = Depends(require_editor), service: TestFailureService = Depends(get_service)):
    return await _call(service.confirm_device, device_id, body.text, body.version, user.id, user.display_name or user.username)
