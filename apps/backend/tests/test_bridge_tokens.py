from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from functools import partial
from threading import Barrier, RLock
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.sqlite_store import SqliteDocumentStore
from modules.auth.dependencies import require_authenticated_user
from modules.auth.store import AuthUser
from modules.bridge_tokens.models import AllocationRecord
from modules.bridge_tokens.configuration import (
    BridgeTokenConfigurationService,
    BridgeTokenConfigurationUpdate,
    BridgeTokenStoredConfiguration,
    MongoBridgeTokenConfigurationRepository,
)
from modules.bridge_tokens.client import BridgefloodsAuthenticationError, BridgefloodsClient
from modules.bridge_tokens.emailer import BridgeEmailSettings
from modules.bridge_tokens.repository import BridgeTokenRepository
from modules.bridge_tokens.routes import (
    get_bridge_token_configuration_service,
    get_bridge_token_service,
    router as bridge_token_router,
)
from modules.bridge_tokens.scheduler import due_task_slots
from modules.bridge_tokens.service import (
    BridgeTokenService,
    BridgeTokenSettings,
    WhitelistEntry,
    allocate_budget,
    entry_matches_key,
)


class FakeConfigurationRepository:
    def __init__(self) -> None:
        self.value: BridgeTokenStoredConfiguration | None = None
        self.initialized = False

    def initialize(self) -> None:
        self.initialized = True

    def get(self) -> BridgeTokenStoredConfiguration | None:
        return self.value

    def save(
        self,
        configuration: BridgeTokenStoredConfiguration,
    ) -> BridgeTokenStoredConfiguration:
        self.value = configuration
        return configuration

    def save_credentials(self, expected, *, base_url, access_token, refresh_token):
        if self.value is None or (
            self.value.base_url, self.value.access_token, self.value.refresh_token
        ) != (expected.base_url, expected.access_token, expected.refresh_token):
            return False
        self.value = self.value.model_copy(update={
            "base_url": base_url, "access_token": access_token, "refresh_token": refresh_token,
        })
        return True


class FakeEmailSender:
    configured = True

    def __init__(self) -> None:
        self.messages: list[tuple[str, str, str]] = []

    def send(self, to_address: str, subject: str, body: str) -> None:
        self.messages.append((to_address, subject, body))


class FakeBridgeClient:
    def __init__(self, keys: list[dict], balance: float | None = 500) -> None:
        self.keys = [dict(item) for item in keys]
        self.balance = balance
        self.updates: list[tuple[str, float, str | None]] = []

    def list_keys(self, page_size: int = 100) -> list[dict]:
        return [dict(item) for item in self.keys]

    def get_profile(self) -> dict:
        return {} if self.balance is None else {"balance": self.balance}

    def get_usage_stats(self, *, start_date: str, end_date: str, key_id: str) -> dict:
        return {"total_actual_cost": 10 if key_id == "andy-key" else 1}

    def update_key_quota(self, key_id: str, quota: float, *, status: str | None = None):
        self.updates.append((key_id, quota, status))
        key = next(item for item in self.keys if item["id"] == key_id)
        key["quota"] = quota
        if status:
            key["status"] = status
        return dict(key)


def auth_user(username: str = "andy", role: str = "operator") -> AuthUser:
    return AuthUser(
        id=f"user-{username}",
        username=username,
        display_name=username.title(),
        role=role,
        password_hash="unused",
        disabled=False,
        token_version=1,
    )


def write_whitelist(path: Path) -> None:
    path.write_text(
        "key_id,key_name,email,display_name,enabled\n"
        "andy-key,Andy,andy@example.com,Andy,true\n"
        "other-key,Other,other@example.com,Other,true\n"
        "disabled-key,Disabled,disabled@example.com,Disabled,false\n",
        encoding="utf-8",
    )


