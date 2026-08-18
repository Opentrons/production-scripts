from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import core.config as setting
from modules.agent import attachment_store, download_store
from modules.agent.routes import download_agent_robot_testing_data
from modules.agent.tools import platform
from modules.robots import opentrons_control


def test_robot_testing_data_download_request_is_scoped_and_normalized(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(setting, "AGENT_ATTACHMENT_DIR", tmp_path / "attachments")
    monkeypatch.setattr(setting, "ROBOT_TESTING_DATA_DIR", "/data/testing_data")
    token = attachment_store.set_attachment_scope("user-1", set())
    try:
        result = download_store.create_robot_testing_data_request(
            "192.168.6.126",
            ["folder/result.csv", "/data/testing_data/folder/result.csv", "summary.json"],
        )
    finally:
        attachment_store.reset_attachment_scope(token)

    assert result["download_url"].startswith("/api/agent/downloads/testing-data/")
    assert result["paths"] == [
        "/data/testing_data/folder/result.csv",
        "/data/testing_data/summary.json",
    ]
    stored = download_store.resolve_robot_testing_data_request(result["download_id"], "user-1")
    assert stored["owner_id"] == "user-1"
    with pytest.raises(download_store.AgentDownloadNotFoundError):
        download_store.resolve_robot_testing_data_request(result["download_id"], "user-2")


def test_download_request_requires_interactive_user_scope(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(setting, "AGENT_ATTACHMENT_DIR", tmp_path / "attachments")

    with pytest.raises(attachment_store.AttachmentError, match="已登录"):
        download_store.create_robot_testing_data_request("192.168.6.126", ["result.csv"])


def test_platform_tool_lists_robot_testing_data(monkeypatch) -> None:
    monkeypatch.setattr(
        opentrons_control,
        "list_robot_testing_data",
        lambda ip, path: {"path": path or "/data/testing_data", "entries": [{"name": "result.csv"}], "ip": ip},
    )

    result = platform.list_robot_testing_data("192.168.6.126", "batch-1")

    assert result["ip"] == "192.168.6.126"
    assert result["path"] == "batch-1"


def test_agent_download_route_resolves_current_user_and_returns_zip(monkeypatch) -> None:
    monkeypatch.setattr(
        download_store,
        "resolve_robot_testing_data_request",
        lambda request_id, owner_id: {
            "id": request_id,
            "owner_id": owner_id,
            "ip": "192.168.6.126",
            "paths": ["/data/testing_data/result.csv"],
        },
    )
    monkeypatch.setattr(
        opentrons_control,
        "download_robot_testing_data",
        lambda ip, paths: ("testing-data.zip", f"{ip}:{paths[0]}".encode(), "application/zip"),
    )

    response = asyncio.run(
        download_agent_robot_testing_data("a" * 32, user=SimpleNamespace(id="user-1"))
    )

    assert response.media_type == "application/zip"
    assert response.headers["content-disposition"] == 'attachment; filename="testing-data.zip"'
    assert response.body.startswith(b"192.168.6.126:")
