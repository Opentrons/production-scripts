from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from api.models import (
    CollectionDataResponse,
    CollectionFilterOptionsResponse,
    CollectionListResponse,
    DataAnalysisOnlineRequest,
    DataAnalysisPathRequest,
    DataAnalysisResponse,
    DataAnalysisSpecRequest,
    DataAnalysisSpecResponse,
    DataLinksResponse,
)
from core.logging import get_logger
from modules.data_analysis import data as data_service
from modules.data_analysis import data_analysis as data_analysis_service
from modules.data_analysis import data_links as data_links_service


logger = get_logger(__name__)
router = APIRouter()

@router.get("/collections", response_model=CollectionListResponse)
async def get_collections():
    return await run_in_threadpool(data_service.get_collections)


@router.get("/collection-data", response_model=CollectionDataResponse)
async def get_collection_data(
    collection_name: str,
    page: int = 1,
    page_size: int = 20,
    model: str | None = None,
    type: str | None = None,
    total_result: str | None = None,
    barcode: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
):
    return await run_in_threadpool(
        data_service.get_collection_data,
        collection_name=collection_name,
        page=page,
        page_size=page_size,
        model=model,
        production_type=type,
        total_result=total_result,
        barcode=barcode,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/collection-filter-options", response_model=CollectionFilterOptionsResponse)
async def get_collection_filter_options(collection_name: str):
    return await run_in_threadpool(data_service.get_collection_filter_options, collection_name)


@router.get("/data-links", response_model=DataLinksResponse)
async def get_data_links():
    return data_links_service.get_data_links()


@router.post("/data-analysis/analyze", response_model=DataAnalysisResponse)
async def analyze_data_files(files: list[UploadFile] = File(...)):
    try:
        logger.info(
            "Received data analysis upload request: files=%s",
            [file.filename for file in files],
        )
        return await data_analysis_service.analyze_uploaded_files(files)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error in data-analysis/analyze: {str(exc)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/data-analysis/analyze-paths", response_model=DataAnalysisResponse)
async def analyze_data_paths(payload: DataAnalysisPathRequest):
    try:
        logger.info("Received data analysis path request: file_paths=%s", payload.file_paths)
        return await run_in_threadpool(data_analysis_service.analyze_paths, payload.file_paths)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error in data-analysis/analyze-paths: {str(exc)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/data-analysis/analyze-online", response_model=DataAnalysisResponse)
async def analyze_online_data(payload: DataAnalysisOnlineRequest):
    try:
        return await run_in_threadpool(
            data_analysis_service.analyze_online,
            payload.model_dump() if hasattr(payload, "model_dump") else payload.dict(),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error in data-analysis/analyze-online: {str(exc)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/data-analysis/specs", response_model=DataAnalysisSpecResponse)
async def get_data_analysis_specs():
    return await run_in_threadpool(data_analysis_service.get_specs)


@router.put("/data-analysis/specs/gravimetric", response_model=dict)
async def update_data_analysis_gravimetric_spec(payload: DataAnalysisSpecRequest):
    return await run_in_threadpool(
        data_analysis_service.update_gravimetric_spec,
        payload.model_dump() if hasattr(payload, "model_dump") else payload.dict(),
    )