def build_service(
    tmp_path: Path,
    client: FakeBridgeClient,
) -> tuple[BridgeTokenService, BridgeTokenRepository, FakeEmailSender]:
    whitelist = tmp_path / "whitelist.csv"
    write_whitelist(whitelist)
    store = SqliteDocumentStore(tmp_path / "bridge.sqlite3")
    repository = BridgeTokenRepository(store.__getitem__)
    email_sender = FakeEmailSender()
    service = BridgeTokenService(
        settings=BridgeTokenSettings(
            base_url="https://example.invalid/api/v1",
            access_token="configured-for-test",
            refresh_token="",
            whitelist_path=whitelist,
            admin_email="admin@example.com",
        ),
        repository=repository,
        email_sender=email_sender,  # type: ignore[arg-type]
        client_factory=lambda: client,  # type: ignore[arg-type]
    )
    service.initialize()
    return service, repository, email_sender


def build_configuration_service(tmp_path: Path):
    repository = FakeConfigurationRepository()
    applied: list[BridgeTokenStoredConfiguration] = []
    token_settings = BridgeTokenSettings(
        base_url="https://api.bridgefloods.example/api/v1",
        access_token="env-access-token",
        refresh_token="env-refresh-token",
        whitelist_path=tmp_path / "whitelist.csv",
        automation_enabled=False,
    )
    email_settings = BridgeEmailSettings(
        provider="gmail",
        from_address="automation@example.com",
        gmail_token_path=tmp_path / "gmail-token.json",
        smtp_host="",
        smtp_port=587,
        smtp_username="",
        smtp_password="",
        smtp_use_ssl=False,
        smtp_starttls=True,
    )
    service = BridgeTokenConfigurationService(
        repository=repository,
        base_token_settings=token_settings,
        base_email_settings=email_settings,
        apply_configuration=lambda stored, _token, _email: applied.append(stored),
        validate_credentials=lambda _stored: None,
    )
    return service, repository, applied


def test_key_id_is_authoritative_when_present() -> None:
    entry = WhitelistEntry(key_id="expected", key_name="Andy", enabled=True)
    assert entry_matches_key(entry, {"id": "expected", "name": "Other"}) is True
    assert entry_matches_key(entry, {"id": "different", "name": "Andy"}) is False


def test_allocate_budget_preserves_total_and_minimum() -> None:
    result = allocate_budget(
        ["a", "b", "c"],
        {"a": 10, "b": 30, "c": 60},
        2000,
        50,
    )
    assert sum(result.values()) == pytest.approx(2000)
    assert min(result.values()) >= 50
    assert result["c"] > result["b"] > result["a"]


def test_authenticated_user_sees_all_enabled_live_balances(tmp_path: Path) -> None:
    client = FakeBridgeClient(
        [
            {"id": "andy-key", "name": "Andy", "quota": 200, "quota_used": 75, "status": "active"},
            {"id": "other-key", "name": "Other", "quota": 900, "quota_used": 1, "status": "active"},
        ]
    )
    service, repository, _ = build_service(tmp_path, client)
    repository.save_record(
        AllocationRecord(
            key_id="other-key",
            key_name="Other",
            action="weekly_allocation",
            amount=900,
            quota_before=0,
            quota_after=900,
            quota_used=1,
            remaining_after=899,
            success=True,
        )
    )

    dashboard = service.current_user_dashboard(auth_user(), refresh=True)
    records = service.list_user_records(
        auth_user(),
        action=None,
        page=1,
        page_size=20,
    )

    assert dashboard.live is True
    assert dashboard.total_remaining == 1024
    assert [item.key_name for item in dashboard.keys] == ["Andy", "Other"]
    assert dashboard.keys[0].email_hint == "a**y@example.com"
    assert records.total == 1
    assert records.records[0].key_name == "Other"


