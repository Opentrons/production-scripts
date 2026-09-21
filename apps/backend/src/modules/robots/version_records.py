from __future__ import annotations

from datetime import datetime, timezone
import re
from threading import RLock
from typing import Any
from uuid import uuid4

import requests

import core.config as setting
from core.database import mongodb
from modules.robots.api_client.client import OpentronsHttpClient
from modules.robots.files.ssh_client import OpentronsSshClient
from modules.robots.identity import resolve_robot_serial


TEST_VERSION_PATH = "/data/.hardware-testing-description"
TEST_VERSION_COMMAND = f"cat {TEST_VERSION_PATH} 2>/dev/null || true"
ROBOT_SERIAL_SSH_COMMAND = "cat /var/serial 2>/dev/null || true"
ROBOT_SUBSYSTEMS = ("gantry_x", "gantry_y", "head", "rear_panel")
OPENTRONS_GITHUB_REPO = "Opentrons/opentrons"

PRODUCTS: tuple[dict[str, Any], ...] = (
    {
        "key": "robot",
        "label": "Robot（机器人）",
        "test_names": [
            "1. Z STAGE SUBASSEMBLY TEST",
            "2. DIAGNOSTICS & SERIAL NUMBER PROGRAMMING",
            "3. DIAGNOSTICS FINISHED",
            "4. TESTS USING JOGGING SCRIPT",
            "5. GANTRY STRESS TEST",
            "6. XY BELT CALIBRATION",
            "7. SOFTWARE UPDATE",
            "8. QC PROTOCOL",
            "9. SHIPPING FIRMWARE",
        ],
    },
    {
        "key": "pipette_single_channel",
        "label": "Pipette Single Channel（单通道）",
        "test_names": [
            "1. CURRENT & SPEED TEST",
            "2. DIAGNOSTICS",
            "3. GRAVIMETRIC TEST",
            "4. SHIPPING FIRMWARE",
        ],
    },
    {
        "key": "pipette_8_channels",
        "label": "Pipette 8 Channels（8 通道）",
        "test_names": [
            "1. CURRENT & SPEED TEST",
            "2. DIAGNOSTICS",
            "3. GRAVIMETRIC TEST",
            "4. SHIPPING FIRMWARE",
        ],
    },
    {
        "key": "pipette_96_channels_200ul",
        "label": "Pipette 96 Channels 200 µL",
        "test_names": [
            "1. DIAGNOSTICS AND SERIAL NUMBER TOUCHPOINT",
            "2. DROPOUT & PROTOCOL TEST TOUCHPOINT",
            "3. PHOTOMETRIC TOUCHPOINT",
            "4. GRAVIMETRIC TOUCHPOINT",
            "5. PREHEATING TOUCHPOINT",
            "6. BASELINE & DILUENT FILLING TOUCHPOINT",
            "7. SHIPPING FIRMWARE TOUCHPOINT",
        ],
    },
    {
        "key": "pipette_96_channels_1000ul",
        "label": "Pipette 96 Channels 1000 µL",
        "test_names": [
            "1. DIAGNOSTICS AND SERIAL NUMBER TOUCHPOINT",
            "2. PROTOCOL TEST",
            "3. PHOTOMETRIC TOUCHPOINT",
            "4. GRAVIMETRIC TOUCHPOINT",
            "5. SHIPPING FIRMWARE TOUCHPOINT",
        ],
    },
    {
        "key": "gripper",
        "label": "Gripper",
        "test_names": [
            "1. DIAGNOSTICS SOFTWARE FIRMWARE",
            "2. QC PROTOCOL",
            "3. SHIPPING SOFTWARE FIRMWARE",
        ],
    },
)

_PRODUCT_BY_KEY = {str(product["key"]): product for product in PRODUCTS}
_PERSIST_LOCK = RLock()
_COMMIT_ID_CACHE: dict[str, str | None] = {}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any, fallback: str = "") -> str:
    if isinstance(value, str):
        text = value.replace("\x00", "").strip()
        return text or fallback
    if isinstance(value, (int, float, bool)):
        return str(value)
    return fallback


