from __future__ import annotations

import core.config as setting
from modules.auth.factory import create_auth_store


def test_auth_storage_is_independent_from_business_simulation(tmp_path, monkeypatch) -> None:
    auth_path = tmp_path / "auth.sqlite3"
    monkeypatch.setattr(setting, "AUTH_STORAGE", "sqlite")
    monkeypatch.setattr(setting, "AUTH_DB_PATH", auth_path)
    monkeypatch.setattr(setting, "use_sqlite_persistence", lambda: False)

    store = create_auth_store()

    assert store.path == auth_path


def test_real_device_scan_is_independent_from_sqlite_auth(monkeypatch) -> None:
    monkeypatch.setattr(setting, "DEVICE_SCAN_MODE", "real")
    monkeypatch.setattr(setting, "use_sqlite_persistence", lambda: False)

    assert setting.use_simulated_device_scan() is False


def test_legacy_simulating_mode_still_uses_fixture_devices(monkeypatch) -> None:
    monkeypatch.setattr(setting, "DEVICE_SCAN_MODE", "real")
    monkeypatch.setattr(setting, "use_sqlite_persistence", lambda: True)

    assert setting.use_simulated_device_scan() is True
