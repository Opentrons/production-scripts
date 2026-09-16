from __future__ import annotations

import io
import zipfile

import pytest

from modules.robots import app_log_analysis


def _sample_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "opentrons-logs/api.log",
            "Sep 01 21:49:31.364540 host opentrons-api[1]: Error 1004 COMMAND_TIMED_OUT "
            "(CommandTimedOutError): Sensor Read from node timed out\n",
        )
        archive.writestr("opentrons-logs/server.log", "Sep 01 21:49:30.000000 host uvicorn: ok\n")
    return buffer.getvalue()


def test_analyze_app_log_zip_returns_summary(tmp_path, monkeypatch):
    summary = app_log_analysis.analyze_app_log_zip(
        _sample_zip(),
        robot_ip="192.168.6.10",
        archive_name="opentrons-app-logs-192.168.6.10.zip",
        device_name="FLEX-1",
    )
    assert summary["ip"] == "192.168.6.10"
    assert summary["archive"] == "opentrons-app-logs-192.168.6.10.zip"
    assert "error" in summary


def test_save_and_list_analysis_records(monkeypatch):
    stored: list[dict] = []

    class FakeCollection:
        def insert_one(self, document):
            stored.append(dict(document))
            return None

        def count_documents(self, query):
            if not query:
                return len(stored)
            ip = query.get("robot_ip")
            return sum(1 for item in stored if item.get("robot_ip") == ip)

        def find(self, query):
            items = stored
            if query.get("robot_ip"):
                items = [item for item in items if item.get("robot_ip") == query["robot_ip"]]

            class Cursor(list):
                def sort(self, *_args, **_kwargs):
                    return self

                def skip(self, count):
                    return Cursor(self[count:])

                def limit(self, count):
                    return Cursor(self[:count])

            return Cursor(list(reversed(items)))

        def find_one(self, query):
            for item in stored:
                if item.get("_id") == query.get("_id"):
                    return dict(item)
            return None

        def create_index(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(app_log_analysis, "_get_collection", lambda: FakeCollection())
    monkeypatch.setattr(
        app_log_analysis,
        "analyze_app_log_zip",
        lambda *_args, **_kwargs: {
            "time": "2026-09-01T21:49:31Z",
            "error": "Sensor Read timed out",
            "code": "1004",
            "code_name": "COMMAND_TIMED_OUT",
        },
    )

    record = app_log_analysis.analyze_and_store_app_log_zip(
        b"unused",
        robot_ip="192.168.6.10",
        archive_name="demo.zip",
        device_name="FLEX-1",
    )
    assert record["status"] == "completed"
    assert record["summary"]["code"] == "1004"

    listed = app_log_analysis.list_analysis_records(robot_ip="192.168.6.10")
    assert listed["total"] == 1
    assert listed["records"][0]["_id"] == record["_id"]

    fetched = app_log_analysis.get_analysis_record(record["_id"])
    assert fetched["device_name"] == "FLEX-1"


def test_analyze_and_store_persists_failure(monkeypatch):
    stored: list[dict] = []

    class FakeCollection:
        def insert_one(self, document):
            stored.append(dict(document))

        def create_index(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(app_log_analysis, "_get_collection", lambda: FakeCollection())
    monkeypatch.setattr(
        app_log_analysis,
        "analyze_app_log_zip",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    record = app_log_analysis.analyze_and_store_app_log_zip(
        b"unused",
        robot_ip="192.168.6.11",
        archive_name="demo.zip",
    )
    assert record["status"] == "failed"
    assert "boom" in record["error"]
    assert len(stored) == 1
