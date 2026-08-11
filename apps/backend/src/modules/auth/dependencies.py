from __future__ import annotations

import secrets
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from fastapi import Depends, HTTPException, Request, status

from core import config
from modules.auth.service import (
    AuthService,
    AuthenticationConfigurationError,
    AuthenticationError,
)
from modules.auth.store import AuthUser


ACCESS_COOKIE_NAME = "production_access_token"
REFRESH_COOKIE_NAME = "production_refresh_token"
CSRF_COOKIE_NAME = "production_csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@dataclass(frozen=True)
class AuthContext:
    user: AuthUser
    claims: dict[str, Any]
    cookie_authenticated: bool


@lru_cache(maxsize=1)
def get_auth_service() -> AuthService:
    service = AuthService(
        db_path=config.AUTH_DB_PATH,
        jwt_secret=config.AUTH_JWT_SECRET,
        issuer=config.AUTH_JWT_ISSUER,
        audience=config.AUTH_JWT_AUDIENCE,
        access_token_minutes=config.AUTH_ACCESS_TOKEN_MINUTES,
        refresh_token_hours=config.AUTH_REFRESH_TOKEN_HOURS,
    )
    service.initialize()
    return service


def _credentials(request: Request) -> tuple[str, bool]:
    cookie_token = request.cookies.get(ACCESS_COOKIE_NAME, "").strip()
    if cookie_token:
        return cookie_token, True
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        return token.strip(), False
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _verify_csrf(request: Request, expected: str) -> None:
    cookie_value = request.cookies.get(CSRF_COOKIE_NAME, "")
    header_value = request.headers.get(CSRF_HEADER_NAME, "")
    if not (
        cookie_value
        and header_value
        and expected
        and secrets.compare_digest(cookie_value, header_value)
        and secrets.compare_digest(cookie_value, expected)
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")


def verify_refresh_csrf(request: Request) -> None:
    cookie_value = request.cookies.get(CSRF_COOKIE_NAME, "")
    header_value = request.headers.get(CSRF_HEADER_NAME, "")
    if not cookie_value or not header_value or not secrets.compare_digest(cookie_value, header_value):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")


def require_auth_context(
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> AuthContext:
    token, cookie_authenticated = _credentials(request)
    try:
        user, claims = service.verify_access_token(token)
    except AuthenticationConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    if cookie_authenticated and request.method.upper() not in SAFE_METHODS:
        _verify_csrf(request, str(claims.get("csrf", "")))
    return AuthContext(user=user, claims=claims, cookie_authenticated=cookie_authenticated)


def require_authenticated_user(
    context: AuthContext = Depends(require_auth_context),
) -> AuthUser:
    return context.user