def test_monitor_topup_is_verified_and_persisted(tmp_path: Path) -> None:
    client = FakeBridgeClient(
        [
            {
                "id": "andy-key",
                "name": "Andy",
                "quota": 200,
                "quota_used": 175,
                "status": "quota_exhausted",
            },
            {"id": "other-key", "name": "Other", "quota": 200, "quota_used": 10, "status": "active"},
        ],
        balance=500,
    )
    service, _, _ = build_service(tmp_path, client)

    result = service.run_monitor()
    records = service.list_user_records(
        auth_user(),
        action="low_balance_topup",
        page=1,
        page_size=20,
    )

    assert result.checked == 2
    assert result.eligible == 1
    assert result.updated == 1
    assert client.updates == [("andy-key", 300, "active")]
    assert records.total == 1
    assert records.records[0].success is True
    assert records.records[0].amount == 100
    assert records.records[0].remaining_after == 125


def test_monitor_fails_closed_when_main_balance_is_unknown(tmp_path: Path) -> None:
    client = FakeBridgeClient(
        [{"id": "andy-key", "name": "Andy", "quota": 100, "quota_used": 80, "status": "active"}],
        balance=None,
    )
    service, _, _ = build_service(tmp_path, client)

    result = service.run_monitor()

    assert result.eligible == 1
    assert result.updated == 0
    assert client.updates == []
    assert "Main account balance could not be confirmed" in result.errors


def test_weekly_allocation_preserves_usage_and_total_budget(tmp_path: Path) -> None:
    client = FakeBridgeClient(
        [
            {"id": "andy-key", "name": "Andy", "quota": 300, "quota_used": 75, "status": "active"},
            {"id": "other-key", "name": "Other", "quota": 300, "quota_used": 10, "status": "active"},
            {"id": "disabled-key", "name": "Disabled", "quota": 10, "quota_used": 9, "status": "active"},
        ]
    )
    service, _, _ = build_service(tmp_path, client)

    result = service.run_weekly_allocation()

    assert result.updated == 2
    targets = {key_id: quota for key_id, quota, _ in client.updates}
    assert set(targets) == {"andy-key", "other-key"}
    assert (targets["andy-key"] - 75) + (targets["other-key"] - 10) == pytest.approx(2000)
    assert next(item for item in client.keys if item["id"] == "andy-key")["quota_used"] == 75


def test_main_balance_alert_is_suppressed_until_recovery(tmp_path: Path) -> None:
    client = FakeBridgeClient(
        [
            {"id": "andy-key", "name": "Andy", "quota": 200, "quota_used": 10, "status": "active"},
            {"id": "other-key", "name": "Other", "quota": 200, "quota_used": 10, "status": "active"},
        ],
        balance=49,
    )
    service, _, email_sender = build_service(tmp_path, client)

    service.run_monitor()
    service.run_monitor()
    assert [subject for _, subject, _ in email_sender.messages] == [
        "Kimmy，小桥token余额告急，记得充值。"
    ]

    client.balance = 51
    service.run_monitor()
    client.balance = 49
    service.run_monitor()
    assert [subject for _, subject, _ in email_sender.messages].count(
        "Kimmy，小桥token余额告急，记得充值。"
    ) == 2


def test_reminders_merge_multiple_keys_for_same_user_and_email(tmp_path: Path) -> None:
    client = FakeBridgeClient(
        [
            {"id": "andy-key-1", "name": "Andy One", "quota": 100, "quota_used": 20, "status": "active"},
            {"id": "andy-key-2", "name": "Andy Two", "quota": 200, "quota_used": 50, "status": "active"},
        ]
    )
    service, _, email_sender = build_service(tmp_path, client)
    service.settings.whitelist_path.write_text(
        "key_id,key_name,email,display_name,enabled\n"
        "andy-key-1,Andy One,andy@example.com,Andy,true\n"
        "andy-key-2,Andy Two,andy@example.com,Andy,true\n",
        encoding="utf-8",
    )

    result = service.run_weekly_reminders()
    user_deliveries = [message for message in email_sender.messages if message[0] == "andy@example.com"]
    records = service.list_user_records(
        auth_user(),
        action="weekly_reminder",
        page=1,
        page_size=20,
    )

    assert result.emails_sent == 1
    assert len(user_deliveries) == 1
    assert "Andy One" in user_deliveries[0][2]
    assert "Andy Two" in user_deliveries[0][2]
    assert records.total == 2
    assert all(record.email_sent for record in records.records)


