"""Provision robot / instrument / module barcodes via SSH (Opentrons factory scripts)."""

from __future__ import annotations

import re
import shlex
import time
from typing import Any

import core.config as setting
from core.logging import get_logger
from core.sqlite_store import get_platform_store
from modules.robots.api_client.client import OpentronsApiError, OpentronsHttpClient
from modules.robots.files.ssh_client import OpentronsSshClient, OpentronsSshError
from modules.robots.identity import resolve_robot_serial

logger = get_logger(__name__)

TARGET_ROBOT = "robot"
TARGET_PIPETTE = "pipette"
TARGET_GRIPPER = "gripper"
TARGET_HEPAUV = "hepauv"

ROBOT_SERIAL_RE = re.compile(r"^FLX[\w]{1}[\d]{2}[\d]{8}[\d]{3}$")
PIPETTE_SERIAL_RE = re.compile(r"^P[\w\d]{3}V\d{2}[\w\d]{0,12}$")
GRIPPER_SERIAL_RE = re.compile(r"^GRPV\d{2}[\w\d]{0,12}$")
HEPAUV_SERIAL_RE = re.compile(r"^HUV\d{2}[\w\d]{0,12}$")

SIM_BARCODE_COLLECTION = "barcode_provision_state"

PROVISION_HINTS = {
    TARGET_ROBOT: "格式示例: FLXA1020230605001",
    TARGET_PIPETTE: "格式示例: P1KSV0120250101001（PNNNVMM + 序列）",
    TARGET_GRIPPER: "格式示例: GRPV0120250101001",
    TARGET_HEPAUV: "格式示例: HUV0120250101001",
}


def _http_client(ip: str, port: int | None = None) -> OpentronsHttpClient:
    return OpentronsHttpClient(ip, port or setting.ROBOT_HEALTH_PORT)


def _unwrap_list(payload: Any) -> list[Any]:
    data = OpentronsHttpClient.unwrap_data(payload)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("instruments", "modules", "data"):
            nested = data.get(key)
            if isinstance(nested, list):
                return nested
    return []


def _text(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float, bool)):
            return str(value)
    return ""


def _validate_serial(kind: str, serial: str) -> str | None:
    cleaned = serial.strip()
    if not cleaned:
        return "条码不能为空"
    checkers = {
        TARGET_ROBOT: (ROBOT_SERIAL_RE, PROVISION_HINTS[TARGET_ROBOT]),
        TARGET_PIPETTE: (PIPETTE_SERIAL_RE, PROVISION_HINTS[TARGET_PIPETTE]),
        TARGET_GRIPPER: (GRIPPER_SERIAL_RE, PROVISION_HINTS[TARGET_GRIPPER]),
        TARGET_HEPAUV: (HEPAUV_SERIAL_RE, PROVISION_HINTS[TARGET_HEPAUV]),
    }
    checker = checkers.get(kind)
    if not checker:
        return f"不支持的目标类型: {kind}"
    pattern, hint = checker
    if not pattern.match(cleaned):
        return f"条码格式不正确。{hint}"
    return None


def _is_hepauv_module(item: dict[str, Any]) -> bool:
    blob = " ".join(
        filter(
            None,
            [
                _text(item.get("moduleModel")),
                _text(item.get("moduleType")),
                _text(item.get("displayName")),
                _text(item.get("name")),
                _text(item.get("model")),
            ],
        )
    ).lower()
    return "hepa" in blob or "hepauv" in blob or "hepa/uv" in blob or "hepa_uv" in blob


def _sim_state_key(ip: str) -> str:
    return f"barcode:{ip}"


def _sim_collection():
    return get_platform_store()[SIM_BARCODE_COLLECTION]


def _load_sim_state(ip: str) -> dict[str, Any]:
    doc = _sim_collection().find_one({"_id": _sim_state_key(ip)})
    if isinstance(doc, dict) and isinstance(doc.get("targets"), dict):
        return dict(doc["targets"])
    defaults = {
        "robot": "FLXA1020250101001",
        "pipette:left": "P1KSV0120250101001",
        "pipette:right": "",
        "gripper": "GRPV0120250101001",
        "hepauv:1": "HUV0120250101001",
    }
    _sim_collection().update_one(
        {"_id": _sim_state_key(ip)},
        {"$set": {"_id": _sim_state_key(ip), "targets": defaults, "ip": ip}},
        upsert=True,
    )
    return defaults


