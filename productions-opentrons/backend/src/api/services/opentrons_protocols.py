from __future__ import annotations

import json
from typing import Any

import settings as setting
from opentrons.opentrons_api.client import OpentronsHttpClient
from opentrons.opentrons_files.file_service import OpentronsFileService


def _client(ip: str, port: int | None = None) -> OpentronsHttpClient:
    return OpentronsHttpClient(ip, port or setting.ROBOT_HEALTH_PORT)


def list_protocols(ip: str, port: int | None = None) -> list[dict[str, Any]]:
    return _client(ip, port).list_protocols()


def get_protocol(ip: str, protocol_id: str, port: int | None = None) -> dict[str, Any]:
    return _client(ip, port).get_protocol(protocol_id)


def download_protocol_bundle(ip: str, protocol_id: str, port: int | None = None) -> tuple[str, bytes]:
    client = _client(ip, port)
    protocol = client.get_protocol(protocol_id)
    analyses = client.list_protocol_analyses(protocol_id)
    bundle = {
        "protocol": protocol,
        "analyses": analyses,
    }
    filename = f"{protocol_id}.protocol.json"
    return filename, json.dumps(bundle, indent=2, ensure_ascii=False).encode("utf-8")


def download_protocol_source(ip: str, protocol_id: str) -> tuple[str, bytes, str]:
    return OpentronsFileService(ip).download_protocol_source(protocol_id)


def upload_protocol(
    ip: str,
    files: list[tuple[str, bytes]],
    *,
    key: str | None = None,
    protocol_kind: str | None = None,
    port: int | None = None,
) -> dict[str, Any]:
    return _client(ip, port).upload_protocol(files, key=key, protocol_kind=protocol_kind)


def analyze_protocol(
    ip: str,
    protocol_id: str,
    *,
    body: dict[str, Any] | None = None,
    port: int | None = None,
) -> list[dict[str, Any]]:
    return _client(ip, port).analyze_protocol(protocol_id, body=body)


def list_protocol_analyses(
    ip: str,
    protocol_id: str,
    port: int | None = None,
) -> list[dict[str, Any]]:
    return _client(ip, port).list_protocol_analyses(protocol_id)


def list_runs(ip: str, port: int | None = None) -> list[dict[str, Any]]:
    return _client(ip, port).list_runs()


def create_and_play_run(
    ip: str,
    protocol_id: str,
    port: int | None = None,
) -> dict[str, Any]:
    client = _client(ip, port)
    run = client.create_run(protocol_id=protocol_id)
    run_id = run.get("id")
    if not run_id:
        raise ValueError("Run created without id")
    action = client.run_action(run_id, "play")
    return {"run": run, "action": action}


def run_control_action(
    ip: str,
    run_id: str,
    action_type: str,
    port: int | None = None,
) -> dict[str, Any]:
    return _client(ip, port).run_action(run_id, action_type)
