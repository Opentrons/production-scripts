from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from api.router import router as api_router
from api.routers import system
from modules.auth.dependencies import (
    CSRF_COOKIE_NAME,
    get_auth_service,
    require_authenticated_user,
    require_platform_access,
)
from modules.auth.routes import router as auth_router
from modules.auth.service import AuthService, AuthenticationError


def make_service(tmp_path: Path) -> AuthService:
    service = AuthService(
        db_path=tmp_path / "auth.sqlite3",
        jwt_secret="test-secret-" * 4,
        issuer="test-production-platform",
        audience="test-production-web",
        access_token_minutes=5,
        refresh_token_hours=1,
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
    assert session.session_expires_at - session.access_expires_at == timedelta(
        hours=167,
        minutes=40,
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


def test_data_center_client_endpoints_bypass_platform_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(system.health_service, "get_health_status", lambda: {"status": True, "services": {}})
    app = FastAPI()
    app.include_router(api_router, prefix="/api")
    client = TestClient(app)

    assert client.get("/api/health").status_code == 200
    assert client.post("/api/pull-folder").status_code == 422
    assert client.post("/api/upload-data", json={}).status_code == 422
    assert client.post("/api/upload-data/manual").status_code == 422


def test_device_operator_can_use_platform_but_not_device_control(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    service.create_user(
        username="device-control",
        password="device-control-password",
        display_name="设备操作员",
        role="device_operator",
    )
    app = FastAPI()
    protected = APIRouter(dependencies=[Depends(require_platform_access)])

    @protected.get("/health")
    def health():
        return {"success": True}

    @protected.get("/robots")
    def robots():
        return {"success": True}

    @protected.post("/robots/commands")
    def robot_command():
        return {"success": True}

    @protected.get("/robots/{ip}/control/summary")
    def robot_control_summary(ip: str):
        return {"success": True, "ip": ip}

    @protected.post("/robots/{ip}/control/home")
    def robot_control_home(ip: str):
        return {"success": True, "ip": ip}

    @protected.get("/data")
    def data():
        return {"success": True}

    @protected.get("/robots-private")
    def robots_private():
        return {"success": True}

    app.include_router(auth_router, prefix="/api")
    app.include_router(protected, prefix="/api")
    app.dependency_overrides[get_auth_service] = lambda: service
    client = TestClient(app)

    login = client.post(
        "/api/auth/login",
        json={"username": "device-control", "password": "device-control-password"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "device_operator"
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/robots").status_code == 200
    assert client.get("/api/data").status_code == 200
    assert client.get("/api/robots-private").status_code == 200
    assert client.get("/api/robots/192.168.1.10/control/summary").status_code == 200

    csrf_token = client.cookies.get(CSRF_COOKIE_NAME)
    assert csrf_token
    command = client.post(
        "/api/robots/commands",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert command.status_code == 200
    control = client.post(
        "/api/robots/192.168.1.10/control/home",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert control.status_code == 403
    assert control.json()["detail"] == {
        "code": "auth.permission_denied",
        "message": "当前账号无设备控制权限",
        "params": {},
    }

    english_control = client.post(
        "/api/robots/192.168.1.10/control/home",
        headers={"X-CSRF-Token": csrf_token, "Accept-Language": "en-US"},
    )
    assert english_control.status_code == 403
    assert english_control.json()["detail"]["code"] == "auth.permission_denied"
    assert english_control.json()["detail"]["message"] == "This account cannot use device controls."
