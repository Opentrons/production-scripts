from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.concurrency import run_in_threadpool

from api.models import IntegrationCollectionDataResponse
from core.i18n import api_error
from modules.auth.dependencies import require_collection_data_access
from modules.data_analysis import data as data_service


router = APIRouter(
    prefix="/integrations",
    tags=["integrations"],
    dependencies=[Depends(require_collection_data_access)],
)


@router.get("/collection-data", response_model=IntegrationCollectionDataResponse)
async def get_collection_data(
    request: Request,
    collection_name: str = Query(default=data_service.ALL_COLLECTIONS_KEY, min_length=1, max_length=128),
    limit: int = Query(default=200, ge=1, le=1000),
    cursor: str | None = Query(default=None, max_length=2048),
    model: str | None = Query(default=None, max_length=128),
    product_type: str | None = Query(default=None, alias="type", max_length=128),
    total_result: str | None = Query(default=None, max_length=64),
    barcode: str | None = Query(default=None, max_length=256),
    updated_after: str | None = Query(default=None, max_length=64),
    updated_before: str | None = Query(default=None, max_length=64),
):
    try:
        return await run_in_threadpool(
            data_service.get_collection_data_cursor,
            collection_name=collection_name,
            limit=limit,
            cursor=cursor,
            model=model,
            production_type=product_type,
            total_result=total_result,
            barcode=barcode,
            start_date=updated_after,
            end_date=updated_before,
        )
    except data_service.InvalidCollectionCursor as exc:
        raise api_error(
            status.HTTP_400_BAD_REQUEST,
            "integration.invalid_cursor",
            locale=request.headers.get("Accept-Language"),
        ) from exc
    except data_service.CollectionNotFoundError as exc:
        raise api_error(
            status.HTTP_404_NOT_FOUND,
            "errors.not_found",
            locale=request.headers.get("Accept-Language"),
        ) from exc
    except data_service.CollectionDataUnavailableError as exc:
        raise api_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "errors.service_unavailable",
            locale=request.headers.get("Accept-Language"),
        ) from exc
