"""Persist Opentrons App Log analysis results in MongoDB."""

from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import logging
import tempfile
import threading
from pathlib import Path
from typing import Any
from uuid import uuid4

import core.config as setting
from core.database import mongodb
from modules.agent.llm.service import LLMConfigurationError, llm_service

logger = logging.getLogger(__name__)

_INDEX_READY = False
_INDEX_LOCK = threading.Lock()
_ANALYZER_MODULE: Any | None = None
_ANALYZER_LOCK = threading.Lock()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    return value


def _get_collection():
    global _INDEX_READY
    if mongodb.client is None and not mongodb.connect():
        raise RuntimeError("MongoDB 连接失败，无法保存 App Log 分析记录")
    collection = mongodb.get_database(setting.MESSAGE_COLLECTION)[
        setting.ROBOT_APP_LOG_ANALYSIS_COLLECTION
    ]
    if not _INDEX_READY:
        with _INDEX_LOCK:
            if not _INDEX_READY:
                collection.create_index([("created_at", -1)])
                collection.create_index([("robot_ip", 1), ("created_at", -1)])
                _INDEX_READY = True
    return collection


def _load_analyzer() -> Any:
    """Import ``apps/backend/scripts/analyze_logs.py`` without installing it as a package."""

    global _ANALYZER_MODULE
    if _ANALYZER_MODULE is not None:
        return _ANALYZER_MODULE
    with _ANALYZER_LOCK:
        if _ANALYZER_MODULE is not None:
            return _ANALYZER_MODULE
        script_path = Path(__file__).resolve().parents[3] / "scripts" / "analyze_logs.py"
        if not script_path.is_file():
            raise FileNotFoundError(f"找不到日志分析脚本: {script_path}")
        spec = importlib.util.spec_from_file_location("production_analyze_logs", script_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"无法加载日志分析脚本: {script_path}")
        module = importlib.util.module_from_spec(spec)
        # Register before exec so dataclasses(slots=True) can resolve the module.
        import sys

        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _ANALYZER_MODULE = module
        return module


def _compact_analysis(full: dict[str, Any]) -> dict[str, Any]:
    analyzer = _load_analyzer()
    slim = analyzer.slim_result(full)
    failure = analyzer._pick_last_protocol_failure(full) or {}
    return {
        **slim,
        "category": failure.get("category") or failure.get("error_category"),
        "trigger": failure.get("trigger"),
        "run_id": failure.get("run_id"),
        "command_id": failure.get("command_id"),
        "evidence": list(failure.get("evidence") or [])[:8],
        "time_range": full.get("time_range"),
        "error_count": full.get("error_count"),
        "ignored_error_count": full.get("ignored_error_count"),
        "warnings": list(full.get("warnings") or [])[:10],
        "source_lookup": full.get("source_lookup"),
    }


def analyze_failure_with_llm(summary: dict[str, Any]) -> str | None:
    if not summary or not llm_service.configured:
        return None
    return llm_service.analyze_app_log_failure(summary)


def analyze_app_log_zip(
    zip_bytes: bytes,
    *,
    robot_ip: str,
    archive_name: str,
    device_name: str | None = None,
) -> dict[str, Any]:
    """Analyze an App Log zip in a temp file and return the compact summary."""

    if not zip_bytes:
        raise ValueError("App Log zip 为空，无法分析")
    analyzer = _load_analyzer()
    with tempfile.NamedTemporaryFile(prefix="app-log-", suffix=".zip") as temporary:
        temporary.write(zip_bytes)
        temporary.flush()
        full = analyzer.analyze_archive(Path(temporary.name))
    summary = _compact_analysis(full if isinstance(full, dict) else {})
    summary["ip"] = robot_ip
    summary["archive"] = archive_name
    if device_name:
        summary["robot"] = device_name
    return summary