def test_bridge_routes_use_the_authenticated_user(tmp_path: Path) -> None:
    client_backend = FakeBridgeClient(
        [{"id": "andy-key", "name": "Andy", "quota": 120, "quota_used": 20, "status": "active"}]
    )
    service, _, _ = build_service(tmp_path, client_backend)
    app = FastAPI()
    app.include_router(bridge_token_router)
    app.dependency_overrides[require_authenticated_user] = auth_user
    app.dependency_overrides[get_bridge_token_service] = lambda: service

    response = TestClient(app).get("/bridge-tokens/me")

    assert response.status_code == 200
    assert response.json()["username"] == "andy"
    assert response.json()["total_remaining"] == 100


def test_configuration_migrates_env_and_never_returns_secrets(tmp_path: Path) -> None:
    service, repository, applied = build_configuration_service(tmp_path)

    stored = service.initialize()
    response = service.get_configuration()
    payload = response.model_dump()

    assert repository.initialized is True
    assert stored.access_token == "env-access-token"
    assert stored.refresh_token == "env-refresh-token"
    assert response.access_token_configured is True
    assert response.refresh_token_configured is True
    assert "access_token" not in payload
    assert "refresh_token" not in payload
    assert "smtp_password" not in payload
    assert applied == [stored]


def test_configuration_update_retains_blank_secrets_and_hot_applies(tmp_path: Path) -> None:
    service, repository, applied = build_configuration_service(tmp_path)
    service.initialize()
    payload = BridgeTokenConfigurationUpdate(
        automation_enabled=True,
        base_url="https://api.bridgefloods.example/api/v2",
        timezone="Asia/Shanghai",
        quota_threshold=35,
        quota_increment=125,
        main_balance_alert_threshold=40,
        weekly_token_budget=2500,
        allocation_lookback_days=21,
        min_weekly_allocation=60,
        min_rebalance_remaining=25,
        reminder_subject="Bridge token reminder",
        admin_email="admin@example.com",
        email_provider="gmail",
        email_from="automation@example.com",
        smtp_host="",
        smtp_port=587,
        smtp_username="",
        smtp_use_ssl=False,
        smtp_starttls=True,
        access_token="",
        refresh_token=None,
        smtp_password="",
    )

    response = service.update_configuration(payload, updated_by="admin")

    assert repository.value is not None
    assert repository.value.access_token == "env-access-token"
    assert repository.value.refresh_token == "env-refresh-token"
    assert repository.value.weekly_token_budget == 2500
    assert repository.value.automation_enabled is True
    assert response.updated_by == "admin"
    assert applied[-1] == repository.value


def test_automation_toggle_persists_and_hot_applies(tmp_path: Path) -> None:
    service, repository, applied = build_configuration_service(tmp_path)
    service.initialize()

    response = service.update_automation(True, updated_by="admin")

    assert repository.value is not None
    assert repository.value.automation_enabled is True
    assert repository.value.updated_by == "admin"
    assert response.automation_enabled is True
    assert applied[-1] == repository.value


