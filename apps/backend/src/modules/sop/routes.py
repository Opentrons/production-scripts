from fastapi import APIRouter, HTTPException, Query

from core.google import GoogleConfigurationError, GoogleDriverError
from modules.sop.models import SopMasterSheetResponse, SopPdfAnalysisResponse
from modules.sop.runtime import sop_service
from modules.sop.service import SopAnalysisError


router = APIRouter(prefix="/sop", tags=["sop"])


@router.get("/master-sheet", response_model=SopMasterSheetResponse)
def get_sop_master_sheet(
    refresh: bool = Query(default=False, description="忽略 SQLite 缓存并重新读取 Google Sheet"),
) -> SopMasterSheetResponse:
    try:
        return sop_service.get_master_sheet(refresh=refresh)
    except GoogleConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GoogleDriverError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/files/{file_id}/analysis", response_model=SopPdfAnalysisResponse)
def analyze_sop_pdf(
    file_id: str,
    refresh: bool = Query(default=False, description="忽略 SQLite 缓存并重新分析 SOP PDF"),
) -> SopPdfAnalysisResponse:
    try:
        return sop_service.analyze_pdf(file_id, refresh=refresh)
    except GoogleConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GoogleDriverError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except SopAnalysisError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