def _boolean(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in (1, "true", "True"):
        return True
    if value in (0, "false", "False"):
        return False
    return None


def _items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        payload = payload.get("data", payload)
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _read_test_version(ip: str) -> str:
    """Read robot test version the same way Device Control version query does.

    Prefer SSH `cat` of `/data/.hardware-testing-description` (same source as
    device management / get_ot3_version). Missing or empty content becomes N/A.
    """

    try:
        exit_code, stdout, _stderr = OpentronsSshClient(ip).exec_command(
            TEST_VERSION_COMMAND,
            timeout=15,
        )
        if exit_code == 0:
            value = _normalize_test_version(_text(stdout))
            if value and "file not found" not in value.casefold():
                return value
    except Exception:
        pass

    try:
        value = _normalize_test_version(_text(OpentronsSshClient(ip).read_text(TEST_VERSION_PATH)))
        if value and "file not found" not in value.casefold():
            return value
    except Exception:
        pass
    return "N/A"


def _normalize_test_version(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    candidates = [
        line
        for line in lines
        if line.casefold() not in {"serial", "sn", "barcode"}
    ]
    candidates = candidates or lines
    for line in candidates:
        if _extract_test_commit_ref(line):
            return _clean_test_version_line(line)
    return _clean_test_version_line(candidates[-1] if len(candidates) > 1 else candidates[0])


def _clean_test_version_line(value: str) -> str:
    text = value.strip().rstrip(",;")
    label_match = re.match(
        r"^(?:test\s+version|version|scripts?|tag|branch|commit(?:\s+hash)?|hash|sha)\s*[:=：]\s*(.+)$",
        text,
        flags=re.IGNORECASE,
    )
    if label_match:
        return label_match.group(1).strip().rstrip(",;")
    return text


def _extract_test_commit_ref(value: Any) -> str:
    text = _normalize_test_version(value) if "\n" in str(value or "") else _text(value)
    if not text or text.upper() == "N/A":
        return ""
    github_match = re.search(r"/(?:tree|commit)/([^\s?#]+)", text, flags=re.IGNORECASE)
    if github_match:
        return github_match.group(1).rstrip("/")
    sha_match = re.search(r"\b[0-9a-f]{7,40}\b", text, flags=re.IGNORECASE)
    if sha_match:
        return sha_match.group(0)
    label_match = re.search(
        r"(?:test\s+version|version|scripts?|tag|branch|commit(?:\s+hash)?|hash|sha)\s*[:=：]\s*([^\s,;]+)",
        text,
        flags=re.IGNORECASE,
    )
    if label_match:
        return label_match.group(1).rstrip("/")
    token = text.split()[0].strip().rstrip("/")
    if re.search(r"[A-Za-z]", token) and re.search(r"[.-]", token):
        return token
    return ""


def _resolve_test_commit_id(ref: str) -> str | None:
    text = str(ref or "").strip()
    if not text or text.lower().endswith(".py"):
        return None
    if re.fullmatch(r"[0-9a-f]{40}", text, flags=re.IGNORECASE):
        return text.lower()
    with _PERSIST_LOCK:
        if text in _COMMIT_ID_CACHE:
            return _COMMIT_ID_CACHE[text]

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "production-scripts-version-records",
    }
    token = _text(getattr(setting, "GITHUB_TOKEN", "")) or ""
    try:
        import os

        token = token or os.getenv("GITHUB_TOKEN", "").strip() or os.getenv("GH_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        response = requests.get(
            f"https://api.github.com/repos/{OPENTRONS_GITHUB_REPO}/commits",
            params={"sha": text, "per_page": 1},
            headers=headers,
            timeout=15,
        )
        if response.status_code != 200:
            commit_id = None
        else:
            payload = response.json()
            commit_id = (
                str(payload[0].get("sha") or "").strip().lower()
                if isinstance(payload, list) and payload and isinstance(payload[0], dict)
                else None
            )
    except (requests.RequestException, ValueError, TypeError, IndexError, KeyError):
        commit_id = None

    with _PERSIST_LOCK:
        _COMMIT_ID_CACHE[text] = commit_id
    return commit_id


def _test_commit_fields(test_version: Any) -> dict[str, str]:
    normalized = _normalize_test_version(test_version) or "N/A"
    commit_ref = _extract_test_commit_ref(normalized)
    commit_id = _resolve_test_commit_id(commit_ref) if commit_ref else None
    return {
        "test_version": normalized,
        "test_commit_hash": commit_ref,
        "test_commit_id": commit_id or "",
    }


def _read_robot_serial_ssh(ip: str) -> str:
    """Fallback serial read used by device barcode / device-info flows."""

    try:
        exit_code, stdout, _stderr = OpentronsSshClient(ip).exec_command(
            ROBOT_SERIAL_SSH_COMMAND,
            timeout=15,
        )
        if exit_code == 0:
            return _text(stdout.splitlines()[0] if stdout.strip() else "")
    except Exception:
        pass
    return ""


def _resolve_robot_barcode(ip: str, health: dict[str, Any], update_health: dict[str, Any]) -> str:
    """Resolve robot barcode like Device Info / barcode provision, else N/A."""

    barcode = resolve_robot_serial(health, update_health) or ""
    if not barcode:
        barcode = _read_robot_serial_ssh(ip)
    return barcode or "N/A"


def _http_client(ip: str, port: int) -> OpentronsHttpClient:
    return OpentronsHttpClient(ip, port)


def _normalize_subsystem(item: dict[str, Any], name: str) -> dict[str, Any]:
    return {
        "name": name,
        "firmware_version": _text(
            item.get("current_fw_version", item.get("currentFwVersion")),
            "N/A",
        ),
        "next_firmware_version": _text(
            item.get("next_fw_version", item.get("nextFwVersion")),
            "N/A",
        ),
        "revision": _text(item.get("revision"), "N/A"),
        "ok": _boolean(item.get("ok")),
        "fw_update_needed": _boolean(
            item.get("fw_update_needed", item.get("fwUpdateNeeded"))
        ),
    }


def _collect_robot_versions(
    ip: str,
    port: int,
    *,
    require_barcode: bool = True,
) -> dict[str, Any]:
    client = _http_client(ip, port)
    health = _record(client.get_health())
    try:
        update_health = _record(client.get_update_server_health())
    except Exception:
        update_health = {}
    subsystem_items = _items(client.request("GET", "/subsystems/status"))
    subsystem_by_name = {
        _text(item.get("name")): item
        for item in subsystem_items
        if _text(item.get("name"))
    }
    barcode = _resolve_robot_barcode(ip, health, update_health)
    if require_barcode and barcode == "N/A":
        raise RuntimeError("设备未返回 Robot 条码")

    return {
        "barcode": barcode,
        "test_version": _read_test_version(ip),
        "robot": {
            "name": _text(health.get("name"), "N/A"),
            "model": _text(health.get("robot_model", health.get("robotModel")), "N/A"),
            "api_version": _text(health.get("api_version"), "N/A"),
            "system_version": _text(health.get("system_version"), "N/A"),
        },
        "subsystems": [
            _normalize_subsystem(subsystem_by_name.get(name, {}), name)
            for name in ROBOT_SUBSYSTEMS
        ],
    }


def _instrument_matches(product_key: str, item: dict[str, Any]) -> bool:
    instrument_type = _text(item.get("instrumentType", item.get("instrument_type"))).lower()
    model = _text(
        item.get("instrumentName", item.get("instrumentModel", item.get("instrument_model")))
    ).lower()
    data = _record(item.get("data"))
    channels = data.get("channels", item.get("channels"))
    max_volume = data.get("max_volume", data.get("maxVolume", item.get("max_volume")))

    if product_key == "gripper":
        return "gripper" in instrument_type or "gripper" in model
    if "pipette" not in instrument_type and "pipette" not in model:
        return False

    try:
        channel_count = int(channels)
    except (TypeError, ValueError):
        channel_count = 0
    try:
        maximum_volume = float(max_volume)
    except (TypeError, ValueError):
        maximum_volume = 0

    if product_key == "pipette_single_channel":
        return channel_count == 1 or "single" in model
    if product_key == "pipette_8_channels":
        return channel_count == 8 or "8channel" in model or "8_channel" in model
    if product_key == "pipette_96_channels_200ul":
        return channel_count == 96 and ("p200" in model or 0 < maximum_volume <= 200)
    if product_key == "pipette_96_channels_1000ul":
        return channel_count == 96 and ("p1000" in model or maximum_volume > 200)
    return False


def _collect_instrument_versions(ip: str, port: int, product_key: str) -> dict[str, Any]:
    client = _http_client(ip, port)
    instruments = _items(client.get_instruments())
    instrument = next(
        (item for item in instruments if _instrument_matches(product_key, item)),
        None,
    )
    if instrument is None:
        raise RuntimeError(f"当前设备未检测到 {_PRODUCT_BY_KEY[product_key]['label']}")

    barcode = _text(
        instrument.get("serialNumber", instrument.get("serial_number", instrument.get("id"))),
        "N/A",
    )

    try:
        health = _record(client.get_health())
    except Exception:
        health = {}

    return {
        "barcode": barcode or "N/A",
        "test_version": _read_test_version(ip),
        "robot": {
            "name": _text(health.get("name"), "N/A"),
            "model": _text(health.get("robot_model", health.get("robotModel")), "N/A"),
            "api_version": _text(health.get("api_version"), "N/A"),
            "system_version": _text(health.get("system_version"), "N/A"),
        },
        "instrument": {
            "name": _text(
                instrument.get("instrumentName", instrument.get("name")),
                "N/A",
            ),
            "model": _text(
                instrument.get("instrumentModel", instrument.get("model")),
                "N/A",
            ),
            "type": _text(
                instrument.get("instrumentType", instrument.get("instrument_type")),
                "N/A",
            ),
            "mount": _text(instrument.get("mount"), "N/A"),
            "subsystem": _text(instrument.get("subsystem"), "N/A"),
            "firmware_version": _text(
                instrument.get("firmwareVersion", instrument.get("firmware_version")),
                "N/A",
            ),
            "ok": _boolean(instrument.get("ok")),
        },
    }


def _simulated_versions(ip: str, port: int, product_key: str) -> dict[str, Any]:
    from modules.system import simulating_seed

    robot = simulating_seed.find_fake_robot(ip, port) or {}
    firmware_version = _text(robot.get("fw_version"), "69")
    if product_key == "robot":
        revisions = {
            "gantry_x": "C2.0",
            "gantry_y": "C2.0",
            "head": "C2.0",
            "rear_panel": "D1.0",
        }
        return {
            "barcode": _text(robot.get("serial_number"), "SIM-ROBOT-0001"),
            "test_version": "SIM-TEST-1.0",
            "robot": {
                "name": _text(robot.get("name"), "SIM-FLEX"),
                "model": _text(robot.get("robot_model"), "OT-3 Standard"),
                "api_version": _text(robot.get("api_version"), "N/A"),
                "system_version": _text(robot.get("version"), "N/A"),
            },
            "subsystems": [
                {
                    "name": name,
                    "firmware_version": firmware_version,
                    "next_firmware_version": firmware_version,
                    "revision": revisions[name],
                    "ok": True,
                    "fw_update_needed": False,
                }
                for name in ROBOT_SUBSYSTEMS
            ],
        }

    simulated_barcodes = {
        "pipette_single_channel": "SIM-P1-0001",
        "pipette_8_channels": "SIM-P8-0001",
        "pipette_96_channels_200ul": "SIM-P96-200-0001",
        "pipette_96_channels_1000ul": "SIM-P96-1000-0001",
        "gripper": "SIM-GRIPPER-0001",
    }
    return {
        "barcode": simulated_barcodes[product_key],
        "test_version": "SIM-TEST-1.0",
        "robot": {
            "name": _text(robot.get("name"), "SIM-FLEX"),
            "model": _text(robot.get("robot_model"), "OT-3 Standard"),
            "api_version": _text(robot.get("api_version"), "N/A"),
            "system_version": _text(robot.get("version"), "N/A"),
        },
        "instrument": {
            "name": str(_PRODUCT_BY_KEY[product_key]["label"]),
            "model": product_key,
            "type": "gripper" if product_key == "gripper" else "pipette",
            "mount": "extension" if product_key == "gripper" else "left",
            "subsystem": "gripper" if product_key == "gripper" else "pipette_left",
            "firmware_version": firmware_version,
            "ok": True,
        },
    }


def _collect_versions(
    ip: str,
    port: int,
    product_key: str,
    *,
    require_barcode: bool = True,
) -> dict[str, Any]:
    if product_key == "robot":
        return _collect_robot_versions(
            ip,
            port,
            require_barcode=require_barcode,
        )
    return _collect_instrument_versions(ip, port, product_key)


def _get_collection():
    """Version history is always persisted in MongoDB."""
    if mongodb.client is None and not mongodb.connect():
        raise RuntimeError("MongoDB 连接失败，无法保存版本读取记录")
    return mongodb.get_database(setting.MESSAGE_COLLECTION)[
        setting.ROBOT_VERSION_RECORD_COLLECTION
    ]


def _get_rule_collection():
    if mongodb.client is None and not mongodb.connect():
        raise RuntimeError("MongoDB 连接失败，无法保存版本对比规则")
    collection = mongodb.get_database(setting.MESSAGE_COLLECTION)[
        setting.ROBOT_VERSION_COMPARISON_RULE_COLLECTION
    ]
    collection.create_index([("product_type", 1), ("duro_parent_id", 1)])
    collection.create_index([("updated_at", -1)])
    return collection


def _storage_label() -> str:
    return "mongodb"

def _serialize_document(document: dict[str, Any]) -> dict[str, Any]:
    serialized = dict(document)
    serialized["_id"] = str(serialized.get("_id") or "")
    tests = serialized.get("tests")
    if isinstance(tests, dict):
        serialized["tests"] = {
            key: _serialize_test_entry(value)
            for key, value in tests.items()
        }
    return serialized


def _serialize_test_entry(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    entry = dict(value)
    fields = _test_commit_fields(entry.get("test_version"))
    entry.update(fields)
    return entry


def _test_key(test_name: str) -> str:
    number_match = re.match(r"^\s*(\d+)\.", test_name)
    if number_match:
        return f"test{number_match.group(1)}"
    normalized = re.sub(r"[^a-z0-9]+", "_", test_name.casefold()).strip("_")
    return f"test_{normalized or 'default'}"


def list_products() -> dict[str, Any]:
    return {
        "products": [
            {
                "key": product["key"],
                "label": product["label"],
                "test_names": list(product["test_names"]),
            }
            for product in PRODUCTS
        ]
    }


def get_current_robot_versions(ip: str, port: int = setting.ROBOT_HEALTH_PORT) -> dict[str, Any]:
    captured = _collect_versions(ip, port, "robot", require_barcode=False)
    return {
        "ip": ip,
        "port": port,
        "queried_at": _utc_now(),
        **captured,
    }


def capture_version(
    *,
    ip: str,
    port: int,
    product_type: str,
    test_name: str,
) -> dict[str, Any]:
    normalized_product_type = str(product_type or "").strip()
    product = _PRODUCT_BY_KEY.get(normalized_product_type)
    if product is None:
        raise ValueError("不支持的产品类型")
    normalized_test_name = str(test_name or "").strip()
    if normalized_test_name not in product["test_names"]:
        raise ValueError("测试过程不属于所选产品")

    queried_at = _utc_now()
    # Match Device Control "查询版本": allow missing barcode and still return versions.
    captured = _collect_versions(ip, port, normalized_product_type, require_barcode=False)
    barcode = _text(captured.get("barcode"), "N/A") or "N/A"
    commit_fields = _test_commit_fields(captured.get("test_version"))
    test_entry = {
        "test_name": normalized_test_name,
        "sn": barcode,
        "robot_ip": ip,
        **commit_fields,
        "queried_at": queried_at,
        **({"robot": captured["robot"]} if "robot" in captured else {}),
        **({"subsystems": captured["subsystems"]} if "subsystems" in captured else {}),
        **({"instrument": captured["instrument"]} if "instrument" in captured else {}),
    }
    collection = _get_collection()

    with _PERSIST_LOCK:
        existing = collection.find_one({"barcode": barcode})
        if existing and existing.get("product_type") not in (None, normalized_product_type):
            raise ValueError("该条码已用于其他产品类型")
        tests = dict(existing.get("tests") or {}) if existing else {}
        tests[_test_key(normalized_test_name)] = test_entry
        now = _utc_now()
        collection.update_one(
            {"barcode": barcode},
            {
                "$set": {
                    "barcode": barcode,
                    "sn": barcode,
                    "product_type": normalized_product_type,
                    "product_name": product["label"],
                    "robot_ip": ip,
                    "tests": tests,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        stored = collection.find_one({"barcode": barcode}) or {}

    return {
        "success": True,
        "created": existing is None,
        "storage": _storage_label(),
        "test_key": _test_key(normalized_test_name),
        "test": test_entry,
        "record": _serialize_document(stored),
    }


def list_history(*, page: int = 1, page_size: int = 100) -> dict[str, Any]:
    normalized_page = max(1, int(page))
    normalized_page_size = max(1, min(500, int(page_size)))
    collection = _get_collection()
    total = collection.count_documents({})
    documents = list(
        collection.find({})
        .sort([("updated_at", -1), ("barcode", 1)])
        .skip((normalized_page - 1) * normalized_page_size)
        .limit(normalized_page_size)
    )
    return {
        "records": [_serialize_document(document) for document in documents],
        "total": total,
        "page": normalized_page,
        "page_size": normalized_page_size,
        "storage": _storage_label(),
    }


def delete_history_record(record_id: str) -> dict[str, Any]:
    normalized_id = str(record_id or "").strip()
    if not normalized_id:
        raise ValueError("版本记录 ID 不能为空")
    collection = _get_collection()
    result = collection.delete_one({"_id": normalized_id})
    return {"success": bool(getattr(result, "deleted_count", 0)), "id": normalized_id}


def _normalize_rule_payload(payload: dict[str, Any]) -> dict[str, Any]:
    product_type = str(payload.get("product_type") or "").strip()
    if product_type not in _PRODUCT_BY_KEY:
        raise ValueError("不支持的产品类型")
    fields = [str(field).strip() for field in payload.get("fields") or []]
    allowed_fields = {"test_version", "app_version", "firmware"}
    normalized_fields = [field for field in fields if field in allowed_fields]
    if not normalized_fields:
        raise ValueError("至少需要一个对比字段")
    test_names = [str(item).strip() for item in payload.get("test_names") or [] if str(item).strip()]
    if not test_names:
        raise ValueError("至少需要一个对比测试")
    return {
        "product_type": product_type,
        "product_name": _text(payload.get("product_name"), str(_PRODUCT_BY_KEY[product_type]["label"])),
        "duro_product_id": _text(payload.get("duro_product_id")),
        "duro_product_label": _text(payload.get("duro_product_label")),
        "duro_parent_id": _text(payload.get("duro_parent_id")),
        "duro_parent_label": _text(payload.get("duro_parent_label")),
        "test_names": test_names,
        "fields": normalized_fields,
    }


def list_comparison_rules() -> dict[str, Any]:
    collection = _get_rule_collection()
    records = list(collection.find({}).sort([("updated_at", -1), ("product_name", 1)]))
    return {
        "rules": [_serialize_document(record) for record in records],
        "total": len(records),
        "storage": "mongodb",
    }


def create_comparison_rule(payload: dict[str, Any]) -> dict[str, Any]:
    collection = _get_rule_collection()
    now = _utc_now()
    document = {
        "_id": uuid4().hex,
        **_normalize_rule_payload(payload),
        "created_at": now,
        "updated_at": now,
    }
    collection.insert_one(document)
    return _serialize_document(document)


def update_comparison_rule(rule_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    collection = _get_rule_collection()
    update = {
        **_normalize_rule_payload(payload),
        "updated_at": _utc_now(),
    }
    result = collection.update_one({"_id": str(rule_id)}, {"$set": update})
    if getattr(result, "matched_count", 0) == 0:
        raise KeyError(rule_id)
    document = collection.find_one({"_id": str(rule_id)}) or {"_id": str(rule_id), **update}
    return _serialize_document(document)


def delete_comparison_rule(rule_id: str) -> dict[str, Any]:
    collection = _get_rule_collection()
    result = collection.delete_one({"_id": str(rule_id)})
    return {"success": bool(getattr(result, "deleted_count", 0)), "id": str(rule_id)}