def test_configuration_routes_require_admin(tmp_path: Path) -> None:
    configuration_service, repository, applied = build_configuration_service(tmp_path)
    configuration_service.initialize()
    app = FastAPI()
    app.include_router(bridge_token_router)
    app.dependency_overrides[get_bridge_token_configuration_service] = (
        lambda: configuration_service
    )
    app.dependency_overrides[require_authenticated_user] = lambda: auth_user(
        "viewer", role="viewer"
    )
    client = TestClient(app)

    assert client.get("/bridge-tokens/configuration").status_code == 403
    assert client.patch(
        "/bridge-tokens/configuration/automation",
        json={"automation_enabled": True},
    ).status_code == 403

    app.dependency_overrides[require_authenticated_user] = lambda: auth_user(
        role="admin"
    )
    response = client.get("/bridge-tokens/configuration")
    assert response.status_code == 200
    assert response.json()["access_token_configured"] is True
    assert "access_token" not in response.json()

    response = client.patch(
        "/bridge-tokens/configuration/automation",
        json={"automation_enabled": True},
    )
    assert response.status_code == 200
    assert response.json()["automation_enabled"] is True
    assert repository.value is not None
    assert repository.value.automation_enabled is True
    assert applied[-1] == repository.value


def test_due_slots_use_beijing_week_and_half_hour() -> None:
    now = datetime(2026, 9, 3, 10, 17, tzinfo=ZoneInfo("Asia/Shanghai"))
    tasks = due_task_slots(now)

    assert ("weekly_allocation", "2026-08-31") in tasks
    assert ("weekly_reminder", "2026-08-31") in tasks
    assert ("weekly_rebalance", "2026-08-31") in tasks
    assert ("monitor", "2026-09-03T10:00:00+08:00") in tasks


def test_only_weekly_allocation_gets_bounded_scheduled_retries(tmp_path: Path) -> None:
    store = SqliteDocumentStore(tmp_path / "retry.sqlite3")
    repository = BridgeTokenRepository(store.__getitem__)
    repository.initialize()

    assert repository.claim_run(action="weekly_allocation", slot="2026-08-31") is True
    repository.finish_run(
        action="weekly_allocation",
        slot="2026-08-31",
        summary={"errors": ["network"]},
    )
    assert repository.claim_run(action="weekly_allocation", slot="2026-08-31") is False

    runs = store[BridgeTokenRepository.RUNS]
    runs.update_one(
        {"_id": "weekly_allocation:2026-08-31"},
        {"$set": {"next_retry_at": "2000-01-01T00:00:00+00:00"}},
    )
    assert repository.claim_run(action="weekly_allocation", slot="2026-08-31") is True
    repository.finish_run(
        action="weekly_allocation",
        slot="2026-08-31",
        summary={"errors": ["network"]},
    )
    runs.update_one(
        {"_id": "weekly_allocation:2026-08-31"},
        {"$set": {"next_retry_at": "2000-01-01T00:00:00+00:00"}},
    )
    assert repository.claim_run(action="weekly_allocation", slot="2026-08-31") is True
    repository.finish_run(
        action="weekly_allocation",
        slot="2026-08-31",
        summary={"errors": ["network"]},
    )
    runs.update_one(
        {"_id": "weekly_allocation:2026-08-31"},
        {"$set": {"next_retry_at": "2000-01-01T00:00:00+00:00"}},
    )
    assert repository.claim_run(action="weekly_allocation", slot="2026-08-31") is False

    assert repository.claim_run(action="weekly_reminder", slot="2026-09-02") is True
    repository.finish_run(
        action="weekly_reminder",
        slot="2026-09-02",
        summary={"errors": ["delivery"]},
    )
    assert repository.claim_run(action="weekly_reminder", slot="2026-09-02") is False