def _save_sim_state(ip: str, targets: dict[str, Any]) -> None:
    _sim_collection().update_one(
        {"_id": _sim_state_key(ip)},
        {"$set": {"_id": _sim_state_key(ip), "targets": targets, "ip": ip}},
        upsert=True,
    )


def _simulating_targets(ip: str) -> dict[str, Any]:
    state = _load_sim_state(ip)
    targets = [
        {
            "id": "robot",
            "kind": TARGET_ROBOT,
            "label": "Robot / Flex 主机",
            "mount": None,
            "slot": None,
            "product": "OT-3 Standard",
            "current_serial": _text(state.get("robot")),
            "provisionable": True,
            "script": "opentrons_hardware.scripts.provision_robot",
            "hint": PROVISION_HINTS[TARGET_ROBOT],
        },
        {
            "id": "pipette:left",
            "kind": TARGET_PIPETTE,
            "label": "Pipette · left",
            "mount": "left",
            "slot": None,
            "product": "p1000_single",
            "current_serial": _text(state.get("pipette:left")),
            "provisionable": True,
            "script": "opentrons_hardware.scripts.provision_pipette",
            "hint": PROVISION_HINTS[TARGET_PIPETTE],
        },
        {
            "id": "pipette:right",
            "kind": TARGET_PIPETTE,
            "label": "Pipette · right",
            "mount": "right",
            "slot": None,
            "product": "p50_multi",
            "current_serial": _text(state.get("pipette:right")) or None,
            "provisionable": True,
            "script": "opentrons_hardware.scripts.provision_pipette",
            "hint": PROVISION_HINTS[TARGET_PIPETTE],
        },
        {
            "id": "gripper",
            "kind": TARGET_GRIPPER,
            "label": "Gripper",
            "mount": "extension",
            "slot": None,
            "product": "gripper",
            "current_serial": _text(state.get("gripper")),
            "provisionable": True,
            "script": "opentrons_hardware.scripts.provision_gripper",
            "hint": PROVISION_HINTS[TARGET_GRIPPER],
        },
        {
            "id": "hepauv:1",
            "kind": TARGET_HEPAUV,
            "label": "HEPA/UV Module",
            "mount": None,
            "slot": "1",
            "product": "hepauv",
            "current_serial": _text(state.get("hepauv:1")),
            "provisionable": True,
            "script": "opentrons_hardware.scripts.provision_hepauv",
            "hint": PROVISION_HINTS[TARGET_HEPAUV],
        },
    ]
    return {
        "ip": ip,
        "port": setting.ROBOT_HEALTH_PORT,
        "http_connected": True,
        "ssh_connected": True,
        "simulating": True,
        "targets": targets,
        "errors": [],
    }


def _read_robot_serial_http(client: OpentronsHttpClient) -> str:
    try:
        health = client.get_health()
    except OpentronsApiError:
        return ""
    try:
        update_health = client.get_update_server_health()
    except OpentronsApiError:
        update_health = {}
    return _text(resolve_robot_serial(health, update_health), health.get("robot_serial"))


def _read_robot_serial_ssh(ssh: OpentronsSshClient) -> str:
    try:
        exit_code, stdout, _stderr = ssh.exec_command("cat /var/serial 2>/dev/null || true", timeout=15)
        if exit_code == 0:
            return stdout.strip().splitlines()[0].strip() if stdout.strip() else ""
    except OpentronsSshError as exc:
        logger.warning("Failed to read /var/serial via SSH: %s", exc)
    return ""


