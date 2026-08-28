from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.concurrency import run_in_threadpool

from modules.supplies.models import (
    SupplementaryMaterial,
    SupplementaryMaterialCreate,
    SupplementaryMaterialListResponse,
    SupplementaryMaterialUpdate,
)
from modules.supplies.runtime import supplementary_material_service
from modules.supplies.service import (
    DuplicateSupplementaryMaterialError,
    SupplementaryMaterialNotFoundError,
)


router = APIRouter(prefix="/supplies", tags=["supplies"])


@router.get("", response_model=SupplementaryMaterialListResponse)
async def list_supplies(
    q: str | None = Query(default=None, max_length=200),
) -> SupplementaryMaterialListResponse:
    items = await run_in_threadpool(supplementary_material_service.list, q)
    return SupplementaryMaterialListResponse(items=items, total=len(items))


@router.post("", response_model=SupplementaryMaterial, status_code=status.HTTP_201_CREATED)
async def create_supply(payload: SupplementaryMaterialCreate) -> SupplementaryMaterial:
    try:
        return await run_in_threadpool(supplementary_material_service.create, payload)
    except DuplicateSupplementaryMaterialError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put("/{material_id}", response_model=SupplementaryMaterial)
async def update_supply(
    material_id: str,
    payload: SupplementaryMaterialUpdate,
) -> SupplementaryMaterial:
    try:
        return await run_in_threadpool(supplementary_material_service.update, material_id, payload)
    except SupplementaryMaterialNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DuplicateSupplementaryMaterialError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supply(material_id: str) -> Response:
    try:
        await run_in_threadpool(supplementary_material_service.delete, material_id)
    except SupplementaryMaterialNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
