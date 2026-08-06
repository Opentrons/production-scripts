from fastapi import APIRouter, HTTPException, Query

from duro.client import DuroApiError, DuroAuthenticationError
from duro.models import (
    DuroComponentChildrenResponse,
    DuroConnectionStatus,
    DuroProductBomResponse,
    DuroProductSearchRequest,
    DuroProductSearchResponse,
)
from duro.runtime import duro_client, duro_service


router = APIRouter(prefix="/duro", tags=["duro"])


@router.get("/status", response_model=DuroConnectionStatus)
def get_duro_status() -> DuroConnectionStatus:
    return duro_client.connection_status()


@router.get("/products", response_model=DuroProductSearchResponse)
def get_duro_products(
    refresh: bool = Query(default=False, description="忽略 SQLite 缓存并重新读取 Duro"),
) -> DuroProductSearchResponse:
    return _handle_product_search(DuroProductSearchRequest(), refresh=refresh)


@router.post("/products/search", response_model=DuroProductSearchResponse)
def search_duro_products(
    payload: DuroProductSearchRequest,
    refresh: bool = Query(default=False),
) -> DuroProductSearchResponse:
    return _handle_product_search(payload, refresh=refresh)


@router.get("/products/{product_id}/bom", response_model=DuroProductBomResponse)
def get_duro_product_bom(
    product_id: str,
    refresh: bool = Query(default=False, description="忽略 SQLite 缓存并重新读取产品 BOM"),
) -> DuroProductBomResponse:
    try:
        return duro_service.get_product_bom(product_id, refresh=refresh)
    except DuroAuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except DuroApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/products/{product_id}/bom/search", response_model=DuroProductBomResponse)
def search_duro_product_bom(
    product_id: str,
    q: str = Query(min_length=1, max_length=200, description="BOM 料号或产品名称"),
) -> DuroProductBomResponse:
    try:
        return duro_service.search_product_bom(product_id, q)
    except DuroAuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except DuroApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/components/{component_id}/children", response_model=DuroComponentChildrenResponse)
def get_duro_component_children(
    component_id: str,
    refresh: bool = Query(default=False, description="忽略 SQLite 缓存并重新读取子组件"),
) -> DuroComponentChildrenResponse:
    try:
        return duro_service.get_component_children(component_id, refresh=refresh)
    except DuroAuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except DuroApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _handle_product_search(
    payload: DuroProductSearchRequest,
    refresh: bool,
) -> DuroProductSearchResponse:
    try:
        return duro_service.search_products(payload, refresh=refresh)
    except DuroAuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except DuroApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
