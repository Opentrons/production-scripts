from __future__ import annotations

from pathlib import Path

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
    monkeypatch.setattr(version_records, "_read_robot_serial_ssh", lambda ip: "")

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
    monkeypatch.setattr(version_records, "_read_robot_serial_ssh", lambda ip: "")

    result = version_records._collect_robot_versions("192.168.0.123", 31950)

    assert result["barcode"] == "FLXA1020230817003"


def test_capture_allows_missing_barcode_as_na(tmp_path: Path, monkeypatch) -> None:
    collection = SqliteDocumentStore(tmp_path / "versions-na.sqlite3")["versions"]
    monkeypatch.setattr(version_records, "_resolve_test_commit_id", lambda ref: f"sha-{ref}")
    monkeypatch.setattr(version_records, "_get_collection", lambda: collection)
    monkeypatch.setattr(
        version_records,
        "_collect_versions",
        lambda *args, **kwargs: {
            "barcode": "N/A",
            "test_version": "hardware-test-1.2.3",
            "robot": {"system_version": "v9.1.1"},
            "subsystems": [],
        },
    )
    product = version_records.list_products()["products"][0]

    result = version_records.capture_version(
        ip="192.168.0.123",
        port=31950,
        product_type="robot",
        test_name=product["test_names"][0],
    )

    assert result["test"]["sn"] == "N/A"
    assert result["test"]["test_version"] == "hardware-test-1.2.3"
    assert result["record"]["barcode"] == "N/A"
    documents = list(collection.find({}))
    assert len(documents) == 1
    assert documents[0]["barcode"] == "N/A"


def test_capture_merges_tests_for_the_same_barcode(tmp_path: Path, monkeypatch) -> None:
    collection = SqliteDocumentStore(tmp_path / "versions.sqlite3")["versions"]
    monkeypatch.setattr(version_records, "_resolve_test_commit_id", lambda ref: f"sha-{ref}")
    captured = {
        "barcode": "FLXA1001",
        "test_version": "SERIAL\nmp.robot.diagnostics-24.08.05-1",
        "robot": {"name": "RightFlex"},
        "subsystems": [],
    }
    monkeypatch.setattr(version_records, "_get_collection", lambda: collection)
    monkeypatch.setattr(version_records, "_collect_versions", lambda *args, **kwargs: captured)

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
    assert documents[0]["tests"]["test1"]["test_version"] == "mp.robot.diagnostics-24.08.05-1"
    assert documents[0]["tests"]["test1"]["test_commit_hash"] == "mp.robot.diagnostics-24.08.05-1"
    assert documents[0]["tests"]["test1"]["test_commit_id"] == "sha-mp.robot.diagnostics-24.08.05-1"
    assert documents[0]["tests"]["test2"]["test_name"] == product["test_names"][1]


def test_business_capture_uses_mongodb(tmp_path: Path, monkeypatch) -> None:
    collection = SqliteDocumentStore(tmp_path / "mongo-double.sqlite3")["versions"]
    monkeypatch.setattr(version_records, "_resolve_test_commit_id", lambda ref: f"sha-{ref}")
    captured = {
        "barcode": "FLXA1001",
        "test_version": "hardware-test-1.2.3",
        "robot": {"name": "RightFlex"},
        "subsystems": [],
    }
    monkeypatch.setattr(setting, "use_sqlite_persistence", lambda: False)
    monkeypatch.setattr(version_records, "_get_collection", lambda: collection)
    monkeypatch.setattr(version_records, "_collect_versions", lambda *args, **kwargs: captured)

    product = version_records.list_products()["products"][0]
    result = version_records.capture_version(
        ip="192.168.0.123",
        port=31950,
        product_type="robot",
        test_name=product["test_names"][0],
    )
    history = version_records.list_history()

    assert result["storage"] == "mongodb"
    assert history["storage"] == "mongodb"
    assert history["total"] == 1
    assert history["records"][0]["barcode"] == "FLXA1001"


def test_delete_history_record_removes_version_document(tmp_path: Path, monkeypatch) -> None:
    collection = SqliteDocumentStore(tmp_path / "versions-delete.sqlite3")["versions"]
    monkeypatch.setattr(version_records, "_get_collection", lambda: collection)
    collection.insert_one(
        {
            "_id": "version-record-1",
            "barcode": "FLXA1001",
            "product_type": "robot",
            "tests": {},
            "updated_at": "2026-09-21T00:00:00+00:00",
        }
    )

    deleted = version_records.delete_history_record("version-record-1")
    missing = version_records.delete_history_record("version-record-1")

    assert deleted == {"success": True, "id": "version-record-1"}
    assert missing == {"success": False, "id": "version-record-1"}
    assert version_records.list_history()["total"] == 0