class RotatingAuthServer:
    """The upstream contract: 24h AT, single-use RT renewed for 30 days."""
    def __init__(self):
        self.now = datetime(2026, 11, 1, tzinfo=timezone.utc)
        self.access_expires = self.now + timedelta(days=1)
        self.refresh_expires = self.now + timedelta(days=30)
        self.access_token = "TEST_ACCESS_0_SECRET"
        self.refresh_token = "TEST_REFRESH_0_SECRET"
        self.refresh_calls = 0
        self.barrier = None
        self.profile_fails = False
        self._lock = RLock()

    def request(self, method, url, **kwargs):
        if url.endswith("/auth/refresh"):
            assert "Authorization" not in kwargs["headers"]
            with self._lock:
                self.refresh_calls += 1
                if kwargs["json"]["refresh_token"] != self.refresh_token or self.now >= self.refresh_expires:
                    return httpx.Response(401, json={"code": 401, "message": "invalid refresh token"})
                self.access_token = f"TEST_ACCESS_{self.refresh_calls}_SECRET"
                self.refresh_token = f"TEST_REFRESH_{self.refresh_calls}_SECRET"
                self.access_expires = self.now + timedelta(days=1)
                self.refresh_expires = self.now + timedelta(days=30)
                return httpx.Response(200, json={"code": 0, "data": {
                    "access_token": self.access_token, "refresh_token": self.refresh_token,
                    "expires_in": 86400,
                }})
        valid = kwargs["headers"].get("Authorization") == f"Bearer {self.access_token}" and self.now < self.access_expires
        if not valid:
            if self.barrier is not None:
                self.barrier.wait(timeout=5)
            return httpx.Response(401, json={"code": "TOKEN_EXPIRED"})
        if url.endswith("/user/profile"):
            if self.profile_fails:
                return httpx.Response(503)
            return httpx.Response(200, json={"code": 0, "data": {"balance": 500}})
        return httpx.Response(200, json={"code": 0, "data": [
            {"id": "andy-key", "name": "Andy", "quota": 100, "quota_used": 5},
            {"id": "other-key", "name": "Other", "quota": 100, "quota_used": 10},
        ]})


@pytest.fixture
def rolling_credentials(tmp_path, monkeypatch):
    server = RotatingAuthServer()
    monkeypatch.setattr("modules.bridge_tokens.client.httpx.request", server.request)
    cfg, _, applied = build_configuration_service(tmp_path)
    cfg.base_token_settings = replace(
        cfg.base_token_settings, access_token=server.access_token, refresh_token=server.refresh_token,
    )
    write_whitelist(cfg.base_token_settings.whitelist_path)
    store = SqliteDocumentStore(tmp_path / "rolling-credentials.sqlite3")
    repository = MongoBridgeTokenConfigurationRepository()
    collection = store["bridge_token_configuration"]
    original_update = collection.update_one
    def update_one(query, update, **kwargs):
        # Mongo stores BSON dates; the local durable test store serializes JSON.
        encoded = json.loads(json.dumps(update, default=lambda value: value.isoformat()))
        return original_update(query, encoded, **kwargs)
    monkeypatch.setattr(collection, "update_one", update_one)
    monkeypatch.setattr(
        collection, "replace_one",
        lambda query, document, **kwargs: update_one(query, {"$set": document}, **kwargs),
        raising=False,
    )
    monkeypatch.setattr(repository, "_collection", lambda: collection)
    cfg.repository = repository
    cfg._validate_credentials = cfg._validate_bridge_credentials
    cfg.initialize()
    def make_service(configuration_service=cfg):
        settings, _ = configuration_service._runtime_settings(repository.get())
        service = BridgeTokenService(
            settings=settings, repository=BridgeTokenRepository(store.__getitem__),
            email_sender=FakeEmailSender(), token_refresher=configuration_service.refresh_credentials,
        )
        service.initialize()
        return service
    return server, cfg, make_service, applied


def test_weekly_page_visits_survive_restarts_and_slide_refresh_for_more_than_30_days(rolling_credentials):
    server, cfg, make_service, _ = rolling_credentials
    start = server.now
    for week in range(1, 9):
        server.now = start + timedelta(weeks=week)
        restarted = BridgeTokenConfigurationService(
            repository=cfg.repository, base_token_settings=cfg.base_token_settings,
            base_email_settings=cfg.base_email_settings, apply_configuration=lambda *args: None,
        )
        restarted.initialize()
        dashboard = make_service(restarted).current_user_dashboard(auth_user(), refresh=True)
        assert dashboard.live is True
        assert dashboard.error == ""
        assert restarted.repository.get().access_token == server.access_token
        assert restarted.repository.get().refresh_token == server.refresh_token
        assert server.refresh_expires == server.now + timedelta(days=30)
        assert server.refresh_calls == week
        assert restarted.repository.get().automation_enabled is False


