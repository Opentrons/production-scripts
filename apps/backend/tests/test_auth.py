from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from modules.auth.dependencies import (
    CSRF_COOKIE_NAME,
    get_auth_service,
    require_authenticated_user,
)
from modules.auth.routes import router as auth_router
from modules.auth.service import AuthService, AuthenticationError


def make_service(tmp_path: Path) -> AuthService:
    service = AuthService(
        db_path=tmp_path / "auth.sqlite3",
        jwt_secret="test-secret-" * 4,
        issuer="test-production-platform",
        audience="test-production-web",
        access_token_minutes=20,
        refresh_token_hours=8,
    )
    service.initialize()
    return service


def create_user(service: AuthService, username: str = "operator"):
    return service.create_user(
        username=username,
        password="correct-horse-battery-staple",
        display_name="Production Operator",
        role="operator",
    )


def test_auth_service_issues_rotates_and_revokes_session(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    user = create_user(service)

    session = service.login(
        user.username,
        "correct-horse-battery-staple",
        user_agent="pytest",
        ip_address="127.0.0.1",
    )
    verified_user, claims = service.verify_access_token(session.access_token)
    assert verified_user.id == user.id
    assert claims["role"] == "operator"
    assert claims["csrf"] == session.csrf_token

    refreshed = service.refresh(session.refresh_token)
    assert refreshed.refresh_token != session.refresh_token
    assert refreshed.access_token != session.access_token
    assert service.verify_access_token(refreshed.access_token)[0].id == user.id

    service.revoke_refresh_token(refreshed.refresh_token)
    with pytest.raises(AuthenticationError, match="no longer active"):
        service.verify_access_token(refreshed.access_token)


def test_reused_refresh_token_revokes_session(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    user = create_user(service)
    session = service.issue_session(user, user_agent="pytest", ip_address="127.0.0.1")
    refreshed = service.refresh(session.refresh_token)

    with pytest.raises(AuthenticationError, match="already been used"):
        service.refresh(session.refresh_token)
    with pytest.raises(AuthenticationError, match="no longer active"):
        service.verify_access_token(refreshed.access_token)


def test_invalid_credentials_are_rejected(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    create_user(service)

    with pytest.raises(AuthenticationError, match="Invalid username or password"):
        service.authenticate("operator", "incorrect-password")
    with pytest.raises(AuthenticationError, match="Invalid username or password"):
        service.authenticate("missing-user", "incorrect-password")


def test_expired_access_token_is_rejected(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.access_token_minutes = -1
    user = create_user(service)
    session = service.issue_session(user, user_agent="pytest", ip_address="127.0.0.1")

    with pytest.raises(AuthenticationError, match="Invalid or expired"):
        service.verify_access_token(session.access_token)


def test_auth_routes_protect_api_and_require_csrf(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    create_user(service)
    app = FastAPI()
    protected = APIRouter(dependencies=[Depends(require_authenticated_user)])

    @protected.get("/protected")
    def read_protected():
        return {"success": True}

    @protected.post("/protected")
    def update_protected():
        return {"success": True}

    app.include_router(auth_router, prefix="/api")
    app.include_router(protected, prefix="/api")
    app.dependency_overrides[get_auth_service] = lambda: service
    client = TestClient(app)

    assert client.get("/api/protected").status_code == 401
    login = client.post(
        "/api/auth/login",
        json={"username": "operator", "password": "correct-horse-battery-staple"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["display_name"] == "Production Operator"
    assert "production_access_token" not in login.json()
    assert client.get("/api/protected").status_code == 200
    assert client.post("/api/protected").status_code == 403

    csrf_token = client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf_token
    assert client.post(
        "/api/protected",
        headers={"X-CSRF-Token": csrf_token},
    ).status_code == 200

    refresh = client.post(
        "/api/auth/refresh",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert refresh.status_code == 200
    next_csrf_token = client.cookies.get(CSRF_COOKIE_NAME)
    assert next_csrf_token and next_csrf_token != csrf_token

    logout = client.post(
        "/api/auth/logout",
        headers={"X-CSRF-Token": next_csrf_token},
    )
    assert logout.status_code == 200
    assert client.get("/api/protected").status_code == 401
