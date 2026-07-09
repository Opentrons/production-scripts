from __future__ import annotations

from typing import Any

import settings as setting
from opentrons.opentrons_api.client import OpentronsApiError, OpentronsHttpClient
from opentrons.opentrons_files.file_service import OpentronsFileService
from opentrons.opentrons_files.ssh_client import OpentronsSshClient, OpentronsSshError

from api.services.logging import logger


def _http_client(ip: str, port: int | None = None) -> OpentronsHttpClient:
    return OpentronsHttpClient(ip, port or setting.ROBOT_HEALTH_PORT)


def get_device_control_summary(ip: str, port: int | None = None) -> dict[str, Any]:
    client = _http_client(ip, port)
    ssh = OpentronsSshClient(ip)
    summary: dict[str, Any] = {
        "ip": ip,
        "port": port or setting.ROBOT_HEALTH_PORT,
        "http_connected": False,
        "ssh_connected": False,
        "health": None,
        "instruments": None,
        "modules": None,
        "positions": None,
        "errors": [],
    }

    try:
        summary["health"] = client.get_health()
        summary["http_connected"] = True
    except OpentronsApiError as exc:
        summary["errors"].append(f"HTTP health: {exc}")

    if summary["http_connected"]:
        for key, fetcher in (
            ("instruments", client.get_instruments),
            ("modules", client.get_modules),
            ("positions", client.get_robot_positions),
        ):
            try:
                summary[key] = fetcher()
            except OpentronsApiError as exc:
                summary["errors"].append(f"{key}: {exc}")
                try:
                    if key == "instruments":
                        summary[key] = client.get_pipettes()
                except OpentronsApiError as fallback_exc:
                    summary["errors"].append(f"pipettes: {fallback_exc}")

    try:
        ssh.test_connection()
        summary["ssh_connected"] = True
    except OpentronsSshError as exc:
        summary["errors"].append(f"SSH: {exc}")

    return summary


def home_robot(ip: str, *, target: str = "robot", mount: str | None = None, port: int | None = None) -> dict[str, Any]:
    client = _http_client(ip, port)
    return client.home_robot(target=target, mount=mount)


def move_robot(
    ip: str,
    *,
    target: str,
    point: list[float],
    mount: str,
    model: str | None = None,
    port: int | None = None,
) -> dict[str, Any]:
    client = _http_client(ip, port)
    return client.move_robot(target=target, point=point, mount=mount, model=model)


def reset_robot(ip: str, *, options: dict[str, bool] | None = None, port: int | None = None) -> dict[str, Any]:
    client = _http_client(ip, port)
    reset_options = options or {"tipLengths": True, "offsets": True, "runsHistory": True}
    return client.reset_settings(options=reset_options)


def reboot_robot(ip: str) -> dict[str, Any]:
    ssh = OpentronsSshClient(ip)
    ssh.reboot()
    logger.info(f"Reboot command sent to robot {ip}")
    return {"success": True, "message": "Reboot command sent"}


def list_robot_files(ip: str, path: str | None = None) -> dict[str, Any]:
    return OpentronsFileService(ip).list_directory(path)


def read_robot_file(ip: str, path: str) -> dict[str, Any]:
    return OpentronsFileService(ip).read_file(path)


def write_robot_file(ip: str, path: str, content: str, *, create_if_missing: bool = True) -> dict[str, Any]:
    return OpentronsFileService(ip).write_file(path, content, create_if_missing=create_if_missing)


def upload_robot_file(ip: str, path: str, content: bytes) -> dict[str, Any]:
    return OpentronsFileService(ip).upload_file(path, content)


def delete_robot_file(ip: str, path: str) -> dict[str, Any]:
    return OpentronsFileService(ip).delete_path(path)


def download_robot_file(ip: str, path: str) -> tuple[str, bytes, str]:
    return OpentronsFileService(ip).download_file(path)