def list_provision_targets(ip: str, port: int | None = None) -> dict[str, Any]:
    if setting.use_sqlite_persistence():
        return _simulating_targets(ip)

    client = _http_client(ip, port)
    ssh = OpentronsSshClient(ip)
    errors: list[str] = []
    http_connected = False
    ssh_connected = False
    robot_serial = ""
    instruments: list[Any] = []
    modules: list[Any] = []
    pipettes_dict: dict[str, Any] = {}

    try:
        robot_serial = _read_robot_serial_http(client)
        http_connected = True
        try:
            instruments_payload = client.get_instruments()
            instruments = _unwrap_list(instruments_payload)
            raw_data = OpentronsHttpClient.unwrap_data(instruments_payload)
            if isinstance(raw_data, dict) and ("left" in raw_data or "right" in raw_data):
                pipettes_dict = raw_data
        except OpentronsApiError as exc:
            errors.append(f"instruments: {exc}")
            try:
                pipettes_payload = client.get_pipettes()
                raw_data = OpentronsHttpClient.unwrap_data(pipettes_payload)
                if isinstance(raw_data, dict):
                    pipettes_dict = raw_data
                else:
                    instruments = _unwrap_list(pipettes_payload)
            except OpentronsApiError as fallback_exc:
                errors.append(f"pipettes: {fallback_exc}")
        try:
            modules = _unwrap_list(client.get_modules())
        except OpentronsApiError as exc:
            errors.append(f"modules: {exc}")
    except OpentronsApiError as exc:
        errors.append(f"HTTP: {exc}")

    try:
        ssh.test_connection()
        ssh_connected = True
        if not robot_serial:
            robot_serial = _read_robot_serial_ssh(ssh)
    except OpentronsSshError as exc:
        errors.append(f"SSH: {exc}")

    targets: list[dict[str, Any]] = [
        {
            "id": "robot",
            "kind": TARGET_ROBOT,
            "label": "Robot / Flex 主机",
            "mount": None,
            "slot": None,
            "product": "Flex",
            "current_serial": robot_serial or None,
            "provisionable": True,
            "script": "opentrons_hardware.scripts.provision_robot",
            "hint": PROVISION_HINTS[TARGET_ROBOT],
        }
    ]

    for index, raw in enumerate(instruments):
        if not isinstance(raw, dict):
            continue
        instrument_type = _text(raw.get("instrumentType"), raw.get("type")).lower()
        mount = _text(raw.get("mount"), raw.get("pipetteMount")).lower() or None
        serial = _text(raw.get("serialNumber"), raw.get("serial"), raw.get("id")) or None
        product = _text(
            raw.get("instrumentName"),
            raw.get("instrumentModel"),
            raw.get("pipetteName"),
            raw.get("pipetteModel"),
            raw.get("displayName"),
            raw.get("name"),
        )

        if instrument_type == "gripper" or "gripper" in product.lower() or mount in {"extension", "gripper"}:
            targets.append(
                {
                    "id": f"gripper:{index}",
                    "kind": TARGET_GRIPPER,
                    "label": "Gripper",
                    "mount": mount or "extension",
                    "slot": None,
                    "product": product or "gripper",
                    "current_serial": serial,
                    "provisionable": True,
                    "script": "opentrons_hardware.scripts.provision_gripper",
                    "hint": PROVISION_HINTS[TARGET_GRIPPER],
                }
            )
            continue

        if mount not in {"left", "right"}:
            # Legacy pipette map: {"left": {...}, "right": {...}}
            continue

        targets.append(
            {
                "id": f"pipette:{mount}",
                "kind": TARGET_PIPETTE,
                "label": f"Pipette · {mount}",
                "mount": mount,
                "slot": None,
                "product": product or f"pipette-{mount}",
                "current_serial": serial,
                "provisionable": True,
                "script": "opentrons_hardware.scripts.provision_pipette",
                "hint": PROVISION_HINTS[TARGET_PIPETTE],
            }
        )

    if not any(t["kind"] == TARGET_PIPETTE for t in targets) and pipettes_dict:
        for mount in ("left", "right"):
            raw = pipettes_dict.get(mount)
            if not isinstance(raw, dict):
                continue
            serial = _text(raw.get("id"), raw.get("serialNumber"), raw.get("serial")) or None
            product = _text(raw.get("name"), raw.get("model"), raw.get("pipetteName"), raw.get("pipetteModel"))
            if not serial and not product:
                continue
            targets.append(
                {
                    "id": f"pipette:{mount}",
                    "kind": TARGET_PIPETTE,
                    "label": f"Pipette · {mount}",
                    "mount": mount,
                    "slot": None,
                    "product": product or f"pipette-{mount}",
                    "current_serial": serial,
                    "provisionable": True,
                    "script": "opentrons_hardware.scripts.provision_pipette",
                    "hint": PROVISION_HINTS[TARGET_PIPETTE],
                }
            )

    for index, raw in enumerate(modules):
        if not isinstance(raw, dict):
            continue
        serial = _text(raw.get("serialNumber"), raw.get("serial"), raw.get("id")) or None
        product = _text(raw.get("moduleModel"), raw.get("moduleType"), raw.get("displayName"), raw.get("name"))
        slot = _text(
            (raw.get("location") or {}).get("slotName") if isinstance(raw.get("location"), dict) else None,
            raw.get("slotName"),
            raw.get("slot"),
            raw.get("usbPort"),
        ) or None
        if _is_hepauv_module(raw):
            targets.append(
                {
                    "id": f"hepauv:{index}",
                    "kind": TARGET_HEPAUV,
                    "label": f"HEPA/UV · slot {slot or index}",
                    "mount": None,
                    "slot": slot,
                    "product": product or "hepauv",
                    "current_serial": serial,
                    "provisionable": True,
                    "script": "opentrons_hardware.scripts.provision_hepauv",
                    "hint": PROVISION_HINTS[TARGET_HEPAUV],
                }
            )
        else:
            targets.append(
                {
                    "id": f"module:{index}",
                    "kind": "module",
                    "label": product or f"Module · {index}",
                    "mount": None,
                    "slot": slot,
                    "product": product or "module",
                    "current_serial": serial,
                    "provisionable": False,
                    "script": None,
                    "hint": "该模块暂无工厂烧录脚本（仅支持 robot / pipette / gripper / HEPA-UV）",
                    "reason": "unsupported_module",
                }
            )

    # Deduplicate pipette targets by mount
    seen_ids: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for target in targets:
        key = target["id"]
        if key in seen_ids:
            continue
        seen_ids.add(key)
        deduped.append(target)

    return {
        "ip": ip,
        "port": port or setting.ROBOT_HEALTH_PORT,
        "http_connected": http_connected,
        "ssh_connected": ssh_connected,
        "simulating": False,
        "targets": deduped,
        "errors": errors,
    }


