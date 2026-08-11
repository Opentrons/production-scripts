from __future__ import annotations

from pathlib import Path

import pytest

from core import runtime_mode
from core.sqlite_store import SqliteDocumentStore
import core.config as setting
from modules.robots import version_records


def test_collect_robot_versions_includes_required_subsystems(monkeypatch) -> None:
    class FakeClient:
        def get_health(self):
            return {
                "name": "RightFlex",
                "robot_model": "OT-3 Standard",
                "robot_serial": "FLXA1001",
                "api_version": "9.1.1",
                "system_version": "v9.1.1",
            }

        def request(self, method, path):
            assert (method, path) == ("GET", "/subsystems/status")
            return {
                "data": [
                    {
                        "name": name,
                        "current_fw_version": "69",
                        "next_fw_version": "69",
                        "revision": "C2.0",
                        "ok": True,
                        "fw_update_needed": False,
                    }
                    for name in ("gantry_x", "gripper", "gantry_y", "head", "rear_panel")
                ]
            }

    monkeypatch.setattr(version_records, "_http_client", lambda ip, port: FakeClient())
    monkeypatch.setattr(version_records, "_read_test_version", lambda ip: "N/A")

    result = version_records._collect_robot_versions("192.168.0.123", 31950)

    assert result["barcode"] == "FLXA1001"
    assert result["test_version"] == "N/A"
    assert [item["name"] for item in result["subsystems"]] == [
        "gantry_x",
        "gantry_y",
        "head",
        "rear_panel",
    ]


def test_current_robot_versions_allows_missing_barcode(monkeypatch) -> None:
    class FakeClient:
        def get_health(self):
            return {"name": "RightFlex", "robot_model": "OT-3 Standard"}

        def request(self, method, path):
            assert (method, path) == ("GET", "/subsystems/status")
            return {
                "data": [
                    {"name": name, "current_fw_version": "69", "revision": "C2.0"}
                    for name in version_records.ROBOT_SUBSYSTEMS
                ]
            }

    monkeypatch.setattr(setting, "use_sqlite_persistence", lambda: False)
    monkeypatch.setattr(version_records, "_http_client", lambda ip, port: FakeClient())
    monkeypatch.setattr(version_records, "_read_test_version", lambda ip: "N/A")

    result = version_records.get_current_robot_versions("192.168.0.123", 31950)

    assert result["barcode"] == "N/A"
    assert [item["firmware_version"] for item in result["subsystems"]] == ["69"] * 4


def test_collect_robot_versions_uses_update_server_barcode(monkeypatch) -> None:
    class FakeClient:
        def get_health(self):
            return {"name": "GRAV1", "robot_model": "OT-3 Standard"}

        def get_update_server_health(self):
            return {"serialNumber": "FLXA1020230817003"}

        def request(self, method, path):
            assert (method, path) == ("GET", "/subsystems/status")
            return {"data": []}

    monkeypatch.setattr(version_records, "_http_client", lambda ip, port: FakeClient())
    monkeypatch.setattr(version_records, "_read_test_version", lambda ip: "N/A")

    result = version_records._collect_robot_versions("192.168.0.123", 31950)

    assert result["barcode"] == "FLXA1020230817003"


def test_capture_rejects_missing_barcode_before_persisting(monkeypatch) -> None:
    monkeypatch.setattr(
        version_records,
        "_collect_versions",
        lambda *args, **kwargs: {"barcode": "N/A", "test_version": "N/A"},
    )
    product = version_records.list_products()["products"][0]

    with pytest.raises(RuntimeError, match="无法保存版本记录"):
        version_records.capture_version(
            ip="192.168.0.123",
            port=31950,
            product_type="robot",
            test_name=product["test_names"][0],
        )


def test_capture_merges_tests_for_the_same_barcode(tmp_path: Path, monkeypatch) -> None:
    collection = SqliteDocumentStore(tmp_path / "versions.sqlite3")["versions"]
    captured = {
        "barcode": "FLXA1001",
        "test_version": "hardware-test-1.2.3",
        "robot": {"name": "RightFlex"},
        "subsystems": [],
    }
    monkeypatch.setattr(version_records, "_get_collection", lambda: collection)
    monkeypatch.setattr(version_records, "_collect_versions", lambda *args: captured)

    product = version_records.list_products()["products"][0]
    version_records.capture_version(
        ip="192.168.0.123",
        port=31950,
        product_type="robot",
        test_name=product["test_names"][0],
    )
    version_records.capture_version(
        ip="192.168.0.123",
        port=31950,
        product_type="robot",
        test_name=product["test_names"][1],
    )

    documents = list(collection.find({}))
    assert len(documents) == 1
    assert documents[0]["barcode"] == "FLXA1001"
    assert set(documents[0]["tests"]) == {"test1", "test2"}
    assert documents[0]["tests"]["test1"]["sn"] == "FLXA1001"
    assert documents[0]["tests"]["test2"]["test_name"] == product["test_names"][1]


def test_business_capture_uses_business_sqlite(tmp_path: Path, monkeypatch) -> None:
    db_root = tmp_path / "db"
    monkeypatch.setattr(setting, "DB_ROOT", db_root)
    monkeypatch.setattr(setting, "DB_BUSINESS_DIR", db_root / "business")
    monkeypatch.setattr(setting, "DB_SIMULATING_DIR", db_root / "simulating")
    runtime_mode._SIMULATING = None
    runtime_mode.set_simulating(False)

    captured = {
        "barcode": "FLXA1001",
        "test_version": "hardware-test-1.2.3",
        "robot": {"name": "RightFlex"},
        "subsystems": [],
    }
    monkeypatch.setattr(version_records, "_collect_versions", lambda *args, **kwargs: captured)

    product = version_records.list_products()["products"][0]
    result = version_records.capture_version(
        ip="192.168.0.123",
        port=31950,
        product_type="robot",
        test_name=product["test_names"][0],
    )
    history = version_records.list_history()

    assert result["storage"] == "sqlite"
    assert history["storage"] == "sqlite"
    assert history["total"] == 1
    assert history["records"][0]["barcode"] == "FLXA1001"
    assert (db_root / "business" / "platform.sqlite3").exists()
    assert not (db_root / "simulating" / "platform.sqlite3").exists()


def test_simulating_capture_uses_sqlite_profile(tmp_path: Path, monkeypatch) -> None:
    db_root = tmp_path / "db"
    monkeypatch.setattr(setting, "DB_ROOT", db_root)
    monkeypatch.setattr(setting, "DB_BUSINESS_DIR", db_root / "business")
    monkeypatch.setattr(setting, "DB_SIMULATING_DIR", db_root / "simulating")
    runtime_mode._SIMULATING = None
    runtime_mode.set_simulating(True)

    try:
        product = version_records.list_products()["products"][0]
        result = version_records.capture_version(
            ip="192.168.6.11",
            port=31950,
            product_type="robot",
            test_name=product["test_names"][0],
        )
        history = version_records.list_history()

        assert result["storage"] == "sqlite"
        assert result["test"]["test_version"] == "SIM-TEST-1.0"
        assert history["total"] == 1
        assert history["records"][0]["tests"]["test1"]["sn"] == "FLXA1020250101001"
        assert (db_root / "simulating" / "platform.sqlite3").exists()
    finally:
        runtime_mode.set_simulating(False)
