from __future__ import annotations

from datetime import datetime, timedelta, timezone

import core.config as setting
from core.logging import get_logger
from core.sqlite_store import get_platform_store
from modules.robots import robots as robot_service

logger = get_logger(__name__)

SEED_MARKER = "simulating_seed_v1"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat()


def build_fake_robots(port: int = setting.ROBOT_HEALTH_PORT) -> list[dict]:
    return [
        {
            "ip": "192.168.6.11",
            "port": port,
            "online": True,
            "service_status": "normal",
            "version": "8.3.0",
            "name": "SIM-FLEX-A",
            "robot_type": "OT-3",
            "serial_number": "FLXA1020250101001",
            "error": None,
            "api_version": "8.3.0",
            "fw_version": "60",
            "health_fetch_failed": False,
        },
        {
            "ip": "192.168.6.12",
            "port": port,
            "online": True,
            "service_status": "normal",
            "version": "8.8.0",
            "name": "SIM-FLEX-B",
            "robot_type": "OT-3",
            "serial_number": "FLXA1020250101002",
            "error": None,
            "api_version": "8.8.0",
            "fw_version": "65",
            "health_fetch_failed": False,
        },
        {
            "ip": "192.168.6.13",
            "port": port,
            "online": True,
            "service_status": "error",
            "version": "9.1.0",
            "name": "SIM-FLEX-C",
            "robot_type": "OT-3",
            "serial_number": "FLXU2020250101003",
            "error": "部分详细信息获取失败: /robot/health HTTP 404",
            "api_version": "9.1.0",
            "fw_version": "69",
            "health_fetch_failed": True,
        },
    ]


def build_fake_scan_result(port: int = setting.ROBOT_HEALTH_PORT) -> dict:
    online_robots = build_fake_robots(port)
    abnormal_robots = [robot for robot in online_robots if robot.get("service_status") != "normal"]
    return {
        "total": len(online_robots),
        "online_count": len(online_robots),
        "offline_count": 0,
        "abnormal_count": len(abnormal_robots),
        "scan_network": "192.168.6.1-255",
        "server_ip": "192.168.6.55",
        "gateway": "192.168.6.1",
        "scan_gateways": ["192.168.6.1"],
        "online_robots": online_robots,
        "offline_robots": [],
        "abnormal_robots": abnormal_robots,
        "simulating": True,
        "port": int(port),
    }


def build_fake_upload_records() -> list[dict]:
    now = _utc_now()
    records = []
    fixtures = [
        ("Flex", "FLXA1020250101001", "leveling", "success"),
        ("Flex", "FLXA1020250101002", "robot_assembly_qc", "success"),
        ("Flex", "FLXU2020250101003", "diagnostic", "failed"),
        ("P1000M", "P1KMV3520250101A01", "gravimetric", "success"),
        ("P50M", "P50MV3520250101A01", "assembly_qc", "running"),
    ]
    for index, (model, sn, test_type, status) in enumerate(fixtures):
        started = now - timedelta(hours=index + 1)
        finished = None if status == "running" else started + timedelta(minutes=8 + index)
        record_id = f"sim-upload-{index + 1:03d}"
        records.append(
            {
                "_id": record_id,
                "status": status,
                "new": index < 2,
                "created_at": _iso(started),
                "request_started_at": _iso(started),
                "finished_at": _iso(finished) if finished else None,
                "file_desc": {
                    "model": model,
                    "sn": sn,
                    "test_type": test_type,
                },
                "csv_file": {"name": f"{sn}-{test_type}.csv"},
                "result": {
                    "model": model,
                    "sn": sn,
                    "test_type": test_type,
                },
                "upload_success": status == "success",
                "database_success": status in {"success", "running"},
                "progress_message": {
                    "success": "上传完成",
                    "failed": "上传失败: simulating fixture",
                    "running": "上传中",
                }[status],
                "error": None if status != "failed" else "simulating fixture failure",
                "seed": SEED_MARKER,
            }
        )
    return records


def build_fake_messages() -> list[dict]:
    now = _utc_now()
    messages = []
    for index, record in enumerate(build_fake_upload_records()[:4]):
        created = now - timedelta(minutes=15 * (index + 1))
        messages.append(
            {
                "_id": f"sim-message-{index + 1:03d}",
                "new": bool(record.get("new")),
                "status": record.get("status"),
                "created_at": _iso(created),
                "title": f"[Simulating] {record['file_desc']['model']} {record['file_desc']['test_type']}",
                "message": record.get("progress_message") or "simulating upload event",
                "file_desc": record.get("file_desc"),
                "seed": SEED_MARKER,
            }
        )
    return messages


def _collection_empty(collection_name: str) -> bool:
    store = get_platform_store()
    return store[collection_name].find_one({}) is None


def seed_scan_gateways() -> None:
    collection = get_platform_store()[setting.ROBOT_SCAN_GATEWAY_COLLECTION]
    if collection.find_one({"gateway": "192.168.6.1"}):
        return
    now = _iso(_utc_now())
    collection.update_one(
        {"gateway": "192.168.6.1"},
        {
            "$set": {"gateway": "192.168.6.1", "updated_at": now, "seed": SEED_MARKER},
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )


def seed_robot_scan_cache(port: int = setting.ROBOT_HEALTH_PORT) -> None:
    result = build_fake_scan_result(port)
    robot_service.save_robot_scan_cache(
        result,
        port=port,
        network=None,
        scan_started_at=_iso(_utc_now()),
        scan_duration_ms=12,
    )


def seed_upload_records() -> None:
    collection = get_platform_store()[setting.DATA_UPLOAD_RECORD_COLLECTION]
    if not _collection_empty(setting.DATA_UPLOAD_RECORD_COLLECTION):
        return
    for record in build_fake_upload_records():
        collection.insert_one(record)


def seed_messages() -> None:
    collection = get_platform_store()[setting.DATA_UPLOAD_STATUS_COLLECTION]
    if not _collection_empty(setting.DATA_UPLOAD_STATUS_COLLECTION):
        return
    for message in build_fake_messages():
        collection.insert_one(message)


def ensure_simulating_seed() -> dict:
    """Populate simulating SQLite fixtures when the profile is empty/missing robots."""
    if not setting.use_sqlite_persistence():
        return {"seeded": False, "reason": "simulating disabled"}

    seed_scan_gateways()
    seed_robot_scan_cache()
    seed_upload_records()
    seed_messages()
    logger.info("Simulating fixtures ensured under %s", setting.get_active_db_dir())
    return {
        "seeded": True,
        "robots": len(build_fake_robots()),
        "upload_records": len(build_fake_upload_records()),
        "messages": len(build_fake_messages()),
        "db_dir": str(setting.get_active_db_dir()),
    }


def find_fake_robot(ip: str, port: int = setting.ROBOT_HEALTH_PORT) -> dict | None:
    for robot in build_fake_robots(port):
        if robot["ip"] == ip:
            return dict(robot)
    return None
