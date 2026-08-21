from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
import hashlib
from pathlib import Path
import random
import re
from typing import Any

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

import core.config as setting
from core.database import mongodb

from modules.data_analysis.data import serialize_mongo_doc
from core.logging import get_logger

logger = get_logger(__name__)
from modules.data_analysis.test_names import canonical_test_type


STALE_UPLOAD_RECORD_MINUTES = 120
ACTIVE_UPLOAD_STATUSES = {"queued", "running", "retrying"}
TERMINAL_UPLOAD_STATUSES = {"success", "failed"}
STAGE_HISTORY_LIMIT = 100


def normalize_record_id(record_id: str) -> str | ObjectId:
    if setting.use_sqlite_persistence():
        return str(record_id)
    return ObjectId(record_id)


def to_mongo_safe(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime) and setting.use_sqlite_persistence():
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): to_mongo_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_mongo_safe(item) for item in value]
    return value


def get_upload_record_collection():
    if setting.use_sqlite_persistence():
        from core.sqlite_store import get_platform_store
        from modules.system import simulating_seed

        simulating_seed.ensure_simulating_seed()
        return get_platform_store()[setting.DATA_UPLOAD_RECORD_COLLECTION]
    if mongodb.client is None and not mongodb.connect():
        raise RuntimeError("Upload record database connection failed")
    return mongodb.get_database(setting.MESSAGE_COLLECTION)[setting.DATA_UPLOAD_RECORD_COLLECTION]


def ensure_upload_record_indexes() -> None:
    collection = get_upload_record_collection()
    create_index = getattr(collection, "create_index", None)
    if not create_index:
        return
    create_index("idempotency_key", unique=True, sparse=True)
    create_index([("status", 1), ("next_retry_at", 1)])
    create_index([("notification_status", 1), ("notification_next_retry_at", 1)])


def get_upload_record(record_id: str | None) -> dict[str, Any] | None:
    if not record_id:
        return None
    try:
        return get_upload_record_collection().find_one({"_id": normalize_record_id(record_id)})
    except Exception as exc:
        logger.warning("Unable to read upload record %s: %s", record_id, exc)
        return None


def get_upload_record_by_idempotency_key(idempotency_key: str | None) -> dict[str, Any] | None:
    normalized = str(idempotency_key or "").strip()
    if not normalized:
        return None
    try:
        return get_upload_record_collection().find_one({"idempotency_key": normalized})
    except Exception as exc:
        logger.warning("Unable to resolve upload idempotency key %s: %s", normalized, exc)
        return None


