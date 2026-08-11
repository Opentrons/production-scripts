from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import RLock

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from core import config
from modules.auth.dependencies import (
    ACCESS_COOKIE_NAME,
    CSRF_COOKIE_NAME,
    REFRESH_COOKIE_NAME,
    AuthContext,
    get_auth_service,
    require_auth_context,
    verify_refresh_csrf,
)
from modules.auth.models import (
    AuthSessionResponse,
    AuthStatusResponse,
    AuthUserResponse,
    LoginRequest,
    LogoutResponse,
)
from modules.auth.service import (
    AuthService,
    AuthenticationConfigurationError,
    AuthenticationError,
    IssuedSession,
    isoformat,
)


router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRateLimiter:
    def __init__(self, attempts: int = 5, window_minutes: int = 15) -> None:
        self.attempts = attempts
        self.window = timedelta(minutes=window_minutes)
        self._failures: dict[str, deque[datetime]] = defaultdict(deque)
        self._lock = RLock()

    def check(self, key: str) -> None:
        now = datetime.now(timezone.utc)
        with self._lock:
            failures = self._failures[key]
            while failures and now - failures[0] > self.window:
                failures.popleft()
            if len(failures) >= self.attempts:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many login attempts. Try again later.",
                )

    def record_failure(self, key: str) -> None:
        with self._lock:
            self._failures[key].append(datetime.now(timezone.utc))

    def clear(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)


login_rate_limiter = LoginRateLimiter()


def _client_ip(request: Request) -> str:
    direct_ip = request.client.host if request.client else "unknown"
    if direct_ip in {"127.0.0.1", "::1"}:
        forwarded = request.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip()
        if forwarded:
            return forwarded
    return direct_ip


def _user_response(session_user) -> AuthUserResponse:
    return AuthUserResponse(
        id=session_user.id,
        username=session_user.username,
        display_name=session_user.display_name,
        role=session_user.role,
    )


def _session_response(session: IssuedSession) -> AuthSessionResponse:
    return AuthSessionResponse(
        user=_user_response(session.user),
        access_expires_at=isoformat(session.access_expires_at),
        session_expires_at=isoformat(session.session_expires_at),
    )


def _set_session_cookies(response: Response, session: IssuedSession) -> None:
    common = {
        "secure": config.AUTH_COOKIE_SECURE,
        "samesite": "lax",
    }
    response.set_cookie(
        ACCESS_COOKIE_NAME,
        session.access_token,
        httponly=True,
        path="/",
        max_age=config.AUTH_ACCESS_TOKEN_MINUTES * 60,
        **common,
    )
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        session.refresh_token,
        httponly=True,
        path="/api/auth",
        max_age=config.AUTH_REFRESH_TOKEN_HOURS * 60 * 60,
        **common,
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        session.csrf_token,
        httponly=False,
        path="/",
        max_age=config.AUTH_REFRESH_TOKEN_HOURS * 60 * 60,
        **common,
    )


def _clear_session_cookies(response: Response) -> None:
    common = {"secure": config.AUTH_COOKIE_SECURE, "samesite": "lax"}
    response.delete_cookie(ACCESS_COOKIE_NAME, path="/", httponly=True, **common)
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/api/auth", httponly=True, **common)
    response.delete_cookie(CSRF_COOKIE_NAME, path="/", httponly=False, **common)


@router.post("/login", response_model=AuthSessionResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    ip_address = _client_ip(request)
    rate_key = f"{ip_address}:{payload.username.strip().casefold()}"
    login_rate_limiter.check(rate_key)
    try:
        session = service.login(
            payload.username,
            payload.password,
            user_agent=request.headers.get("User-Agent", ""),
            ip_address=ip_address,
        )
    except AuthenticationConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except AuthenticationError as exc:
        login_rate_limiter.record_failure(rate_key)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    login_rate_limiter.clear(rate_key)
    _set_session_cookies(response, session)
    return _session_response(session)


@router.post("/refresh", response_model=AuthSessionResponse)
def refresh(
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    verify_refresh_csrf(request)
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME, "")
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token required")
    try:
        session = service.refresh(refresh_token)
    except AuthenticationConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except AuthenticationError as exc:
        _clear_session_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    _set_session_cookies(response, session)
    return _session_response(session)


@router.post("/logout", response_model=LogoutResponse)
def logout(
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    # Logout only removes privileges, so it remains available even if the CSRF cookie was lost.
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME, "")
    if refresh_token:
        service.revoke_refresh_token(refresh_token)
    _clear_session_cookies(response)
    return LogoutResponse()


@router.get("/me", response_model=AuthStatusResponse)
def current_user(context: AuthContext = Depends(require_auth_context)):
    return AuthStatusResponse(authenticated=True, user=_user_response(context.user))


@router.get("/verify", response_model=AuthStatusResponse)
def verify(context: AuthContext = Depends(require_auth_context)):
    return AuthStatusResponse(authenticated=True, user=_user_response(context.user))
