from __future__ import annotations

import posixpath
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


def reset_robot(ip: str, *, axes: list[str], port: int | None = None) -> dict[str, Any]:
    client = _http_client(ip, port)
    return client.home_axes(axes=axes)


def _attached_jog_pipettes(client: OpentronsHttpClient) -> list[dict[str, Any]]:
    instruments = OpentronsHttpClient.unwrap_data(client.get_instruments())
    if not isinstance(instruments, list):
        return []
    return [
        instrument
        for instrument in instruments
        if isinstance(instrument, dict)
        and instrument.get("ok") is True
        and instrument.get("instrumentType") == "pipette"
        and instrument.get("mount") in {"left", "right"}
        and isinstance(instrument.get("instrumentName"), str)
    ]


def create_jog_run(ip: str, *, port: int | None = None) -> dict[str, Any]:
    client = _http_client(ip, port)
    pipette_load_warning: str | None = None
    try:
        attached_pipettes = _attached_jog_pipettes(client)
    except OpentronsApiError as exc:
        attached_pipettes = []
        pipette_load_warning = f"读取已安装移液器失败: {exc}"

    run_id = client.create_maintenance_run()
    loaded_pipettes: dict[str, dict[str, Any]] = {}
    try:
        for instrument in attached_pipettes:
            mount = str(instrument["mount"])
            pipette_id = f"jog-{mount}-pipette"
            client.load_pipette(
                run_id=run_id,
                pipette_name=str(instrument["instrumentName"]),
                mount=mount,
                pipette_id=pipette_id,
            )
            state = instrument.get("state")
            tip_detected = None
            if isinstance(state, dict):
                tip_detected = state.get("tipDetected", state.get("tip_detected"))
            loaded_pipettes[mount] = {
                "pipette_id": pipette_id,
                "name": instrument["instrumentName"],
                "model": instrument.get("instrumentModel"),
                "tip_detected": tip_detected,
            }
    except Exception:
        try:
            client.delete_maintenance_run(run_id)
        except Exception as cleanup_exc:
            logger.warning("Failed to clean Jog run %s after loading pipettes: %s", run_id, cleanup_exc)
        raise

    return {
        "run_id": run_id,
        "pipettes": loaded_pipettes,
        "pipette_load_warning": pipette_load_warning,
    }


def move_jog_robot(
    ip: str,
    *,
    run_id: str,
    direction: str,
    step_mm: float,
    mount: str,
    port: int | None = None,
) -> dict[str, Any]:
    mount_axis = {
        "left": "leftZ",
        "right": "rightZ",
        "gripper": "extensionZ",
    }.get(mount)
    if mount_axis is None:
        raise ValueError("不支持的 Jog Mount")
    direction_axis_map = {
        "up": {"y": step_mm},
        "down": {"y": -step_mm},
        "left": {"x": -step_mm},
        "right": {"x": step_mm},
        "z_up": {mount_axis: step_mm},
        "z_down": {mount_axis: -step_mm},
    }
    if mount in {"left", "right"}:
        plunger_axis = "leftPlunger" if mount == "left" else "rightPlunger"
        direction_axis_map.update(
            {
                "plunger_up": {plunger_axis: step_mm},
                "plunger_down": {plunger_axis: -step_mm},
            }
        )
    if direction not in direction_axis_map:
        raise ValueError("不支持的 Jog 方向")

    command = _http_client(ip, port).move_axes_relative(
        run_id=run_id,
        axis_map=direction_axis_map[direction],
    )
    return {
        "run_id": run_id,
        "direction": direction,
        "step_mm": step_mm,
        "mount": mount,
        "axis_map": direction_axis_map[direction],
        "command": command,
    }


def control_jog_gripper(
    ip: str,
    *,
    run_id: str,
    action: str,
    port: int | None = None,
) -> dict[str, Any]:
    client = _http_client(ip, port)
    if action == "grip":
        command = client.close_gripper_jaw(run_id=run_id)
    elif action == "ungrip":
        command = client.open_gripper_jaw(run_id=run_id)
    else:
        raise ValueError("不支持的 Gripper 操作")
    return {"run_id": run_id, "action": action, "command": command}


def drop_jog_tip(
    ip: str,
    *,
    run_id: str,
    pipette_id: str,
    home_after: bool | None = None,
    port: int | None = None,
) -> dict[str, Any]:
    command = _http_client(ip, port).drop_tip_in_place(
        run_id=run_id,
        pipette_id=pipette_id,
        home_after=home_after,
    )
    return {"run_id": run_id, "pipette_id": pipette_id, "command": command}


def delete_jog_run(ip: str, *, run_id: str, port: int | None = None) -> dict[str, Any]:
    result = _http_client(ip, port).delete_maintenance_run(run_id)
    return {"run_id": run_id, "released": True, "result": result}


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


def _normalize_testing_data_path(path: str | None, *, allow_root: bool) -> str:
    root = posixpath.normpath(setting.ROBOT_TESTING_DATA_DIR)
    raw_path = (path or root).strip()
    if not raw_path.startswith("/"):
        raw_path = posixpath.join(root, raw_path)
    normalized = posixpath.normpath(raw_path)
    if normalized != root and not normalized.startswith(f"{root.rstrip('/')}/"):
        raise ValueError(f"路径必须位于 {root} 下")
    if not allow_root and normalized == root:
        raise ValueError("不能选择测试数据根目录")
    return normalized


def _normalize_testing_data_paths(paths: list[str]) -> list[str]:
    normalized: list[str] = []
    for path in paths:
        item = _normalize_testing_data_path(path, allow_root=False)
        if item not in normalized:
            normalized.append(item)
    if not normalized:
        raise ValueError("请至少选择一个文件或文件夹")
    return normalized


def list_robot_testing_data(ip: str, path: str | None = None) -> dict[str, Any]:
    remote_path = _normalize_testing_data_path(path, allow_root=True)
    result = OpentronsFileService(ip).list_directory(remote_path)
    result["root_path"] = posixpath.normpath(setting.ROBOT_TESTING_DATA_DIR)
    return result


def download_robot_testing_data(ip: str, paths: list[str]) -> tuple[str, bytes, str]:
    selected_paths = _normalize_testing_data_paths(paths)
    root_path = posixpath.normpath(setting.ROBOT_TESTING_DATA_DIR)
    content = OpentronsFileService(ip).download_files_as_zip(selected_paths, root_path=root_path)
    filename = f"testing-data-{ip.replace('.', '-')}.zip"
    return filename, content, "application/zip"


def delete_robot_testing_data(ip: str, paths: list[str]) -> dict[str, Any]:
    selected_paths = _normalize_testing_data_paths(paths)
    deleted_paths = OpentronsFileService(ip).delete_paths(selected_paths)
    return {
        "deleted_paths": deleted_paths,
        "deleted_count": len(deleted_paths),
    }
