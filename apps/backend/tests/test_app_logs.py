from __future__ import annotations

import io
import zipfile

import pytest

from modules.robots import app_logs
from modules.robots.api_client.client import OpentronsApiError


class FakeResponse:
    def __init__(self, content: bytes):
        self.content = content


class FakeClient:
    def __init__(self, health=None, by_path=None, fail_paths=None):
        self._health = health if health is not None else {
            "name": "Flex",
            "logs": ["/logs/api.log", "/logs/server.log"],
        }
        self._by_path = by_path or {}
        self._fail_paths = fail_paths or set()

    def get_health(self):
        if "health" in self._fail_paths:
            raise OpentronsApiError("health request failed")
        return self._health

    def request_raw(self, method, path):
        if path in self._fail_paths:
            raise OpentronsApiError(f"fetch failed: {path}")
        return FakeResponse(self._by_path.get(path, f"content of {path}".encode("utf-8")))


def test_collect_bundles_health_logs(monkeypatch):
    client = FakeClient(by_path={
        "/logs/api.log": b"api log body",
        "/logs/server.log": b"server log body",
    })
    monkeypatch.setattr(app_logs, "OpentronsHttpClient", lambda ip, port: client)

    zip_bytes, filename = app_logs.collect_opentrons_app_logs("192.168.6.123", 31950)

    assert filename.startswith("opentrons-app-logs-192.168.6.123-")
    assert filename.endswith(".zip")
    archive = zipfile.ZipFile(io.BytesIO(zip_bytes))
    names = archive.namelist()
    assert "opentrons-logs/api.log" in names
    assert "opentrons-logs/server.log" in names
    assert archive.read("opentrons-logs/api.log") == b"api log body"
    assert archive.read("opentrons-logs/server.log") == b"server log body"


def test_collect_skips_single_missing_log(monkeypatch):
    client = FakeClient(
        health={"logs": ["/logs/api.log", "/logs/server.log"]},
        fail_paths={"/logs/server.log"},
    )
    monkeypatch.setattr(app_logs, "OpentronsHttpClient", lambda ip, port: client)

    zip_bytes, _ = app_logs.collect_opentrons_app_logs("192.168.6.123", 31950)

    archive = zipfile.ZipFile(io.BytesIO(zip_bytes))
    assert archive.namelist() == ["opentrons-logs/api.log"]


def test_collect_falls_back_to_identifiers(monkeypatch):
    client = FakeClient(health={"name": "Flex", "robot_model": "OT-3 Standard"})
    monkeypatch.setattr(app_logs, "OpentronsHttpClient", lambda ip, port: client)

    zip_bytes, _ = app_logs.collect_opentrons_app_logs("192.168.6.123", 31950)

    archive = zipfile.ZipFile(io.BytesIO(zip_bytes))
    names = archive.namelist()
    assert "opentrons-logs/api.log" in names
    assert "opentrons-logs/server.log" in names
    assert any(name.endswith("touchscreen.log") for name in names)


def test_collect_raises_when_robot_unreachable(monkeypatch):
    client = FakeClient(fail_paths={"health"})
    monkeypatch.setattr(app_logs, "OpentronsHttpClient", lambda ip, port: client)

    with pytest.raises(OpentronsApiError):
        app_logs.collect_opentrons_app_logs("192.168.6.123", 31950)


def test_collect_raises_when_no_logs_available(monkeypatch):
    client = FakeClient(health={"name": "Flex", "logs": []})
    monkeypatch.setattr(app_logs, "OpentronsHttpClient", lambda ip, port: client)
    monkeypatch.setattr(app_logs, "FALLBACK_LOG_IDENTIFIERS", [])

    with pytest.raises(ValueError):
        app_logs.collect_opentrons_app_logs("192.168.6.123", 31950)
