from __future__ import annotations

from datetime import datetime, timezone
import re
from threading import RLock
from typing import Any

import core.config as setting
from modules.robots.api_client.client import OpentronsHttpClient
from modules.robots.files.ssh_client import OpentronsSshClient
from modules.robots.identity import resolve_robot_serial


TEST_VERSION_PATH = "/data/.hardware-testing-description"
ROBOT_SUBSYSTEMS = ("gantry_x", "gantry_y", "head", "rear_panel")

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
    try:
        return _text(OpentronsSshClient(ip).read_text(TEST_VERSION_PATH), "N/A")
    except Exception:
        return "N/A"


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
    barcode = resolve_robot_serial(health, update_health) or ""
    if require_barcode and not barcode:
        raise RuntimeError("设备未返回 Robot 条码")

    return {
        "barcode": barcode or "N/A",
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
    instruments = _items(_http_client(ip, port).get_instruments())
    instrument = next(
        (item for item in instruments if _instrument_matches(product_key, item)),
        None,
    )
    if instrument is None:
        raise RuntimeError(f"当前设备未检测到 {_PRODUCT_BY_KEY[product_key]['label']}")

    barcode = _text(
        instrument.get("serialNumber", instrument.get("serial_number", instrument.get("id")))
    )
    if not barcode:
        raise RuntimeError("Instrument 未返回条码")

    return {
        "barcode": barcode,
        "test_version": _read_test_version(ip),
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
    if setting.use_sqlite_persistence():
        return _simulated_versions(ip, port, product_key)
    if product_key == "robot":
        return _collect_robot_versions(
            ip,
            port,
            require_barcode=require_barcode,
        )
    return _collect_instrument_versions(ip, port, product_key)


def _get_collection():
    """Version history always persists to platform.sqlite3 under the active profile.

    Non-simulating → db-storage/business/platform.sqlite3
    Simulating → db-storage/simulating/platform.sqlite3
    """
    from core.sqlite_store import get_platform_store

    return get_platform_store()[setting.ROBOT_VERSION_RECORD_COLLECTION]


def _storage_label() -> str:
    return "sqlite"

def _serialize_document(document: dict[str, Any]) -> dict[str, Any]:
    serialized = dict(document)
    serialized["_id"] = str(serialized.get("_id") or "")
    return serialized


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
    captured = _collect_versions(ip, port, normalized_product_type)
    barcode = _text(captured.get("barcode"))
    if not barcode or barcode == "N/A":
        subject = "Robot" if normalized_product_type == "robot" else "Instrument"
        raise RuntimeError(f"设备未返回 {subject} 条码，无法保存版本记录")
    test_entry = {
        "test_name": normalized_test_name,
        "sn": barcode,
        "robot_ip": ip,
        "test_version": _text(captured.get("test_version"), "N/A"),
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
