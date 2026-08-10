from __future__ import annotations

from pathlib import Path

from core import runtime_mode
from modules.robots import robots
from modules.system import simulating, simulating_seed
from modules.system import messages as message_service
from modules.uploads import upload_records
import core.config as setting


def test_enable_simulating_seeds_fake_devices_and_uploads(tmp_path: Path, monkeypatch) -> None:
    db_root = tmp_path / "db"
    monkeypatch.setattr(setting, "DB_ROOT", db_root)
    monkeypatch.setattr(setting, "DB_BUSINESS_DIR", db_root / "business")
    monkeypatch.setattr(setting, "DB_SIMULATING_DIR", db_root / "simulating")
    runtime_mode._SIMULATING = None
    robots._robot_scan_memory_cache.clear()

    status = simulating.set_enabled(True)
    assert status["simulating"] is True
    assert status["seed"]["seeded"] is True
    assert (db_root / "simulating" / "platform.sqlite3").exists()

    scan = robots.load_robot_scan_cache(31950)
    assert scan["online_count"] == 3
    assert scan["online_robots"][0]["name"].startswith("SIM-")

    records = upload_records.get_upload_records(page=1, page_size=20)
    assert records["total"] >= 5
    assert records["records"][0]["file_desc"]["sn"]

    inbox = message_service.get_messages()
    assert inbox["total"] >= 1
    assert inbox["messages"][0]["title"].startswith("[Simulating]")


def test_simulating_scan_skips_network(monkeypatch) -> None:
    monkeypatch.setattr(setting, "use_sqlite_persistence", lambda: True)
    monkeypatch.setattr(simulating_seed, "ensure_simulating_seed", lambda: {"seeded": True})

    import asyncio

    result = asyncio.run(robots.scan_robots(31950))
    assert result["online_count"] == 3
    assert result["simulating"] is True