def _combined_output(stdout: str, stderr: str) -> str:
    return f"{stdout or ''}\n{stderr or ''}"


def _robot_write_succeeded(combined: str) -> bool:
    if "Error running action" in combined:
        return False
    if "Write Failed" in combined:
        return False
    if "Invalid serial number" in combined:
        return False
    return "Finished action (write)" in combined or "Write Sucess: SERIAL_NUMBER" in combined


def _interactive_write_succeeded(combined: str, *, success_token: str = "serial confirmed") -> bool:
    lowered = combined.lower()
    if "invalid serial" in lowered or "update failed" in lowered:
        # still allow SUCCESS log line to win below
        pass
    if success_token.lower() in lowered:
        return True
    if re.search(r"\bSUCCESS,", combined):
        if re.search(r"\bFAILURE,", combined):
            # Prefer last outcome marker
            last_success = combined.rfind("SUCCESS,")
            last_failure = combined.rfind("FAILURE,")
            return last_success > last_failure
        return True
    return False


def _build_robot_command(serial: str) -> str:
    # clear_eeprom may prompt for confirmation when EEPROM already has data
    return (
        "printf 'y\\n' | "
        "python3 -m opentrons_hardware.scripts.provision_robot "
        f"--action write --property SERIAL_NUMBER {shlex.quote(serial)}"
    )


def _build_pipette_command(serial: str, mount: str) -> str:
    # Scripts loop forever; --once is declared but unused. Feed one serial then EOF.
    return (
        f"printf '%s\\ny\\n' {shlex.quote(serial)} | "
        f"python3 -m opentrons_hardware.scripts.provision_pipette "
        f"--which {shlex.quote(mount)} --log-level INFO; "
        "tail -n 30 /var/log/provision_pipette.log 2>/dev/null || true"
    )


def _build_gripper_command(serial: str) -> str:
    return (
        f"printf '%s\\ny\\n' {shlex.quote(serial)} | "
        "python3 -m opentrons_hardware.scripts.provision_gripper --log-level INFO; "
        "tail -n 30 /var/log/provision_gripper.log 2>/dev/null || true"
    )


def _build_hepauv_command(serial: str) -> str:
    return (
        f"printf '%s\\ny\\n' {shlex.quote(serial)} | "
        "python3 -m opentrons_hardware.scripts.provision_hepauv --once --log-level INFO; "
        "tail -n 30 /var/log/provision_hepauv.log 2>/dev/null || true"
    )


def _refresh_current_serial(
    *,
    ip: str,
    port: int | None,
    kind: str,
    mount: str | None,
    target_id: str,
) -> str | None:
    if setting.use_sqlite_persistence():
        state = _load_sim_state(ip)
        return _text(state.get(target_id)) or None

    try:
        summary = list_provision_targets(ip, port)
    except Exception as exc:
        logger.warning("Failed to refresh provision targets after write: %s", exc)
        return None

    for target in summary.get("targets") or []:
        if not isinstance(target, dict):
            continue
        if target.get("id") == target_id:
            return target.get("current_serial")
        if kind == TARGET_PIPETTE and target.get("kind") == TARGET_PIPETTE and target.get("mount") == mount:
            return target.get("current_serial")
        if kind == TARGET_ROBOT and target.get("kind") == TARGET_ROBOT:
            return target.get("current_serial")
        if kind == TARGET_GRIPPER and target.get("kind") == TARGET_GRIPPER:
            return target.get("current_serial")
        if kind == TARGET_HEPAUV and target.get("kind") == TARGET_HEPAUV:
            return target.get("current_serial")
    return None


