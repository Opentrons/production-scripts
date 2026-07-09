from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
import re
from typing import Any

from bson import ObjectId

import settings as setting
from database.mongodb import mongodb

from api.services.data import serialize_mongo_doc
from api.services.logging import logger
from api.services.test_names import canonical_test_type


def to_mongo_safe(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): to_mongo_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_mongo_safe(item) for item in value]
    return value


def get_upload_record_collection():
    if mongodb.client is None and not mongodb.connect():
        raise RuntimeError("Upload record database connection failed")
    return mongodb.get_database(setting.MESSAGE_COLLECTION)[setting.DATA_UPLOAD_RECORD_COLLECTION]


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
            query["_id"] = ObjectId(record_id)
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
        if status == "running":
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


def create_upload_record(
    csv_path: str | None,
    zip_path: str | None = None,
    *,
    csv_name: str | None = None,
    zip_name: str | None = None,
    source: str = "api",
) -> str | None:
    try:
        now = datetime.now()
        doc = {
            "status": "running",
            "source": source,
            "request_started_at": now,
            "request_finished_at": None,
            "updated_at": now,
            "csv_file": build_file_info(csv_path, csv_name),
            "zip_file": build_file_info(zip_path, zip_name),
            "file_desc": None,
            "progress_stage": "created",
            "progress_message": "已创建上传任务",
            "upload_success": None,
            "database_success": None,
            "slack_success": None,
            "slack_notified_at": None,
            "result": None,
            "error": None,
        }
        insert_result = get_upload_record_collection().insert_one(doc)
        return str(insert_result.inserted_id)
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
            {"_id": ObjectId(record_id)},
            {"$set": update_fields},
        )
    except Exception as exc:
        logger.error(f"Failed to update upload record {record_id}: {exc}")


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
) -> None:
    finished_success = upload_success and database_success and slack_success is True
    failure_reason = None if finished_success else resolve_failure_reason(
        upload_success=upload_success,
        database_success=database_success,
        slack_success=slack_success,
        error=error,
    )
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
    }
    if slack_success is not None:
        finish_fields["slack_notified_at"] = datetime.now()
    update_upload_record(record_id, finish_fields)


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
        page = max(page, 1)
        page_size = min(max(page_size, 1), 2000)
        skip = (page - 1) * page_size
        query = build_upload_record_query(
            record_id=record_id,
            status=status,
            model=model,
            barcode=barcode,
            start_date=start_date,
            end_date=end_date,
        )

        collection = get_upload_record_collection()
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
        query = build_upload_record_query(
            record_id=record_id,
            status=status,
            model=model,
            barcode=barcode,
            start_date=start_date,
            end_date=end_date,
        )
        records = list(get_upload_record_collection().find(query))
        total = len(records)
        running = sum(1 for record in records if record.get("status") == "running")
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