def _nested_get(document: dict[str, Any], path: str) -> Any:
    current: Any = document
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _sqlite_record_matches(
    document: dict[str, Any],
    *,
    record_id: str | None = None,
    status: str | None = None,
    model: str | None = None,
    barcode: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> bool:
    if record_id and str(document.get("_id")) != str(record_id):
        return False
    if status and document.get("status") != status:
        return False
    if model:
        models = {
            _nested_get(document, "file_desc.model"),
            _nested_get(document, "result.model"),
            _nested_get(document, "upload_result.model"),
        }
        if model not in models:
            return False
    if barcode:
        needle = str(barcode).strip().lower()
        haystacks = [
            str(_nested_get(document, "file_desc.sn") or ""),
            str(_nested_get(document, "result.sn") or ""),
            str(_nested_get(document, "upload_result.sn") or ""),
            str(_nested_get(document, "csv_file.name") or ""),
        ]
        if not any(needle in value.lower() for value in haystacks):
            return False

    start_time = parse_date_bound(start_date)
    end_time = parse_date_bound(end_date, end_of_day=True)
    if start_time or end_time:
        raw_started = document.get("request_started_at")
        if not raw_started:
            return False
        try:
            started = datetime.fromisoformat(str(raw_started).replace("Z", "+00:00"))
            if getattr(started, "tzinfo", None) is not None:
                started = started.replace(tzinfo=None)
        except ValueError:
            return False
        if start_time and started < start_time:
            return False
        if end_time and started > end_time:
            return False
    return True


def parse_date_bound(value: str | None, *, end_of_day: bool = False) -> datetime | None:
    if not value:
        return None

    raw_value = str(value).strip()
    if not raw_value:
        return None

    try:
        if len(raw_value) == 10:
            parsed_date = datetime.fromisoformat(raw_value).date()
            return datetime.combine(
                parsed_date,
                datetime.max.time() if end_of_day else datetime.min.time(),
            )
        parsed_datetime = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        if getattr(parsed_datetime, "tzinfo", None) is not None:
            parsed_datetime = parsed_datetime.replace(tzinfo=None)
        return parsed_datetime
    except ValueError:
        logger.warning(f"Invalid upload record date filter ignored: {value}")
        return None


def build_upload_record_query(
    *,
    record_id: str | None = None,
    status: str | None = None,
    model: str | None = None,
    barcode: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    query: dict[str, Any] = {}
    and_queries: list[dict[str, Any]] = []

    if record_id:
        try:
            query["_id"] = normalize_record_id(record_id)
        except Exception:
            logger.warning(f"Invalid upload record id ignored: {record_id}")

    if status:
        query["status"] = status

    if model:
        and_queries.append(
            {
                "$or": [
                    {"file_desc.model": model},
                    {"result.model": model},
                    {"upload_result.model": model},
                ]
            }
        )

    if barcode:
        escaped_barcode = re.escape(str(barcode).strip())
        if escaped_barcode:
            and_queries.append(
                {
                    "$or": [
                        {"file_desc.sn": {"$regex": escaped_barcode, "$options": "i"}},
                        {"result.sn": {"$regex": escaped_barcode, "$options": "i"}},
                        {"upload_result.sn": {"$regex": escaped_barcode, "$options": "i"}},
                        {"csv_file.name": {"$regex": escaped_barcode, "$options": "i"}},
                    ]
                }
            )

    start_time = parse_date_bound(start_date)
    end_time = parse_date_bound(end_date, end_of_day=True)
    if start_time or end_time:
        request_time_query = {}
        if start_time:
            request_time_query["$gte"] = start_time
        if end_time:
            request_time_query["$lte"] = end_time
        query["request_started_at"] = request_time_query

    if and_queries:
        query["$and"] = and_queries

    return query


def resolve_record_model(record: dict[str, Any]) -> str:
    return (
        (record.get("file_desc") or {}).get("model")
        or (record.get("result") or {}).get("model")
        or (record.get("upload_result") or {}).get("model")
        or "Unknown"
    )


def is_valid_product_model(model: Any) -> bool:
    normalized = str(model or "").strip().upper()
    return bool(normalized and normalized not in {"NA", "N/A", "UNKNOWN", "-"})


def resolve_record_test_type(record: dict[str, Any]) -> str:
    return canonical_test_type(
        (record.get("result") or {}).get("test_type")
        or (record.get("file_desc") or {}).get("test_type")
        or (record.get("upload_result") or {}).get("upload_config_key")
    )


def parse_record_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if getattr(value, "tzinfo", None) is not None else value
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if getattr(parsed, "tzinfo", None) is not None:
                parsed = parsed.replace(tzinfo=None)
            return parsed
        except ValueError:
            return None
    return None


def resolve_record_duration_seconds(record: dict[str, Any]) -> float | None:
    start_time = parse_record_datetime(record.get("request_started_at"))
    end_time = parse_record_datetime(record.get("request_finished_at"))
    if start_time is None or end_time is None:
        return None
    return max(0.0, (end_time - start_time).total_seconds())


def summarize_test_duration_stats(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    duration_map: dict[str, dict[str, Any]] = {}
    for record in records:
        if record.get("status") != "success":
            continue

        duration_seconds = resolve_record_duration_seconds(record)
        if duration_seconds is None:
            continue

        model = resolve_record_model(record)
        test_type = str(resolve_record_test_type(record))
        if not test_type:
            continue
        group_key = f"{model}::{test_type}"
        stats = duration_map.setdefault(
            group_key,
            {
                "model": model,
                "test_type": test_type,
                "count": 0,
                "total_seconds": 0.0,
                "avg_seconds": 0.0,
            },
        )
        stats["count"] += 1
        stats["total_seconds"] += duration_seconds

    for stats in duration_map.values():
        count = stats["count"]
        stats["avg_seconds"] = round(stats["total_seconds"] / count, 1) if count else 0.0
        stats.pop("total_seconds", None)

    return sorted(
        duration_map.values(),
        key=lambda item: (-item["avg_seconds"], item["model"], item["test_type"]),
    )


def summarize_product_stats(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    product_map: dict[str, dict[str, Any]] = {}
    for record in records:
        model = resolve_record_model(record)
        if not is_valid_product_model(model):
            continue
        stats = product_map.setdefault(
            model,
            {
                "model": model,
                "total": 0,
                "finished": 0,
                "success": 0,
                "failed": 0,
                "running": 0,
                "success_rate": 0,
            },
        )
        stats["total"] += 1
        status = record.get("status")
        if status in ACTIVE_UPLOAD_STATUSES:
            stats["running"] += 1
        elif status == "success":
            stats["finished"] += 1
            stats["success"] += 1
        else:
            stats["finished"] += 1
            stats["failed"] += 1

    for stats in product_map.values():
        finished = stats["finished"]
        stats["success_rate"] = round((stats["success"] / finished) * 100, 1) if finished else 0

    return sorted(
        product_map.values(),
        key=lambda item: (-item["success_rate"], -item["finished"], item["model"]),
    )


def build_file_info(path_value: str | None, name: str | None = None) -> dict[str, Any] | None:
    if not path_value and not name:
        return None

    path = Path(path_value) if path_value else None
    info: dict[str, Any] = {
        "path": str(path_value or ""),
        "name": name or (path.name if path else ""),
    }
    try:
        if path and path.exists():
            info["size"] = path.stat().st_size
    except OSError as exc:
        info["stat_error"] = str(exc)
    return info


def build_file_info_with_integrity(path_value: str, name: str | None = None) -> dict[str, Any]:
    info = build_file_info(path_value, name) or {"path": path_value, "name": name or ""}
    digest = hashlib.sha256()
    size = 0
    with open(path_value, "rb") as handle:
        while chunk := handle.read(1024 * 1024):
            size += len(chunk)
            digest.update(chunk)
    info.update({"size": size, "sha256": digest.hexdigest()})
    return info


def create_upload_record(
    csv_path: str | None,
    zip_path: str | None = None,
    *,
    csv_name: str | None = None,
    zip_name: str | None = None,
    source: str = "api",
    idempotency_key: str | None = None,
    csv_size: int | None = None,
    csv_sha256: str | None = None,
) -> str | None:
    try:
        normalized_idempotency_key = str(idempotency_key or "").strip() or None
        collection = get_upload_record_collection()
        ensure_upload_record_indexes()
        if normalized_idempotency_key:
            existing = collection.find_one({"idempotency_key": normalized_idempotency_key})
            if existing:
                return str(existing["_id"])

        now = datetime.now()
        csv_info = build_file_info(csv_path, csv_name)
        if csv_info is not None:
            if csv_size is not None:
                csv_info["expected_size"] = int(csv_size)
            if csv_sha256:
                csv_info["expected_sha256"] = str(csv_sha256).lower()
        doc = {
            "status": "running",
            "source": source,
            "idempotency_key": normalized_idempotency_key,
            "name_key": f"upload:{normalized_idempotency_key}" if normalized_idempotency_key else None,
            "request_started_at": now,
            "request_finished_at": None,
            "updated_at": now,
            "csv_file": csv_info,
            "zip_file": build_file_info(zip_path, zip_name),
            "file_desc": None,
            "progress_stage": "created",
            "progress_message": "已创建上传任务",
            "stage_history": [
                {
                    "stage": "created",
                    "message": "已创建上传任务",
                    "started_at": now,
                    "finished_at": None,
                    "duration_seconds": None,
                }
            ],
            "checkpoint": {},
            "job": None,
            "attempt_count": 0,
            "max_attempts": setting.UPLOAD_MAX_ATTEMPTS,
            "next_retry_at": None,
            "retryable": None,
            "retry_history": [],
            "lease_owner": None,
            "lease_expires_at": None,
            "failure_stage": None,
            "failure_code": None,
            "error_detail": None,
            "upload_success": None,
            "database_success": None,
            "slack_success": None,
            "notification_status": "pending",
            "notification_attempt_count": 0,
            "notification_next_retry_at": None,
            "notification_lease_expires_at": None,
            "notification_payload": None,
            "notification_error": None,
            "slack_notified_at": None,
            "result": None,
            "error": None,
        }
        if normalized_idempotency_key is None:
            doc.pop("idempotency_key", None)
            doc.pop("name_key", None)
        insert_result = collection.insert_one(to_mongo_safe(doc))
        return str(insert_result.inserted_id)
    except DuplicateKeyError:
        if idempotency_key:
            existing = get_upload_record_collection().find_one(
                {"idempotency_key": str(idempotency_key).strip()}
            )
            if existing:
                return str(existing["_id"])
        logger.warning("Duplicate upload record rejected: idempotency_key=%s", idempotency_key)
        return None
    except Exception as exc:
        logger.error(f"Failed to create upload record: {exc}")
        return None


def update_upload_record(record_id: str | None, fields: dict[str, Any]) -> None:
    if not record_id:
        return

    try:
        update_fields = {
            **to_mongo_safe(fields),
            "updated_at": datetime.now(),
        }
        get_upload_record_collection().update_one(
            {"_id": normalize_record_id(record_id)},
            {"$set": update_fields},
        )
    except Exception as exc:
        logger.error(f"Failed to update upload record {record_id}: {exc}")


def update_upload_attempt(
    record_id: str | None,
    expected_attempt: int | None,
    fields: dict[str, Any],
) -> bool:
    if expected_attempt is None:
        update_upload_record(record_id, fields)
        return bool(record_id)
    if not record_id:
        return False
    try:
        result = get_upload_record_collection().update_one(
            {
                "_id": normalize_record_id(record_id),
                "status": "running",
                "attempt_count": int(expected_attempt),
            },
            {"$set": {**to_mongo_safe(fields), "updated_at": datetime.now()}},
        )
        return int(getattr(result, "matched_count", 0) or 0) > 0
    except Exception as exc:
        logger.error("Failed to update upload record %s attempt %s: %s", record_id, expected_attempt, exc)
        return False


def renew_upload_attempt_lease(record_id: str, expected_attempt: int) -> bool:
    now = datetime.now()
    try:
        result = get_upload_record_collection().update_one(
            {
                "_id": normalize_record_id(record_id),
                "status": "running",
                "attempt_count": int(expected_attempt),
            },
            {
                "$set": to_mongo_safe(
                    {
                        "lease_expires_at": now + timedelta(seconds=setting.UPLOAD_LEASE_SECONDS),
                        "updated_at": now,
                    }
                )
            },
        )
        return int(getattr(result, "matched_count", 0) or 0) > 0
    except Exception as exc:
        logger.warning("Unable to renew upload lease %s attempt %s: %s", record_id, expected_attempt, exc)
        return False


def record_upload_progress(
    record_id: str | None,
    stage: str,
    message: str,
    *,
    checkpoint: dict[str, Any] | None = None,
    expected_attempt: int | None = None,
) -> bool:
    record = get_upload_record(record_id)
    if record is None:
        return False
    if expected_attempt is not None and (
        record.get("status") != "running"
        or int(record.get("attempt_count") or 0) != int(expected_attempt)
    ):
        return False

    now = datetime.now()
    history = list(record.get("stage_history") or [])[-STAGE_HISTORY_LIMIT:]
    if history and history[-1].get("stage") == stage:
        history[-1] = {**history[-1], "message": message}
    else:
        if history and not history[-1].get("finished_at"):
            started_at = parse_record_datetime(history[-1].get("started_at"))
            history[-1] = {
                **history[-1],
                "finished_at": now,
                "duration_seconds": (
                    round(max(0.0, (now - started_at).total_seconds()), 3)
                    if started_at
                    else None
                ),
            }
        history.append(
            {
                "stage": stage,
                "message": message,
                "started_at": now,
                "finished_at": None,
                "duration_seconds": None,
            }
        )

    fields: dict[str, Any] = {
        "progress_stage": stage,
        "progress_message": message,
        "stage_history": history[-STAGE_HISTORY_LIMIT:],
    }
    if checkpoint:
        fields["checkpoint"] = {**(record.get("checkpoint") or {}), **checkpoint}
    if record.get("status") == "running" and record.get("lease_owner"):
        fields["lease_expires_at"] = now + timedelta(seconds=setting.UPLOAD_LEASE_SECONDS)
    if expected_attempt is None:
        update_upload_record(record_id, fields)
        return True
    result = get_upload_record_collection().update_one(
        {
            "_id": normalize_record_id(str(record["_id"])),
            "status": "running",
            "attempt_count": int(expected_attempt),
        },
        {"$set": to_mongo_safe({**fields, "updated_at": now})},
    )
    return int(getattr(result, "matched_count", 0) or 0) > 0


def enqueue_upload_record(
    record_id: str | None,
    *,
    csv_path: str,
    zip_path: str | None,
    meta: dict[str, Any] | None,
) -> bool:
    record = get_upload_record(record_id)
    if record is None:
        return False
    if record.get("status") == "success":
        return True
    if record.get("job") and record.get("status") in ACTIVE_UPLOAD_STATUSES:
        return True

    now = datetime.now()
    csv_info = record.get("csv_file") or {}
    if not csv_info.get("sha256") or csv_info.get("path") != csv_path:
        try:
            csv_info = build_file_info_with_integrity(csv_path, csv_info.get("name"))
        except OSError as exc:
            logger.error("Unable to fingerprint queued CSV %s: %s", csv_path, exc)
            return False
    fields = {
        "status": "queued",
        "job": {
            "csv_path": csv_path,
            "zip_path": zip_path,
            "meta": meta or {},
        },
        "request_finished_at": None,
        "next_retry_at": now,
        "retryable": None,
        "failure_stage": None,
        "failure_code": None,
        "error": None,
        "error_detail": None,
        "lease_owner": None,
        "lease_expires_at": None,
        "csv_file": csv_info,
    }
    collection = get_upload_record_collection()
    result = collection.update_one(
        {
            "_id": normalize_record_id(str(record["_id"])),
            "status": record.get("status"),
        },
        {"$set": to_mongo_safe({**fields, "updated_at": now})},
    )
    if int(getattr(result, "matched_count", 0) or 0) == 0:
        refreshed = get_upload_record(record_id)
        return bool(refreshed and refreshed.get("job") and refreshed.get("status") in ACTIVE_UPLOAD_STATUSES)
    record_upload_progress(record_id, "queued", "上传任务已进入持久化队列")
    return True


def calculate_retry_delay_seconds(attempt_count: int) -> float:
    exponent = max(0, int(attempt_count) - 1)
    base_delay = min(
        setting.UPLOAD_RETRY_MAX_SECONDS,
        setting.UPLOAD_RETRY_BASE_SECONDS * (2 ** exponent),
    )
    return round(base_delay * random.uniform(0.8, 1.2), 3)


def _record_is_due(record: dict[str, Any], field: str, now: datetime) -> bool:
    due_at = parse_record_datetime(record.get(field))
    return due_at is None or due_at <= now


def claim_due_upload_record(owner: str) -> dict[str, Any] | None:
    collection = get_upload_record_collection()
    now = datetime.now()
    if setting.use_sqlite_persistence():
        candidates = [
            record
            for record in collection.find({})
            if record.get("status") in {"queued", "retrying"}
            and record.get("job")
            and _record_is_due(record, "next_retry_at", now)
        ]
    else:
        candidates = list(
            collection.find(
                {
                    "status": {"$in": ["queued", "retrying"]},
                    "next_retry_at": {"$lte": now},
                    "job": {"$ne": None},
                }
            ).sort("next_retry_at", 1).limit(20)
        )

    candidates.sort(key=lambda item: str(item.get("next_retry_at") or ""))
    for record in candidates:
        current_attempt = int(record.get("attempt_count") or 0)
        result = collection.update_one(
            {
                "_id": normalize_record_id(str(record["_id"])),
                "status": record.get("status"),
                "attempt_count": current_attempt,
            },
            {
                "$set": to_mongo_safe(
                    {
                        "status": "running",
                        "attempt_count": current_attempt + 1,
                        "attempt_started_at": now,
                        "next_retry_at": None,
                        "lease_owner": owner,
                        "lease_expires_at": now + timedelta(seconds=setting.UPLOAD_LEASE_SECONDS),
                        "updated_at": now,
                    }
                )
            },
        )
        if int(getattr(result, "matched_count", 0) or 0) > 0:
            claimed = get_upload_record(str(record["_id"]))
            if claimed:
                record_upload_progress(
                    str(record["_id"]),
                    "running",
                    f"正在执行上传，第 {current_attempt + 1} 次尝试",
                )
            return claimed
    return None


def schedule_upload_retry(
    record_id: str | None,
    *,
    failure_stage: str,
    failure_code: str,
    error: str,
    error_detail: str | None = None,
    expected_attempt: int | None = None,
) -> bool:
    record = get_upload_record(record_id)
    if record is None:
        return False
    current_status = record.get("status")
    if current_status not in ACTIVE_UPLOAD_STATUSES:
        return False
    attempt_count = int(record.get("attempt_count") or 0)
    if expected_attempt is not None and (
        current_status != "running" or attempt_count != int(expected_attempt)
    ):
        return False
    max_attempts = int(record.get("max_attempts") or setting.UPLOAD_MAX_ATTEMPTS)
    if not record.get("job") or attempt_count >= max_attempts:
        return False

    now = datetime.now()
    delay_seconds = calculate_retry_delay_seconds(attempt_count)
    next_retry_at = now + timedelta(seconds=delay_seconds)
    retry_history = list(record.get("retry_history") or [])
    retry_history.append(
        {
            "attempt": attempt_count,
            "failed_at": now,
            "failure_stage": failure_stage,
            "failure_code": failure_code,
            "error": error,
            "next_retry_at": next_retry_at,
        }
    )
    retry_fields = {
        "status": "retrying",
        "request_finished_at": None,
        "next_retry_at": next_retry_at,
        "retryable": True,
        "retry_history": retry_history[-20:],
        "failure_stage": failure_stage,
        "failure_code": failure_code,
        "error": error,
        "error_detail": error_detail or error,
        "lease_owner": None,
        "lease_expires_at": None,
    }
    result = get_upload_record_collection().update_one(
        {
            "_id": normalize_record_id(str(record["_id"])),
            "status": current_status,
            "attempt_count": attempt_count,
        },
        {"$set": to_mongo_safe({**retry_fields, "updated_at": now})},
    )
    if int(getattr(result, "matched_count", 0) or 0) == 0:
        return False
    record_upload_progress(
        record_id,
        "retrying",
        f"第 {attempt_count} 次上传失败，将在 {round(delay_seconds, 1)} 秒后重试",
    )
    return True


def recover_expired_upload_leases() -> int:
    collection = get_upload_record_collection()
    now = datetime.now()
    if setting.use_sqlite_persistence():
        records = [
            record
            for record in collection.find({})
            if record.get("status") == "running"
            and record.get("job")
            and parse_record_datetime(record.get("lease_expires_at"))
            and parse_record_datetime(record.get("lease_expires_at")) <= now
        ]
    else:
        records = list(
            collection.find(
                {
                    "status": "running",
                    "job": {"$ne": None},
                    "lease_expires_at": {"$lte": now},
                }
            )
        )

    recovered = 0
    for record in records:
        record_id = str(record["_id"])
        expected_attempt = int(record.get("attempt_count") or 0)
        if schedule_upload_retry(
            record_id,
            failure_stage="worker_interrupted",
            failure_code="upload_lease_expired",
            error="后台上传任务租约过期，正在恢复执行",
            expected_attempt=expected_attempt,
        ):
            recovered += 1
        else:
            error = "后台上传任务租约过期且已达到最大重试次数"
            finished = finish_upload_record(
                record_id,
                upload_success=False,
                database_success=False,
                slack_success=None,
                failure_stage="worker_interrupted",
                failure_code="upload_lease_expired",
                error=error,
                expected_attempt=expected_attempt,
            )
            if finished:
                job = record.get("job") or {}
                queue_upload_notification(
                    record_id,
                    result=None,
                    csv_path=str(job.get("csv_path") or ""),
                    zip_path=job.get("zip_path") or None,
                    error_message=error,
                    upload_success=False,
                    database_success=False,
                )
    return recovered


def set_file_description(record_id: str | None, file_desc: dict[str, Any]) -> None:
    update_upload_record(record_id, {"file_desc": file_desc})


def resolve_failure_reason(
    *,
    upload_success: bool,
    database_success: bool,
    slack_success: bool | None,
    error: str | None,
) -> str | None:
    if error:
        return error
    if not upload_success:
        return "数据上传失败"
    if not database_success:
        return "数据库写入失败"
    if slack_success is False:
        return "Slack 通知失败"
    return None


def finish_upload_record(
    record_id: str | None,
    *,
    upload_success: bool,
    database_success: bool,
    slack_success: bool | None,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    failure_stage: str | None = None,
    failure_code: str | None = None,
    error_detail: str | None = None,
    only_if_running: bool = False,
    expected_attempt: int | None = None,
) -> bool:
    finished_success = upload_success and database_success
    failure_reason = None if finished_success else resolve_failure_reason(
        upload_success=upload_success,
        database_success=database_success,
        slack_success=slack_success,
        error=error,
    )
    resolved_failure_stage = failure_stage
    finish_fields = {
        "status": "success" if finished_success else "failed",
        "request_finished_at": datetime.now(),
        "progress_stage": "finished",
        "progress_message": "上传完成" if finished_success else f"上传失败: {failure_reason or '未知错误'}",
        "upload_success": upload_success,
        "database_success": database_success,
        "slack_success": slack_success,
        "result": result,
        "error": failure_reason,
        "failure_stage": resolved_failure_stage if not finished_success else None,
        "failure_code": failure_code if not finished_success else None,
        "error_detail": (error_detail or failure_reason) if not finished_success else None,
        "retryable": False if not finished_success else None,
        "next_retry_at": None,
        "lease_owner": None,
        "lease_expires_at": None,
    }
    if slack_success is not None:
        finish_fields["slack_notified_at"] = datetime.now()
        finish_fields["notification_status"] = "success" if slack_success else "retrying"
    if expected_attempt is not None:
        try:
            if not record_id:
                return False
            update_fields = {**to_mongo_safe(finish_fields), "updated_at": datetime.now()}
            result = get_upload_record_collection().update_one(
                {
                    "_id": normalize_record_id(record_id),
                    "status": "running",
                    "attempt_count": int(expected_attempt),
                },
                {"$set": update_fields},
            )
            if int(getattr(result, "matched_count", 0) or 0) == 0:
                return False
            record_upload_progress(record_id, "finished", finish_fields["progress_message"])
            return True
        except Exception as exc:
            logger.error("Failed to finish upload record %s attempt %s: %s", record_id, expected_attempt, exc)
            return False
    if only_if_running:
        try:
            if not record_id:
                return False
            record = get_upload_record(record_id)
            if record is None or record.get("status") not in ACTIVE_UPLOAD_STATUSES:
                return False
            update_fields = {**to_mongo_safe(finish_fields), "updated_at": datetime.now()}
            result = get_upload_record_collection().update_one(
                {"_id": normalize_record_id(record_id), "status": record.get("status")},
                {"$set": update_fields},
            )
            if int(getattr(result, "matched_count", 0) or 0) == 0:
                return False
            record_upload_progress(record_id, "finished", finish_fields["progress_message"])
            return True
        except Exception as exc:
            logger.error(f"Failed to mark upload record {record_id} as failed: {exc}")
            return False

    update_upload_record(record_id, finish_fields)
    record_upload_progress(record_id, "finished", finish_fields["progress_message"])
    return bool(record_id)


def mark_upload_record_failed(
    record_id: str | None,
    *,
    failure_stage: str,
    failure_code: str,
    error: str,
    error_detail: str | None = None,
    force: bool = False,
) -> bool:
    """Persist a failure that happened outside the upload worker request.

    This is used by clients when a multipart request fails before FastAPI can
    parse the body and enter the upload handler.
    """
    record = get_upload_record(record_id)
    if record is None or record.get("status") in TERMINAL_UPLOAD_STATUSES:
        return False
    if not force and record.get("job") and record.get("status") in ACTIVE_UPLOAD_STATUSES:
        update_upload_record(
            record_id,
            {
                "last_client_error": error,
                "last_client_error_detail": error_detail or error,
                "last_client_error_at": datetime.now(),
            },
        )
        return False

    return finish_upload_record(
        record_id,
        upload_success=False,
        database_success=False,
        slack_success=None,
        error=error,
        failure_stage=failure_stage,
        failure_code=failure_code,
        error_detail=error_detail,
        only_if_running=True,
    )


def queue_upload_notification(
    record_id: str | None,
    *,
    result: dict[str, Any] | None,
    csv_path: str,
    zip_path: str | None,
    error_message: str | None,
    upload_success: bool,
    database_success: bool,
) -> None:
    if not record_id:
        return
    update_upload_record(
        record_id,
        {
            "notification_status": "queued",
            "notification_next_retry_at": datetime.now(),
            "notification_payload": {
                "result": result,
                "csv_path": csv_path,
                "zip_path": zip_path,
                "error_message": error_message,
                "upload_success": upload_success,
                "database_success": database_success,
            },
            "notification_error": None,
            "notification_owner": None,
            "notification_lease_expires_at": None,
        },
    )


def claim_due_upload_notification(owner: str) -> dict[str, Any] | None:
    collection = get_upload_record_collection()
    now = datetime.now()
    if setting.use_sqlite_persistence():
        candidates = [
            record
            for record in collection.find({})
            if record.get("notification_status") in {"queued", "retrying"}
            and record.get("notification_payload")
            and _record_is_due(record, "notification_next_retry_at", now)
        ]
    else:
        candidates = list(
            collection.find(
                {
                    "notification_status": {"$in": ["queued", "retrying"]},
                    "notification_next_retry_at": {"$lte": now},
                    "notification_payload": {"$ne": None},
                }
            ).sort("notification_next_retry_at", 1).limit(20)
        )
    candidates.sort(key=lambda item: str(item.get("notification_next_retry_at") or ""))
    for record in candidates:
        attempts = int(record.get("notification_attempt_count") or 0)
        result = collection.update_one(
            {
                "_id": normalize_record_id(str(record["_id"])),
                "notification_status": record.get("notification_status"),
                "notification_attempt_count": attempts,
            },
            {
                "$set": to_mongo_safe(
                    {
                        "notification_status": "running",
                        "notification_attempt_count": attempts + 1,
                        "notification_owner": owner,
                        "notification_lease_expires_at": now
                        + timedelta(seconds=setting.UPLOAD_LEASE_SECONDS),
                        "notification_next_retry_at": None,
                        "updated_at": now,
                    }
                )
            },
        )
        if int(getattr(result, "matched_count", 0) or 0) > 0:
            return get_upload_record(str(record["_id"]))
    return None


def finish_upload_notification(
    record_id: str,
    *,
    success: bool,
    error: str | None = None,
    expected_attempt: int | None = None,
) -> bool:
    record = get_upload_record(record_id)
    if record is None:
        return False
    attempts = int(record.get("notification_attempt_count") or 0)
    if success:
        fields = {
            "slack_success": True,
            "slack_notified_at": datetime.now(),
            "notification_status": "success",
            "notification_error": None,
            "notification_payload": None,
            "notification_owner": None,
            "notification_lease_expires_at": None,
            "notification_next_retry_at": None,
        }
    elif attempts >= setting.UPLOAD_NOTIFICATION_MAX_ATTEMPTS:
        fields = {
            "slack_success": False,
            "notification_status": "failed",
            "notification_error": error or "Slack notification failed",
            "notification_owner": None,
            "notification_lease_expires_at": None,
            "notification_next_retry_at": None,
        }
    else:
        delay_seconds = calculate_retry_delay_seconds(attempts)
        fields = {
            "slack_success": False,
            "notification_status": "retrying",
            "notification_error": error or "Slack notification failed",
            "notification_owner": None,
            "notification_lease_expires_at": None,
            "notification_next_retry_at": datetime.now() + timedelta(seconds=delay_seconds),
        }

    if expected_attempt is None:
        update_upload_record(record_id, fields)
        return True
    result = get_upload_record_collection().update_one(
        {
            "_id": normalize_record_id(record_id),
            "notification_status": "running",
            "notification_attempt_count": int(expected_attempt),
        },
        {"$set": to_mongo_safe({**fields, "updated_at": datetime.now()})},
    )
    return int(getattr(result, "matched_count", 0) or 0) > 0


def recover_expired_upload_notifications() -> int:
    collection = get_upload_record_collection()
    now = datetime.now()
    if setting.use_sqlite_persistence():
        records = [
            record
            for record in collection.find({})
            if record.get("notification_status") == "running"
            and parse_record_datetime(record.get("notification_lease_expires_at"))
            and parse_record_datetime(record.get("notification_lease_expires_at")) <= now
        ]
    else:
        records = list(
            collection.find(
                {
                    "notification_status": "running",
                    "notification_lease_expires_at": {"$lte": now},
                }
            )
        )
    recovered = 0
    for record in records:
        result = collection.update_one(
            {
                "_id": normalize_record_id(str(record["_id"])),
                "notification_status": "running",
                "notification_attempt_count": int(record.get("notification_attempt_count") or 0),
            },
            {
                "$set": to_mongo_safe(
                    {
                        "notification_status": "retrying",
                        "notification_next_retry_at": now,
                        "notification_owner": None,
                        "notification_lease_expires_at": None,
                        "notification_error": "Notification worker lease expired",
                        "updated_at": now,
                    }
                )
            },
        )
        recovered += int(getattr(result, "modified_count", 0) or 0)
    return recovered


def expire_stale_upload_records(max_age_minutes: int = STALE_UPLOAD_RECORD_MINUTES) -> int:
    """Fail running tasks that stopped reporting progress after a worker interruption."""
    recover_expired_upload_leases()
    collection = get_upload_record_collection()
    cutoff = datetime.now() - timedelta(minutes=max(1, max_age_minutes))
    failure_fields = {
        "status": "failed",
        "request_finished_at": datetime.now(),
        "updated_at": datetime.now(),
        "progress_stage": "finished",
        "progress_message": "上传任务长时间无更新，已标记为失败",
        "upload_success": False,
        "database_success": False,
        "slack_success": None,
        "failure_stage": "worker_interrupted",
        "failure_code": "stale_upload_record",
        "error": "上传任务长时间无更新，可能因服务重启或任务中断而结束",
        "error_detail": f"最后更新时间早于 {cutoff.isoformat(timespec='seconds')}",
    }

    if setting.use_sqlite_persistence():
        expired = 0
        for record in collection.find({"status": "running"}):
            updated_at = parse_record_datetime(record.get("updated_at") or record.get("request_started_at"))
            if updated_at is None or updated_at >= cutoff:
                continue
            result = collection.update_one(
                {"_id": str(record.get("_id")), "status": "running"},
                {"$set": to_mongo_safe(failure_fields)},
            )
            expired += int(getattr(result, "modified_count", 0) or 0)
        return expired

    result = collection.update_many(
        {"status": "running", "updated_at": {"$lt": cutoff}},
        {"$set": failure_fields},
    )
    return int(getattr(result, "modified_count", 0) or 0)


def get_upload_records(
    page: int = 1,
    page_size: int = 20,
    record_id: str | None = None,
    status: str | None = None,
    model: str | None = None,
    barcode: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    try:
        expire_stale_upload_records()
        page = max(page, 1)
        page_size = min(max(page_size, 1), 2000)
        skip = (page - 1) * page_size
        collection = get_upload_record_collection()

        if setting.use_sqlite_persistence():
            matched = [
                serialize_mongo_doc(doc)
                for doc in collection.find({})
                if _sqlite_record_matches(
                    doc,
                    record_id=record_id,
                    status=status,
                    model=model,
                    barcode=barcode,
                    start_date=start_date,
                    end_date=end_date,
                )
            ]
            matched.sort(key=lambda item: str(item.get("request_started_at") or ""), reverse=True)
            return {
                "records": matched[skip : skip + page_size],
                "total": len(matched),
                "page": page,
                "page_size": page_size,
            }

        query = build_upload_record_query(
            record_id=record_id,
            status=status,
            model=model,
            barcode=barcode,
            start_date=start_date,
            end_date=end_date,
        )
        total = collection.count_documents(query)
        cursor = collection.find(query).sort("request_started_at", -1).skip(skip).limit(page_size)
        records = [serialize_mongo_doc(doc) for doc in cursor]
        return {
            "records": records,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except Exception as exc:
        logger.error(f"Error fetching upload records: {str(exc)}")
        return {
            "records": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "error": str(exc),
        }


def get_upload_record_stats(
    record_id: str | None = None,
    status: str | None = None,
    model: str | None = None,
    barcode: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    try:
        expire_stale_upload_records()
        collection = get_upload_record_collection()
        if setting.use_sqlite_persistence():
            records = [
                doc
                for doc in collection.find({})
                if _sqlite_record_matches(
                    doc,
                    record_id=record_id,
                    status=status,
                    model=model,
                    barcode=barcode,
                    start_date=start_date,
                    end_date=end_date,
                )
            ]
        else:
            query = build_upload_record_query(
                record_id=record_id,
                status=status,
                model=model,
                barcode=barcode,
                start_date=start_date,
                end_date=end_date,
            )
            records = list(collection.find(query))
        total = len(records)
        running = sum(1 for record in records if record.get("status") in ACTIVE_UPLOAD_STATUSES)
        success = sum(1 for record in records if record.get("status") == "success")
        finished = total - running
        failed = finished - success
        success_rate = round((success / finished) * 100, 1) if finished else 0
        products = summarize_product_stats(records)
        finished_products = [item for item in products if item.get("finished", 0) > 0]
        highest_product = finished_products[0] if finished_products else None
        lowest_product = (
            sorted(finished_products, key=lambda item: (item["success_rate"], -item["finished"], item["model"]))[0]
            if finished_products
            else None
        )
        return {
            "total": total,
            "finished": finished,
            "success": success,
            "failed": failed,
            "running": running,
            "success_rate": success_rate,
            "highest_product": highest_product,
            "lowest_product": lowest_product,
            "products": products,
            "test_durations": summarize_test_duration_stats(records),
        }
    except Exception as exc:
        logger.error(f"Error fetching upload records: {str(exc)}")
        return {
            "total": 0,
            "finished": 0,
            "success": 0,
            "failed": 0,
            "running": 0,
            "success_rate": 0,
            "highest_product": None,
            "lowest_product": None,
            "products": [],
            "test_durations": [],
            "error": str(exc),
        }


def get_upload_record_filter_options() -> dict:
    try:
        collection = get_upload_record_collection()
        if setting.use_sqlite_persistence():
            documents = list(collection.find({}))
            model_values = {
                value
                for value in [
                    *(_nested_get(doc, "file_desc.model") for doc in documents),
                    *(_nested_get(doc, "result.model") for doc in documents),
                    *(_nested_get(doc, "upload_result.model") for doc in documents),
                ]
                if value
            }
            statuses = sorted({str(doc.get("status")) for doc in documents if doc.get("status")})
            return {"models": sorted(str(value) for value in model_values), "statuses": statuses}

        model_values = {
            value
            for value in [
                *collection.distinct("file_desc.model"),
                *collection.distinct("result.model"),
                *collection.distinct("upload_result.model"),
            ]
            if value
        }
        return {
            "models": sorted(model_values),
            "statuses": sorted([value for value in collection.distinct("status") if value]),
        }
    except Exception as exc:
        logger.error(f"Error fetching upload record filter options: {str(exc)}")
        return {
            "models": [],
            "statuses": [],
            "error": str(exc),
        }
