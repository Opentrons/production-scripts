from __future__ import annotations

import core.config as setting
from core import runtime_mode
from modules.auth.factory import create_auth_store
from modules.supplies.repository import SupplementaryMaterialRepository
from modules.supplies.runtime import configure_supplementary_material_repository
from modules.workflows.repository import WorkflowRepository
from modules.workflows.runtime import configure_workflow_repository


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


def test_simulating_mode_still_uses_fixture_devices(monkeypatch) -> None:
    monkeypatch.setattr(setting, "DEVICE_SCAN_MODE", "real")
    monkeypatch.setattr(runtime_mode, "is_simulating", lambda: True)

    assert setting.use_simulated_device_scan() is True


def test_sqlite_fallback_does_not_enable_fixture_devices(monkeypatch) -> None:
    monkeypatch.setattr(setting, "DEVICE_SCAN_MODE", "real")
    monkeypatch.setattr(runtime_mode, "is_simulating", lambda: False)
    monkeypatch.setattr(setting, "use_sqlite_persistence", lambda: True)

    assert setting.use_simulated_device_scan() is False


def test_sqlite_fallback_reconfigures_static_business_repositories(
    tmp_path,
    monkeypatch,
) -> None:
    db_root = tmp_path / "db"
    monkeypatch.setattr(setting, "DB_ROOT", db_root)
    monkeypatch.setattr(setting, "DB_BUSINESS_DIR", db_root / "business")
    monkeypatch.setattr(setting, "DB_SIMULATING_DIR", db_root / "simulating")
    runtime_mode._SIMULATING = False
    runtime_mode.set_sqlite_fallback(True, reason="test")

    try:
        supplies_repository = configure_supplementary_material_repository()
        workflow_repository = configure_workflow_repository()

        assert isinstance(supplies_repository, SupplementaryMaterialRepository)
        assert isinstance(workflow_repository, WorkflowRepository)
        assert supplies_repository.database_path.parent == db_root / "business"
        assert workflow_repository.store_path.parent == db_root / "business"
    finally:
        runtime_mode.set_sqlite_fallback(False)
        configure_supplementary_material_repository()
        configure_workflow_repository()