@pytest.mark.parametrize("shared_client", [True, False])
def test_concurrent_expired_requests_rotate_only_once(rolling_credentials, shared_client):
    server, cfg, make_service, _ = rolling_credentials
    service = make_service()
    server.now += timedelta(days=7)
    server.barrier = Barrier(6)
    if shared_client:
        clients = [service._default_client()] * 6
    else:
        clients = [make_service()._default_client() for _ in range(6)]
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(lambda client: client.list_keys(), clients))
    assert all(len(result) == 2 for result in results)
    assert server.refresh_calls == 1
    assert cfg.repository.get().refresh_token == server.refresh_token


def test_configuration_validation_saves_rotated_tokens_before_applying_settings(rolling_credentials):
    server, cfg, _, applied = rolling_credentials
    server.now += timedelta(days=7)
    cfg.update_automation(True, updated_by="admin")
    assert cfg.repository.get().refresh_token == server.refresh_token
    assert cfg.repository.get().access_token == server.access_token
    assert applied[-1].refresh_token == server.refresh_token
    assert server.refresh_calls == 1


def test_failed_profile_validation_keeps_successfully_rotated_pair(rolling_credentials):
    server, cfg, _, _ = rolling_credentials
    server.now += timedelta(days=7)
    server.profile_fails = True
    with pytest.raises(ValueError):
        cfg.update_automation(True, updated_by="admin")
    assert cfg.repository.get().automation_enabled is False
    assert cfg.repository.get().refresh_token == server.refresh_token
    server.profile_fails = False
    cfg.update_automation(True, updated_by="admin")
    assert cfg.repository.get().automation_enabled is True
    assert server.refresh_calls == 1


def test_editing_non_secret_configuration_retains_latest_credentials(rolling_credentials):
    server, cfg, make_service, _ = rolling_credentials
    server.now += timedelta(days=7)
    assert make_service().current_user_dashboard(auth_user()).live
    payload = BridgeTokenConfigurationUpdate.model_validate({
        **cfg.get_configuration().model_dump(), "quota_threshold": 42,
    })
    cfg.update_configuration(payload, updated_by="admin")
    assert cfg.repository.get().refresh_token == server.refresh_token
    assert cfg.repository.get().quota_threshold == 42
    assert make_service().current_user_dashboard(auth_user()).live
    assert server.refresh_calls == 1


def test_expired_refresh_token_is_reported_without_erasing_snapshots(rolling_credentials, caplog):
    server, cfg, make_service, _ = rolling_credentials
    service = make_service()
    assert service.current_user_dashboard(auth_user()).live
    old_token = cfg.repository.get().refresh_token
    server.now += timedelta(days=31)
    dashboard = service.current_user_dashboard(auth_user())
    assert dashboard.error == "authentication_required"
    assert dashboard.live is False
    assert dashboard.total_remaining == 185
    assert server.refresh_calls == 1
    assert cfg.repository.get().refresh_token == old_token
    assert old_token not in caplog.text


def test_temporary_storage_failure_retries_saving_without_consuming_refresh_again(rolling_credentials, monkeypatch):
    server, cfg, make_service, _ = rolling_credentials
    service = make_service()
    server.now += timedelta(days=7)
    original = cfg.repository.save_credentials
    def broken_save(*args, **kwargs):
        raise RuntimeError("database unavailable")
    monkeypatch.setattr(cfg.repository, "save_credentials", broken_save)
    dashboard = service.current_user_dashboard(auth_user())
    assert dashboard.error == "credential_save_failed"
    assert server.refresh_calls == 1
    monkeypatch.setattr(cfg.repository, "save_credentials", original)
    dashboard = service.current_user_dashboard(auth_user())
    assert dashboard.live
    assert cfg.repository.get().refresh_token == server.refresh_token
    assert server.refresh_calls == 1


