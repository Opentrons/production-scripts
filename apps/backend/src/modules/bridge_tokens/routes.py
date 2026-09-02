from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from modules.auth.dependencies import require_authenticated_user
from modules.auth.store import AuthUser
from modules.bridge_tokens.models import AllocationRecordPage, CurrentUserTokenResponse
from modules.bridge_tokens.configuration import (
    BridgeTokenConfigurationResponse,
    BridgeTokenConfigurationService,
    BridgeTokenConfigurationUnavailable,
    BridgeTokenConfigurationUpdate,
)
from modules.bridge_tokens.runtime import (
    bridge_token_configuration_service,
    bridge_token_service,
)
from modules.bridge_tokens.service import BridgeTokenService


router = APIRouter(prefix="/bridge-tokens", tags=["bridge-tokens"])


def get_bridge_token_service() -> BridgeTokenService:
    return bridge_token_service


def get_bridge_token_configuration_service() -> BridgeTokenConfigurationService:
    return bridge_token_configuration_service


def require_bridge_token_admin(
    user: AuthUser = Depends(require_authenticated_user),
) -> AuthUser:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可以修改 Bridge 自动化配置",
        )
    return user


@router.get("/me", response_model=CurrentUserTokenResponse)
def get_current_user_tokens(
    refresh: bool = Query(True),
    user: AuthUser = Depends(require_authenticated_user),
    service: BridgeTokenService = Depends(get_bridge_token_service),
) -> CurrentUserTokenResponse:
    return service.current_user_dashboard(user, refresh=refresh)


@router.get("/me/records", response_model=AllocationRecordPage)
def get_current_user_records(
    action: Literal[
        "weekly_allocation",
        "low_balance_topup",
        "weekly_rebalance",
        "weekly_reminder",
    ]
    | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: AuthUser = Depends(require_authenticated_user),
    service: BridgeTokenService = Depends(get_bridge_token_service),
) -> AllocationRecordPage:
    return service.list_user_records(
        user,
        action=action,
        page=page,
        page_size=page_size,
    )


@router.get("/configuration", response_model=BridgeTokenConfigurationResponse)
def get_bridge_token_configuration(
    _: AuthUser = Depends(require_bridge_token_admin),
    service: BridgeTokenConfigurationService = Depends(
        get_bridge_token_configuration_service
    ),
) -> BridgeTokenConfigurationResponse:
    try:
        return service.get_configuration()
    except BridgeTokenConfigurationUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.put("/configuration", response_model=BridgeTokenConfigurationResponse)
def update_bridge_token_configuration(
    payload: BridgeTokenConfigurationUpdate,
    user: AuthUser = Depends(require_bridge_token_admin),
    service: BridgeTokenConfigurationService = Depends(
        get_bridge_token_configuration_service
    ),
) -> BridgeTokenConfigurationResponse:
    try:
        return service.update_configuration(payload, updated_by=user.username)
    except BridgeTokenConfigurationUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
