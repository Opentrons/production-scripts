from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from api.models import (
    ProductManagementFilterOptionsResponse,
    ProductManagementListResponse,
    ProductManagementManualAddRequest,
    ProductManagementManualAddResponse,
    ProductManagementSyncResponse,
    ProductStatusUpdateRequest,
    ProductStatusUpdateResponse,
    UnitTrackerRowsResponse,
    UnitTrackerSyncResponse,
)
from modules.data_analysis import product_management as product_management_service
from modules.data_analysis import unit_tracker as unit_tracker_service


router = APIRouter()

@router.get("/unit-tracker/rows", response_model=UnitTrackerRowsResponse)
async def get_unit_tracker_rows(
    page: int = 1,
    page_size: int = 100,
    product: str | None = None,
    test_type: str | None = None,
    barcode: str | None = None,
):
    return await run_in_threadpool(
        unit_tracker_service.list_rows,
        page=page,
        page_size=page_size,
        product=product,
        test_type=test_type,
        barcode=barcode,
    )


@router.post("/unit-tracker/sync", response_model=UnitTrackerSyncResponse)
async def sync_unit_tracker_rows(limit: int | None = Query(default=None, ge=1)):
    result = await run_in_threadpool(unit_tracker_service.sync_all_rows, limit=limit)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error") or "Unit tracker sync failed")
    return result


@router.get("/product-management/products", response_model=ProductManagementListResponse)
async def get_product_management_products(
    page: int = 1,
    page_size: int = 100,
    barcode: str | None = None,
    model: str | None = None,
    test_type: str | None = None,
    status: str | None = None,
):
    return await run_in_threadpool(
        product_management_service.get_products,
        page=page,
        page_size=page_size,
        barcode=barcode,
        model=model,
        test_type=test_type,
        status=status,
    )


@router.get("/product-management/filter-options", response_model=ProductManagementFilterOptionsResponse)
async def get_product_management_filter_options():
    return await run_in_threadpool(product_management_service.get_filter_options)


@router.post("/product-management/sync", response_model=ProductManagementSyncResponse)
async def sync_product_management_products():
    result = await run_in_threadpool(product_management_service.sync_products_from_upload_records)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error") or "Product sync failed")
    return result


@router.post("/product-management/manual-add", response_model=ProductManagementManualAddResponse)
async def add_manual_product_or_test(request: ProductManagementManualAddRequest):
    result = await run_in_threadpool(
        product_management_service.add_manual_product_or_test,
        request.model_dump() if hasattr(request, "model_dump") else request.dict(),
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error") or "Manual product add failed")
    return result


@router.put("/product-management/product-status", response_model=ProductStatusUpdateResponse)
async def update_product_status(request: ProductStatusUpdateRequest):
    result = await run_in_threadpool(
        product_management_service.update_product_status,
        barcode=request.barcode,
        status=request.status,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error") or "Product status update failed")
    return result
