from fastapi import APIRouter, HTTPException, Query

from modules.duro.client import DuroApiError, DuroAuthenticationError
from modules.duro.models import DuroVersionCatalogResponse
from modules.duro.runtime import duro_service


router = APIRouter(prefix="/test-versions", tags=["test-versions"])


@router.get("/duro", response_model=DuroVersionCatalogResponse)
def get_duro_test_versions(
    refresh: bool = Query(default=False, description="Ignore the cached Duro version catalog"),
) -> DuroVersionCatalogResponse:
    try:
        return duro_service.get_version_catalog(refresh=refresh)
    except DuroAuthenticationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DuroApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