def provision_barcode(
    ip: str,
    *,
    kind: str,
    serial: str,
    mount: str | None = None,
    target_id: str | None = None,
    port: int | None = None,
) -> dict[str, Any]:
    cleaned = serial.strip()
    error = _validate_serial(kind, cleaned)
    if error:
        raise ValueError(error)

    if kind == TARGET_PIPETTE and mount not in {"left", "right"}:
        raise ValueError("烧录 pipette 需要指定 mount=left|right")

    resolved_target_id = target_id or (
        f"pipette:{mount}" if kind == TARGET_PIPETTE else kind if kind == TARGET_ROBOT else kind
    )

    if setting.use_sqlite_persistence():
        state = _load_sim_state(ip)
        state[resolved_target_id] = cleaned
        if kind == TARGET_ROBOT:
            state["robot"] = cleaned
        elif kind == TARGET_PIPETTE:
            state[f"pipette:{mount}"] = cleaned
        elif kind == TARGET_GRIPPER:
            state["gripper"] = cleaned
        _save_sim_state(ip, state)
        return {
            "success": True,
            "message": "Simulating 模式：条码已写入本地状态",
            "kind": kind,
            "mount": mount,
            "target_id": resolved_target_id,
            "requested_serial": cleaned,
            "current_serial": cleaned,
            "exit_code": 0,
            "command": "(simulating)",
            "stdout": "",
            "stderr": "",
            "simulating": True,
        }

    if kind == TARGET_ROBOT:
        command = _build_robot_command(cleaned)
        timeout = 180
        success_checker = _robot_write_succeeded
    elif kind == TARGET_PIPETTE:
        command = _build_pipette_command(cleaned, mount or "left")
        timeout = 120
        success_checker = lambda out: _interactive_write_succeeded(out)
    elif kind == TARGET_GRIPPER:
        command = _build_gripper_command(cleaned)
        timeout = 120
        success_checker = lambda out: _interactive_write_succeeded(out)
    elif kind == TARGET_HEPAUV:
        command = _build_hepauv_command(cleaned)
        timeout = 120
        success_checker = lambda out: _interactive_write_succeeded(out, success_token="SUCCESS")
    else:
        raise ValueError(f"不支持烧录类型: {kind}")

    ssh = OpentronsSshClient(ip)
    try:
        exit_code, stdout, stderr = ssh.exec_command(command, timeout=timeout)
    except OpentronsSshError as exc:
        raise RuntimeError(f"SSH 执行失败: {exc}") from exc

    combined = _combined_output(stdout, stderr)
    success = success_checker(combined)

    # Pipette/gripper often exit non-zero after SUCCESS because the script loops and hits EOF.
    if not success and kind in {TARGET_PIPETTE, TARGET_GRIPPER, TARGET_HEPAUV}:
        success = _interactive_write_succeeded(combined)

    current_serial: str | None = None
    if success:
        if kind == TARGET_ROBOT:
            # robot-server restarts after provision; give it a moment
            time.sleep(2)
            current_serial = _read_robot_serial_ssh(ssh) or cleaned
            if current_serial and current_serial != cleaned:
                success = False
        else:
            time.sleep(1)
            current_serial = _refresh_current_serial(
                ip=ip,
                port=port,
                kind=kind,
                mount=mount,
                target_id=resolved_target_id,
            )
            if current_serial is None:
                current_serial = cleaned

    message = "条码烧录成功" if success else "条码烧录失败，请查看命令输出"
    if success and current_serial and current_serial != cleaned:
        message = f"脚本报告成功，但读回条码为 {current_serial}（期望 {cleaned}）"
        success = False

    return {
        "success": success,
        "message": message,
        "kind": kind,
        "mount": mount,
        "target_id": resolved_target_id,
        "requested_serial": cleaned,
        "current_serial": current_serial,
        "exit_code": exit_code,
        "command": command,
        "stdout": stdout[-12000:] if stdout else "",
        "stderr": stderr[-8000:] if stderr else "",
        "simulating": False,
    }