def save_app_log_analysis(
    *,
    robot_ip: str,
    archive_name: str,
    device_name: str | None = None,
    zip_bytes: bytes | None = None,
    summary: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Create a Mongo analysis record. Analysis failure still stores a failed row."""

    now = _utc_now()
    record: dict[str, Any] = {
        "_id": uuid4().hex,
        "robot_ip": str(robot_ip or "").strip(),
        "device_name": str(device_name or "").strip() or str(robot_ip or "").strip(),
        "archive_name": str(archive_name or "").strip(),
        "status": "failed" if error else "completed",
        "error": error,
        "summary": summary or {},
        "created_at": now,
        "updated_at": now,
    }
    if zip_bytes is not None and summary is None and error is None:
        try:
            record["summary"] = analyze_app_log_zip(
                zip_bytes,
                robot_ip=record["robot_ip"],
                archive_name=record["archive_name"],
                device_name=record["device_name"],
            )
            record["status"] = "completed"
            record["error"] = None
            try:
                record["llm_reason"] = analyze_failure_with_llm(record["summary"])
                record["llm_error"] = None
            except LLMConfigurationError:
                record["llm_reason"] = None
                record["llm_error"] = None
            except Exception as exc:  # noqa: BLE001 - keep rule-based analysis available
                logger.warning("LLM App Log analysis failed for %s: %s", robot_ip, exc)
                record["llm_reason"] = None
                record["llm_error"] = str(exc)
        except Exception as exc:  # noqa: BLE001 - persist failure for the UI
            logger.exception("App Log analysis failed for %s", robot_ip)
            record["status"] = "failed"
            record["error"] = str(exc)
            record["summary"] = {}

    _get_collection().insert_one(record)
    return _serialize(record)


def analyze_and_store_app_log_zip(
    zip_bytes: bytes,
    *,
    robot_ip: str,
    archive_name: str,
    device_name: str | None = None,
) -> dict[str, Any]:
    """Analyze zip bytes and always persist a Mongo record."""

    try:
        summary = analyze_app_log_zip(
            zip_bytes,
            robot_ip=robot_ip,
            archive_name=archive_name,
            device_name=device_name,
        )
        llm_reason = None
        llm_error = None
        try:
            llm_reason = analyze_failure_with_llm(summary)
        except LLMConfigurationError:
            pass
        except Exception as exc:  # noqa: BLE001 - persist the base analysis record
            logger.warning("LLM App Log analysis failed for %s: %s", robot_ip, exc)
            llm_error = str(exc)
        record = save_app_log_analysis(
            robot_ip=robot_ip,
            archive_name=archive_name,
            device_name=device_name,
            summary=summary,
        )
        if llm_reason is not None or llm_error is not None:
            collection = _get_collection()
            update = {
                "llm_reason": llm_reason,
                "llm_error": llm_error,
                "updated_at": _utc_now(),
            }
            collection.update_one({"_id": record["_id"]}, {"$set": update})
            record.update(_serialize(update))
        return record
    except Exception as exc:  # noqa: BLE001
        return save_app_log_analysis(
            robot_ip=robot_ip,
            archive_name=archive_name,
            device_name=device_name,
            error=str(exc),
        )


def list_analysis_records(
    *,
    page: int = 1,
    page_size: int = 20,
    robot_ip: str | None = None,
) -> dict[str, Any]:
    collection = _get_collection()
    query: dict[str, Any] = {}
    ip = str(robot_ip or "").strip()
    if ip:
        query["robot_ip"] = ip
    total = collection.count_documents(query)
    skip = max(0, (max(1, page) - 1) * max(1, page_size))
    cursor = (
        collection.find(query)
        .sort([("created_at", -1)])
        .skip(skip)
        .limit(max(1, min(page_size, 100)))
    )
    return {
        "records": [_serialize(item) for item in cursor],
        "total": total,
        "page": max(1, page),
        "page_size": max(1, min(page_size, 100)),
    }


def get_analysis_record(record_id: str) -> dict[str, Any]:
    record = _get_collection().find_one({"_id": str(record_id).strip()})
    if record is None:
        raise KeyError(record_id)
    return _serialize(record)