def test_late_rotation_cannot_overwrite_manually_replaced_credentials(rolling_credentials):
    _, cfg, _, _ = rolling_credentials
    original = cfg.repository.get()
    manual = original.model_copy(update={"access_token": "manual-at", "refresh_token": "manual-rt", "quota_threshold": 37})
    cfg.repository.save(manual)
    assert cfg.repository.save_credentials(
        original, base_url=original.base_url, access_token="late-at", refresh_token="late-rt",
    ) is False
    stored = cfg.repository.get()
    assert stored.refresh_token == "manual-rt"
    assert stored.quota_threshold == 37


def test_stale_client_can_adopt_and_then_renew_an_already_expired_stored_pair(rolling_credentials):
    server, _, make_service, _ = rolling_credentials
    stale = make_service()
    server.now += timedelta(days=7)
    assert make_service().current_user_dashboard(auth_user()).live
    server.now += timedelta(days=7)
    assert stale.current_user_dashboard(auth_user()).live
    assert server.refresh_calls == 2


def test_refresh_token_alone_can_restore_balance(rolling_credentials):
    server, cfg, make_service, _ = rolling_credentials
    cfg.repository.save(cfg.repository.get().model_copy(update={"access_token": ""}))
    assert make_service().current_user_dashboard(auth_user()).live
    assert cfg.repository.get().access_token == server.access_token
    assert server.refresh_calls == 1


def test_rejected_renewed_access_token_has_bounded_retries(rolling_credentials, monkeypatch):
    server, cfg, _, _ = rolling_credentials
    original_request = server.request
    def rejected(method, url, **kwargs):
        if url.endswith("/auth/refresh"):
            return original_request(method, url, **kwargs)
        return httpx.Response(401, json={"code": "TOKEN_EXPIRED"})
    monkeypatch.setattr("modules.bridge_tokens.client.httpx.request", rejected)
    current = cfg.repository.get()
    client = BridgefloodsClient(
        base_url=current.base_url, access_token=current.access_token, refresh_token=current.refresh_token,
        refresh_handler=partial(cfg.refresh_credentials, current.base_url),
    )
    with pytest.raises(BridgefloodsAuthenticationError):
        client.list_keys()
    assert server.refresh_calls == 2


def test_expired_bridge_credentials_return_a_dashboard_error_without_platform_logout(rolling_credentials):
    server, _, make_service, _ = rolling_credentials
    service = make_service()
    assert service.current_user_dashboard(auth_user()).live
    server.now += timedelta(days=31)
    app = FastAPI()
    app.include_router(bridge_token_router)
    app.dependency_overrides[get_bridge_token_service] = lambda: service
    app.dependency_overrides[require_authenticated_user] = auth_user
    with TestClient(app) as client:
        response = client.get("/bridge-tokens/me")
    assert response.status_code == 200
    assert response.json()["error"] == "authentication_required"
    assert response.json()["total_remaining"] == 185
    assert "TEST_REFRESH_" not in response.text
    assert "TEST_ACCESS_" not in response.text


def test_unavailable_storage_is_detected_before_consuming_refresh_token(rolling_credentials, monkeypatch):
    server, cfg, make_service, _ = rolling_credentials
    service = make_service()
    server.now += timedelta(days=7)
    def unavailable():
        raise RuntimeError("database unavailable")
    monkeypatch.setattr(cfg.repository, "get", unavailable)
    assert service.current_user_dashboard(auth_user()).error == "credential_save_failed"
    assert server.refresh_calls == 0
