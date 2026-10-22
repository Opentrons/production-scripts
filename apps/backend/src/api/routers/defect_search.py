from __future__ import annotations

from html import escape
import logging
import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, field_validator

from modules.auth.dependencies import require_authenticated_user
from modules.auth.store import AuthUser
from modules.defect_search import feedback, maintenance, repository, service


router = APIRouter(prefix="/defect-search", tags=["defect-search"])
logger = logging.getLogger(__name__)
MAX_IMPORT_BYTES = 5 * 1024 * 1024


def require_defect_admin(user: AuthUser = Depends(require_authenticated_user)) -> AuthUser:
    if user.role != 'admin':
        raise HTTPException(status_code=403, detail='仅管理员可以维护缺陷知识库')
    return user


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    case_id: int = Field(gt=0, strict=True)
    query: str = Field(default='', max_length=500)
    action: str = Field(min_length=1, max_length=2000)
    outcome: Literal['passed', 'failed', 'pending']
    recurrence: Literal['unknown', 'yes', 'no'] = 'unknown'
    note: str = Field(default='', max_length=4000)
    repair_session_id: str = Field(default='', max_length=128)
    actual_serial_number: str = Field(default='', max_length=128)


class ImportPreviewRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    csv_content: str = Field(min_length=1, max_length=MAX_IMPORT_BYTES)

    @field_validator('csv_content')
    @classmethod
    def validate_csv_size(cls, value: str) -> str:
        if len(value.encode('utf-8')) > MAX_IMPORT_BYTES:
            raise ValueError('导入文件不能超过 5 MB')
        return value


class ImportRequest(ImportPreviewRequest):
    preview_token: str = Field(min_length=1, max_length=256)


async def _limit_import_body(request: Request) -> None:
    # Account for JSON overhead while keeping the CSV itself capped at 5 MB.
    body_limit = MAX_IMPORT_BYTES + 64 * 1024
    declared_size = request.headers.get('content-length')
    if declared_size:
        try:
            if int(declared_size) > body_limit:
                raise HTTPException(status_code=413, detail='导入请求不能超过 5 MB')
        except ValueError:
            raise HTTPException(status_code=400, detail='请求长度无效')
    if len(await request.body()) > body_limit:
        raise HTTPException(status_code=413, detail='导入请求不能超过 5 MB')


def _storage_unavailable(exc: Exception) -> HTTPException:
    logger.error('Local defect storage operation failed (%s)', type(exc).__name__)
    return HTTPException(status_code=503, detail='本地缺陷知识库暂时不可用，请稍后重试')


async def _storage_call(function, *args, **kwargs):
    try:
        return await run_in_threadpool(function, *args, **kwargs)
    except feedback.CaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except feedback.RepairSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (sqlite3.Error, OSError) as exc:
        raise _storage_unavailable(exc) from exc


@router.get("/options")
async def get_defect_search_options():
    return await _storage_call(service.get_options)


@router.get("/cases")
async def find_defect_cases(
    q: str = Query(default="", max_length=500),
    product: str = Query(default="", max_length=120),
    station: str = Query(default="", max_length=120),
    defect_code: str = Query(default="", max_length=120),
    action: str = Query(default="", max_length=500),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    return await _storage_call(
        service.search_cases,
        query=q,
        product=product,
        station=station,
        defect_code=defect_code,
        action=action,
        page=page,
        page_size=page_size,
    )


@router.get('/source/{record_id}/data')
async def local_source_record_data(record_id: int):
    case = await _storage_call(service.get_local_case, record_id)
    if case is None:
        raise HTTPException(status_code=404, detail='未找到有效的本地缺陷案例')
    return {'case': case}


@router.get('/feedback')
async def get_case_feedback(
    case_id: int = Query(gt=0),
    repair_session_id: str = Query(default='', max_length=128),
    user: AuthUser = Depends(require_authenticated_user),
):
    try:
        return {'feedback': await _storage_call(
            feedback.list_feedback, service.DATABASE_PATH, service.DATA_PATH, case_id,
            repair_session_id=repair_session_id, created_by=user.id,
        )}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post('/feedback')
async def record_case_feedback(body: FeedbackRequest, user: AuthUser = Depends(require_authenticated_user)):
    try:
        return await _storage_call(
            feedback.save_feedback, service.DATABASE_PATH, service.DATA_PATH,
            **body.model_dump(), created_by=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get('/maintenance')
async def get_maintenance(_user: AuthUser = Depends(require_defect_admin)):
    await _storage_call(repository.ensure_database, service.DATABASE_PATH, service.DATA_PATH)
    return await _storage_call(maintenance.get_maintenance_status, service.DATABASE_PATH)


@router.post('/import/preview', dependencies=[Depends(_limit_import_body)])
async def preview_local_import(body: ImportPreviewRequest, _user: AuthUser = Depends(require_defect_admin)):
    try:
        return await _storage_call(maintenance.preview_import, service.DATABASE_PATH, service.DATA_PATH, body.csv_content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post('/import', dependencies=[Depends(_limit_import_body)])
async def import_local_cases(body: ImportRequest, _user: AuthUser = Depends(require_defect_admin)):
    try:
        return await _storage_call(
            maintenance.import_csv, service.DATABASE_PATH, service.DATA_PATH,
            body.csv_content, body.preview_token,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post('/backup')
async def backup_local_database(_user: AuthUser = Depends(require_defect_admin)):
    await _storage_call(repository.ensure_database, service.DATABASE_PATH, service.DATA_PATH)
    backup = await _storage_call(maintenance.backup_database, service.DATABASE_PATH, reason='manual')
    return {'backup': backup.name}


@router.get("/source/{record_id}", response_class=HTMLResponse)
async def local_source_record(record_id: int):
    case = await _storage_call(service.get_local_case, record_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Local defect record not found")
    labels = {
        "source": "来源台账", "source_sheet": "原工作表", "source_row": "原始行号",
        "record_no": "记录编号", "date": "日期", "station": "测试工站", "product": "产品型号",
        "defect_code": "缺陷代码", "serial_number": "序列号", "defect_description": "缺陷描述",
        "containment_action": "临时措施", "exchange_component": "更换零件", "exchange_verification": "更换验证",
        "cause_analysis": "原因分析", "root_cause": "根因", "long_term_action_qe": "质量长期措施",
        "long_term_action_engineering": "工程长期措施", "responsible_department": "责任部门",
        "symptom_category": "缺陷类别", "remark": "备注",
    }
    rows = "".join(f"<tr><th>{escape(labels.get(key, key))}</th><td>{escape(str(value or '—'))}</td></tr>"
                   for key, value in case.items() if key not in {"source_url", "local_id"})
    return HTMLResponse("<!doctype html><html lang='zh-CN'><meta charset='utf-8'>"
                        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
                        "<title>本地缺陷台账</title><style>body{font:16px/1.6 system-ui;margin:24px auto;padding:0 20px;max-width:1000px;color:#203944}"
                        "table{border-collapse:collapse;width:100%}th,td{border:1px solid #dbe4e8;padding:12px;text-align:left;overflow-wrap:anywhere}"
                        "th{width:180px;background:#f3f6f8}h1{font-size:26px}</style>"
                        "<h1>本地缺陷台账 · 记录详情</h1><p>记录保存在本地知识库，来源年份与行号用于追溯导入台账。</p>"
                        f"<table>{rows}</table></html>", headers={"Cache-Control": "no-store"})