def test_simulating_capture_still_uses_mongodb_storage(tmp_path: Path, monkeypatch) -> None:
    collection = SqliteDocumentStore(tmp_path / "mongo-double.sqlite3")["versions"]
    db_root = tmp_path / "db"
    monkeypatch.setattr(version_records, "_resolve_test_commit_id", lambda ref: f"sha-{ref}")
    monkeypatch.setattr(setting, "DB_ROOT", db_root)
    monkeypatch.setattr(setting, "DB_BUSINESS_DIR", db_root / "business")
    monkeypatch.setattr(setting, "DB_SIMULATING_DIR", db_root / "simulating")
    monkeypatch.setattr(version_records, "_get_collection", lambda: collection)
    monkeypatch.setattr(
        version_records,
        "_collect_versions",
        lambda *args, **kwargs: {
            "barcode": "FLXA1020250101001",
            "test_version": "SIM-TEST-1.0",
            "robot": {"name": "SimFlex"},
            "subsystems": [],
        },
    )
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

        assert result["storage"] == "mongodb"
        assert result["test"]["test_version"] == "SIM-TEST-1.0"
        assert history["storage"] == "mongodb"
        assert history["total"] == 1
        assert history["records"][0]["tests"]["test1"]["sn"] == "FLXA1020250101001"
        assert not (db_root / "simulating" / "platform.sqlite3").exists()
    finally:
        runtime_mode.set_simulating(False)


def test_test_version_normalization_and_legacy_history_enrichment(tmp_path: Path, monkeypatch) -> None:
    collection = SqliteDocumentStore(tmp_path / "versions-legacy.sqlite3")["versions"]
    monkeypatch.setattr(version_records, "_get_collection", lambda: collection)
    monkeypatch.setattr(
        version_records,
        "_resolve_test_commit_id",
        lambda ref: "4225b5a50ae98e4e0358454802b0b8b15716d803"
        if ref == "mp.gripper.diagnostics-24.08.05-1"
        else None,
    )
    collection.insert_one(
        {
            "_id": "legacy",
            "barcode": "GRPV1",
            "product_type": "gripper",
            "tests": {
                "test1": {
                    "test_name": "1. DIAGNOSTICS SOFTWARE FIRMWARE",
                    "sn": "GRPV1",
                    "robot_ip": "192.168.0.5",
                    "test_version": "SERIAL\nmp.gripper.diagnostics-24.08.05-1",
                    "queried_at": "2026-09-21T00:00:00+00:00",
                }
            },
            "updated_at": "2026-09-21T00:00:00+00:00",
        }
    )

    history = version_records.list_history()
    test = history["records"][0]["tests"]["test1"]

    assert version_records._normalize_test_version("SERIAL\nmp.gripper.diagnostics-24.08.05-1") == "mp.gripper.diagnostics-24.08.05-1"
    assert test["test_version"] == "mp.gripper.diagnostics-24.08.05-1"
    assert test["test_commit_hash"] == "mp.gripper.diagnostics-24.08.05-1"
    assert test["test_commit_id"] == "4225b5a50ae98e4e0358454802b0b8b15716d803"


def test_comparison_rule_crud_uses_mongodb_collection(tmp_path: Path, monkeypatch) -> None:
    collection = SqliteDocumentStore(tmp_path / "rules.sqlite3")["rules"]
    monkeypatch.setattr(version_records, "_get_rule_collection", lambda: collection)

    payload = {
        "product_type": "robot",
        "product_name": "Robot",
        "duro_product_id": "duro-product",
        "duro_product_label": "Duro Product",
        "duro_parent_id": "parent",
        "duro_parent_label": "Software / Firmware",
        "test_names": ["1. Z STAGE SUBASSEMBLY TEST"],
        "fields": ["test_version", "app_version", "firmware"],
    }

    created = version_records.create_comparison_rule(payload)
    assert created["product_type"] == "robot"
    assert created["fields"] == ["test_version", "app_version", "firmware"]

    listed = version_records.list_comparison_rules()
    assert listed["storage"] == "mongodb"
    assert listed["total"] == 1

    updated = version_records.update_comparison_rule(
        created["_id"],
        {**payload, "fields": ["test_version"]},
    )
    assert updated["fields"] == ["test_version"]

    deleted = version_records.delete_comparison_rule(created["_id"])
    assert deleted["success"] is True
    assert version_records.list_comparison_rules()["total"] == 0
