from __future__ import annotations

from pathlib import Path

from core import runtime_mode
from core.sqlite_store import SqliteDocumentStore
from modules.robots import robots
import core.config as setting


def test_simulating_mode_switches_active_db_dir(tmp_path: Path, monkeypatch) -> None:
    db_root = tmp_path / "db"
    monkeypatch.setattr(setting, "DB_ROOT", db_root)
    monkeypatch.setattr(setting, "DB_BUSINESS_DIR", db_root / "business")
    monkeypatch.setattr(setting, "DB_SIMULATING_DIR", db_root / "simulating")
    runtime_mode._SIMULATING = None
    runtime_mode.set_sqlite_fallback(False)

    assert runtime_mode.is_simulating() is False
    assert setting.get_active_db_dir() == db_root / "business"

    runtime_mode.set_simulating(True)
    assert runtime_mode.is_simulating() is True
    assert setting.get_active_db_dir() == db_root / "simulating"
    assert setting.use_sqlite_persistence() is True

    runtime_mode.set_simulating(False)
    assert setting.use_sqlite_persistence() is False


def test_dev_fallback_uses_business_sqlite_without_simulating(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_root = tmp_path / "db"
    monkeypatch.setattr(setting, "DB_ROOT", db_root)
    monkeypatch.setattr(setting, "DB_BUSINESS_DIR", db_root / "business")
    monkeypatch.setattr(setting, "DB_SIMULATING_DIR", db_root / "simulating")
    monkeypatch.setattr(setting, "DEVICE_SCAN_MODE", "real")
    runtime_mode._SIMULATING = False
    runtime_mode.set_sqlite_fallback(True, reason="MongoDB unavailable in test")

    try:
        status = runtime_mode.get_simulating_status()
        assert setting.use_sqlite_persistence() is True
        assert setting.get_active_db_dir() == db_root / "business"
        assert setting.use_simulated_device_scan() is False
        assert status["simulating"] is False
        assert status["persistence"] == "sqlite"
        assert status["sqlite_fallback"] is True
        assert status["sqlite_fallback_reason"] == "MongoDB unavailable in test"
    finally:
        runtime_mode.set_sqlite_fallback(False)


def test_sqlite_platform_store_round_trip(tmp_path: Path, monkeypatch) -> None:
    db_root = tmp_path / "db"
    monkeypatch.setattr(setting, "DB_ROOT", db_root)
    monkeypatch.setattr(setting, "DB_BUSINESS_DIR", db_root / "business")
    monkeypatch.setattr(setting, "DB_SIMULATING_DIR", db_root / "simulating")
    runtime_mode._SIMULATING = None
    runtime_mode.set_simulating(True)

    store = SqliteDocumentStore(setting.resolve_sqlite_path("platform.sqlite3"))
    collection = store["robot_scan_gateways"]
    collection.update_one(
        {"gateway": "192.168.6.1"},
        {"$set": {"gateway": "192.168.6.1", "updated_at": "now"}},
        upsert=True,
    )
    docs = list(collection.find({}).sort("gateway", 1))
    assert docs[0]["gateway"] == "192.168.6.1"


def test_robot_scan_gateways_use_sqlite_when_simulating(tmp_path: Path, monkeypatch) -> None:
    db_root = tmp_path / "db"
    monkeypatch.setattr(setting, "DB_ROOT", db_root)
    monkeypatch.setattr(setting, "DB_BUSINESS_DIR", db_root / "business")
    monkeypatch.setattr(setting, "DB_SIMULATING_DIR", db_root / "simulating")
    runtime_mode._SIMULATING = None
    runtime_mode.set_simulating(True)

    try:
        robots.add_scan_gateway("192.168.7.1")
        listed = robots.list_scan_gateways()
        assert listed["gateways"][0]["gateway"] == "192.168.7.1"
        assert (db_root / "simulating" / "platform.sqlite3").exists()
    finally:
        runtime_mode.set_simulating(False)


def test_migrate_legacy_sqlite_files(tmp_path: Path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    db_root = tmp_path / "db"
    data_dir.mkdir()
    legacy = data_dir / "workflows.sqlite3"
    legacy.write_text("legacy", encoding="utf-8")

    monkeypatch.setattr(setting, "DATA_DIR", data_dir)
    monkeypatch.setattr(setting, "DB_ROOT", db_root)
    monkeypatch.setattr(setting, "DB_BUSINESS_DIR", db_root / "business")
    monkeypatch.setattr(setting, "DB_SIMULATING_DIR", db_root / "simulating")

    runtime_mode.ensure_db_layout()
    destination = db_root / "business" / "workflows.sqlite3"
    assert destination.exists()
    assert destination.read_text(encoding="utf-8") == "legacy"
    assert not legacy.exists()
