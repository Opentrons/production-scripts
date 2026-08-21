from __future__ import annotations

import os
import hashlib
import re
import shutil
import threading
import time
import zipfile
import asyncio
import json
from dataclasses import dataclass
from datetime import datetime

import aiofiles
from fastapi import HTTPException, UploadFile

import core.config as setting
from core.database import mongodb
from modules.uploads.handler.models import FileDescription
from modules.uploads.handler.parsers.csv_common import extract_meta_data_from_csv
from modules.uploads.handler.product_catalog import (
    get_test_name_from_metadata,
    get_upload_workflow_from_config_key,
    is_combined_upload_config,
    is_upload_result_successful,
)
from modules.uploads.handler.upload import UploadData, notify_upload_result_to_slack

from core.logging import get_logger

logger = get_logger(__name__)
from modules.uploads import upload_records as upload_record_service


MANUAL_UPLOAD_SOURCE_MAX_FILES = 10
MANUAL_UPLOAD_SOURCE_MAX_ZIP_BYTES = 10 * 1024 * 1024
MANUAL_UPLOAD_SOURCE_TIMEOUT_SECONDS = 10
UPLOAD_WORKFLOW_LOCKS: dict[str, "UploadWorkflowLock"] = {}
UPLOAD_WORKFLOW_LOCKS_GUARD = threading.Lock()


@dataclass(frozen=True)
class UploadWorkflowLockInfo:
    key: str
    sn: str
    model: str
    workflow: str
    config_key: str


@dataclass
class UploadWorkflowLock:
    lock: threading.Lock
    ref_count: int = 0


class UploadRetryScheduled(RuntimeError):
    """Raised internally after a retryable upload attempt has been persisted."""


class UploadFileIntegrityError(ValueError):
    pass


def save_upload_message(result: dict, success: bool, csv_path: str | None, error_message: str | None = None) -> None:
    try:
        collection = mongodb.get_database(setting.MESSAGE_COLLECTION)[setting.DATA_UPLOAD_STATUS_COLLECTION]
        if success:
            message_doc = {
                "title": "Upload Successful",
                "new": True,
                "content": (
                    f"Production: {result.get('production_name') or 'Unknown Production'} \n "
                    f"Test Type: {result.get('test_type') or 'Unknown Test Type'} \n "
                    f"Test Result:{result.get('test_result') or 'Unknown Test Result'} \n "
                    f"Unit Tracker:{result.get('unit_tracker') or 'Unknown Unit Tracker'} \n "
                    f"Unit Tracker Status:{result.get('unit_tracker_status') or 'Unknown Unit Tracker Status'}  \n "
                    f"CSV Link:{result.get('csv_link') or 'Unknown CSV Link'} \n "
                    f"Test Data Link:{result.get('test_data_link') or 'Unknown Test Data Link'}"
                ),
                "created_at": datetime.now(),
            }
        else:
            message_doc = {
                "title": "Upload Failed",
                "new": True,
                "content": f"CSV Path:{csv_path} \n Error:{error_message}",
                "created_at": datetime.now(),
            }
        collection.insert_one(message_doc)
        logger.info(f"Message saved to database: {message_doc.get('title')}")
    except Exception as exc:
        logger.error(f"Failed to save upload message to database: {exc}")


def move_uploaded_zip(zip_path: str | None) -> str | None:
    if not zip_path or not os.path.exists(zip_path):
        return None
    try:
        os.makedirs(setting.TESTING_DATA_DIR, exist_ok=True)
        zip_filename = os.path.basename(zip_path)
        moved_zip_path = os.path.join(setting.TESTING_DATA_DIR, zip_filename)
        shutil.move(zip_path, moved_zip_path)
        logger.info(f"Moved zip file to: {moved_zip_path}")
        return moved_zip_path
    except Exception as exc:
        logger.error(f"Failed to move zip file: {exc}")
        return None


def cleanup_upload_files(csv_path: str | None, zip_path: str | None) -> None:
    try:
        if csv_path and os.path.exists(csv_path):
            os.remove(csv_path)
            logger.info(f"Removed csv file: {csv_path}")
        if zip_path and os.path.exists(zip_path):
            os.remove(zip_path)
            logger.info(f"Removed zip file: {zip_path}")
    except Exception as exc:
        logger.error(f"Failed to clean temp files: {exc}")


def raise_manual_zip_error(message: str) -> None:
    raise HTTPException(
        status_code=400,
        detail={
            "message": message,
            "success": False,
        },
    )


def cleanup_partial_zip(zip_path: str) -> None:
    try:
        if os.path.exists(zip_path):
            os.remove(zip_path)
    except OSError as exc:
        logger.warning(f"Failed to remove partial zip file {zip_path}: {exc}")


def list_source_files(
    source_dir: str,
    zip_path: str,
    csv_path: str,
    *,
    all_files: bool = False,
) -> list[str]:
    if not all_files:
        return [csv_path] if os.path.isfile(csv_path) else []

    source_files = []
    for root, _, files in os.walk(source_dir):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            if os.path.abspath(file_path) == os.path.abspath(zip_path):
                continue
            source_files.append(file_path)
            if len(source_files) > MANUAL_UPLOAD_SOURCE_MAX_FILES:
                raise_manual_zip_error("源文件目录文件数量超过 10 个，已停止上传")
    return source_files


def zip_upload_source_folder(csv_path: str, *, all_files: bool = False) -> str | None:
    source_dir = os.path.dirname(csv_path)
    if not source_dir:
        return None

    zip_path = build_manual_zip_path(csv_path, source_dir)
    started_at = time.monotonic()
    try:
        source_files = list_source_files(source_dir, zip_path, csv_path, all_files=all_files)
        if not source_files:
            return None

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file_path in source_files:
                if all_files and time.monotonic() - started_at > MANUAL_UPLOAD_SOURCE_TIMEOUT_SECONDS:
                    raise_manual_zip_error("源文件目录打包超过 10 秒，已停止上传")

                if all_files:
                    arcname = os.path.relpath(file_path, os.path.dirname(source_dir))
                else:
                    arcname = os.path.basename(file_path)
                zipf.write(file_path, arcname)

                if (
                    all_files
                    and os.path.exists(zip_path)
                    and os.path.getsize(zip_path) > MANUAL_UPLOAD_SOURCE_MAX_ZIP_BYTES
                ):
                    raise_manual_zip_error("源文件目录打包后超过 10MB，已停止上传")
        return zip_path
    except HTTPException:
        cleanup_partial_zip(zip_path)
        raise
    except Exception as exc:
        cleanup_partial_zip(zip_path)
        logger.error(f"Failed to zip upload source folder: {exc}")
        return None


def build_manual_zip_path(csv_path: str, source_dir: str) -> str:
    test_name = resolve_manual_upload_test_name(csv_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(os.path.dirname(source_dir), f"{test_name}-{timestamp}.zip")


def resolve_manual_upload_test_name(csv_path: str) -> str:
    try:
        metadata = extract_meta_data_from_csv(csv_path)
        test_name = get_test_name_from_metadata(metadata)
    except Exception as exc:
        logger.warning(f"Failed to read test name for manual zip: {exc}")
        test_name = ""

    fallback_name = os.path.splitext(os.path.basename(csv_path))[0]
    return sanitize_zip_name(test_name or fallback_name or "manual-upload")


def sanitize_zip_name(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value).strip())
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-._")
    return normalized or "manual-upload"


async def save_manual_upload_files(
    csv_file: UploadFile,
    source_files: list[UploadFile] | None = None,
) -> tuple[str, dict[str, int | str]]:
    filename = os.path.basename(csv_file.filename or "")
    if not filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Only CSV files are allowed",
                "success": False,
            },
        )

    upload_dir = os.path.join(
        setting.DOWNLOAD_DIR,
        "manual_uploads",
        datetime.now().strftime("%Y%m%d_%H%M%S_%f"),
    )
    os.makedirs(upload_dir, exist_ok=True)
    csv_path = os.path.join(upload_dir, filename)
    csv_sha256 = hashlib.sha256()
    csv_size = 0
    async with aiofiles.open(csv_path, "wb") as out_file:
        while content := await csv_file.read(1024 * 1024):
            csv_size += len(content)
            csv_sha256.update(content)
            await out_file.write(content)

    for source_file in source_files or []:
        source_name = os.path.basename(source_file.filename or "")
        if not source_name or source_name == filename:
            continue
        source_path = os.path.join(upload_dir, source_name)
        async with aiofiles.open(source_path, "wb") as out_file:
            while content := await source_file.read(1024 * 1024):
                await out_file.write(content)

    return csv_path, {"size": csv_size, "sha256": csv_sha256.hexdigest()}


async def upload_manual_data(
    csv_file: UploadFile,
    include_source_zip: bool = False,
    all_files: bool = False,
    meta: str | dict | None = None,
    source_files: list[UploadFile] | None = None,
    upload_record_id: str | None = None,
) -> dict:
    csv_filename = os.path.basename(csv_file.filename or "") or "unknown"
    if upload_record_id is None:
        upload_record_id = upload_record_service.create_upload_record(
            None,
            None,
            csv_name=csv_filename,
            source="manual",
        )
    else:
        existing_record = upload_record_service.get_upload_record(upload_record_id) or {}
        if existing_record.get("status") == "success" or (
            existing_record.get("job")
            and existing_record.get("status") in upload_record_service.ACTIVE_UPLOAD_STATUSES
        ):
            return {
                "success": True,
                "record_id": upload_record_id,
                "status": existing_record.get("status"),
                "deduplicated": True,
                "message": "Upload task already exists",
            }
        upload_record_service.update_upload_record(
            upload_record_id,
            {
                "source": "manual",
                "csv_file": upload_record_service.build_file_info(None, csv_filename),
            },
        )
    csv_path = None
    integrity: dict[str, int | str] = {}

    try:
        meta_override = parse_manual_meta(meta)
    except HTTPException as exc:
        error_message = get_http_exception_message(exc)
        finish_failed_upload(
            upload_record_id,
            csv_path=csv_filename,
            upload_success=False,
            database_success=False,
            result=None,
            error_message=error_message,
            failure_stage="request_validation",
            failure_code="invalid_manual_metadata",
        )
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "message": error_message,
                "success": False,
                "record_id": upload_record_id,
            },
        )

    try:
        csv_path, integrity = await save_manual_upload_files(csv_file, source_files)
        expected_file = (upload_record_service.get_upload_record(upload_record_id) or {}).get("csv_file") or {}
        expected_size = expected_file.get("expected_size")
        expected_sha256 = str(expected_file.get("expected_sha256") or "").lower()
        if expected_size is not None and int(expected_size) != int(integrity["size"]):
            raise UploadFileIntegrityError(
                f"CSV 文件大小校验失败: expected={expected_size}, actual={integrity['size']}"
            )
        if expected_sha256 and expected_sha256 != integrity["sha256"]:
            raise UploadFileIntegrityError(
                f"CSV SHA-256 校验失败: expected={expected_sha256}, actual={integrity['sha256']}"
            )
        upload_record_service.update_upload_record(
            upload_record_id,
            {
                "csv_file": {
                    **(upload_record_service.build_file_info(csv_path, csv_filename) or {}),
                    **integrity,
                },
                "manual_meta": meta_override,
                "progress_stage": "saved",
                "progress_message": "已保存上传文件",
            },
        )
    except UploadFileIntegrityError as exc:
        error_message = str(exc)
        finish_failed_upload(
            upload_record_id,
            csv_path=csv_path or csv_filename,
            upload_success=False,
            database_success=False,
            result=None,
            error_message=error_message,
            failure_stage="file_integrity",
            failure_code="csv_integrity_check_failed",
        )
        cleanup_upload_files(csv_path, None)
        raise HTTPException(
            status_code=422,
            detail={
                "message": error_message,
                "success": False,
                "record_id": upload_record_id,
            },
        )
    except HTTPException as exc:
        error_message = get_http_exception_message(exc)
        finish_failed_upload(
            upload_record_id,
            csv_path=csv_path or csv_filename,
            upload_success=False,
            database_success=False,
            result=None,
            error_message=error_message,
            failure_stage="save_files",
            failure_code="save_upload_files_failed",
        )
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "message": error_message,
                "success": False,
                "record_id": upload_record_id,
            },
        )
    except Exception as exc:
        error_message = f"保存上传文件失败: {exc}"
        finish_failed_upload(
            upload_record_id,
            csv_path=csv_path or csv_filename,
            upload_success=False,
            database_success=False,
            result=None,
            error_message=error_message,
            failure_stage="save_files",
            failure_code="save_upload_files_failed",
        )
        raise HTTPException(
            status_code=500,
            detail={
                "message": error_message,
                "success": False,
                "record_id": upload_record_id,
            },
        )

    try:
        zip_path = (
            await asyncio.to_thread(zip_upload_source_folder, csv_path, all_files=all_files)
            if include_source_zip
            else None
        )
    except HTTPException as exc:
        error_message = get_http_exception_message(exc)
        finish_failed_upload(
            upload_record_id,
            csv_path=csv_path,
            zip_path=None,
            upload_success=False,
            database_success=False,
            result=None,
            error_message=error_message,
            failure_stage="package_source",
            failure_code="source_package_failed",
        )
        cleanup_upload_files(csv_path, None)
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "message": error_message,
                "csv_file": csv_path,
                "success": False,
                "record_id": upload_record_id,
            },
        )

    if include_source_zip and not zip_path:
        error_message = "Failed to package source folder"
        finish_failed_upload(
            upload_record_id,
            csv_path=csv_path,
            zip_path=None,
            upload_success=False,
            database_success=False,
            result=None,
            error_message=error_message,
            failure_stage="package_source",
            failure_code="source_package_failed",
        )
        cleanup_upload_files(csv_path, None)
        raise HTTPException(
            status_code=500,
            detail={
                "message": error_message,
                "csv_file": csv_path,
                "success": False,
                "record_id": upload_record_id,
            },
        )

    if zip_path:
        upload_record_service.update_upload_record(
            upload_record_id,
            {"zip_file": upload_record_service.build_file_info(zip_path)},
        )

    queued = upload_record_service.enqueue_upload_record(
        upload_record_id,
        csv_path=csv_path,
        zip_path=zip_path,
        meta=meta_override,
    )
    if not queued:
        error_message = "Failed to enqueue durable upload task"
        finish_failed_upload(
            upload_record_id,
            csv_path=csv_path,
            zip_path=zip_path,
            upload_success=False,
            database_success=False,
            result=None,
            error_message=error_message,
            failure_stage="queue",
            failure_code="upload_enqueue_failed",
        )
        raise HTTPException(
            status_code=503,
            detail={
                "message": error_message,
                "success": False,
                "record_id": upload_record_id,
            },
        )

    return {
        "csv_file": csv_path,
        "zip_file": zip_path,
        "success": True,
        "record_id": upload_record_id,
        "status": "queued",
        "message": "Upload task submitted",
    }


def parse_manual_meta(meta: str | dict | None) -> dict:
    if meta in (None, ""):
        return {}
    if isinstance(meta, dict):
        parsed = meta
    else:
        try:
            parsed = json.loads(meta)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "meta 必须是 JSON object",
                    "success": False,
                },
            ) from exc

    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=400,
            detail={
                "message": "meta 必须是 JSON object",
                "success": False,
            },
        )

    return {
        str(key): value
        for key, value in parsed.items()
        if key is not None and value not in (None, "")
    }


def get_http_exception_message(exc: HTTPException) -> str:
    detail = exc.detail
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("error") or "Upload request failed")
    return str(detail or "Upload request failed")


def resolve_upload_success(raw_result: dict | None, file_desc: dict | None, api_result: dict | None = None) -> bool:
    if not raw_result:
        return bool(api_result and api_result.get("finished"))
    if raw_result.get("error"):
        return False

    config_key = str(raw_result.get("upload_config_key") or (file_desc or {}).get("upload_config_key") or "")
    if not config_key:
        return bool(raw_result.get("csv_link"))

    try:
        return is_upload_result_successful(config_key, raw_result)
    except Exception as exc:
        logger.warning(f"Failed to resolve upload success from raw result: {exc}")
        return bool(raw_result.get("csv_link"))


def resolve_database_success(raw_result: dict | None, api_result: dict | None = None) -> bool:
    if raw_result and "database_saved" in raw_result:
        return raw_result.get("database_saved") is True
    return bool(api_result and api_result.get("finished"))


def infer_upload_failure_stage(
    raw_result: dict | None,
    api_result: dict | None,
    current_stage: str = "upload",
) -> tuple[str, str]:
    """Resolve a stable failure stage/code from the worker result.

    The raw uploader result is intentionally retained in the record; these
    fields make common failures filterable without parsing localized text.
    """
    result = raw_result or api_result or {}
    if result.get("database_saved") is False:
        return "database", "database_write_failed"
    if result.get("missing_tests"):
        return "workflow", "combined_workflow_incomplete"

    precise_stages = {
        "initializing",
        "initialize_google",
        "prepare_spreadsheet",
        "write_spreadsheet",
        "read_summary",
        "move_spreadsheet",
        "upload_raw_data",
        "unit_tracker",
    }
    if current_stage in precise_stages:
        return current_stage, f"{current_stage}_failed"

    error = str(result.get("error") or "").lower()
    if any(keyword in error for keyword in ("parse", "parser", "file description", "csv", "解析")):
        return "parse_csv", "csv_parse_failed"
    if any(keyword in error for keyword in ("unsupported", "test_type", "model", "配置")):
        return "resolve_config", "upload_config_not_supported"
    if any(keyword in error for keyword in ("google", "drive", "sheet", "spreadsheet", "oauth", "token")):
        return "google_drive", "google_upload_failed"
    if current_stage in {
        "parse_csv",
        "resolve_config",
        "google_drive",
        "database",
        "workflow",
    }:
        return current_stage, f"{current_stage}_failed"
    return "upload", "upload_failed"


def is_retryable_upload_failure(
    failure_stage: str,
    failure_code: str,
    error: str | None,
) -> bool:
    normalized_error = str(error or "").lower()
    permanent_markers = (
        "permission denied",
        "insufficient permission",
        "invalid_grant",
        "unauthorized",
        "unsupported",
        "not supported",
        "file description",
        "csv sha-256",
        "文件大小校验失败",
        "配置不存在",
        "不支持",
    )
    if any(marker in normalized_error for marker in permanent_markers):
        return False
    if failure_stage in {
        "request_validation",
        "file_integrity",
        "parse_csv",
        "resolve_config",
        "workflow",
        "package_source",
        "save_files",
    }:
        return False
    if failure_code in {"http_408", "http_429", "http_502", "http_503", "http_504"}:
        return True
    return failure_stage in {
        "initializing",
        "initialize_google",
        "google_drive",
        "prepare_spreadsheet",
        "write_spreadsheet",
        "read_summary",
        "move_spreadsheet",
        "upload_raw_data",
        "database",
        "unit_tracker",
        "request_transport",
        "request_processing",
        "worker_interrupted",
        "upload",
    }


def acquire_upload_workflow_lock_ref(lock_key: str) -> threading.Lock:
    with UPLOAD_WORKFLOW_LOCKS_GUARD:
        lock_state = UPLOAD_WORKFLOW_LOCKS.get(lock_key)
        if lock_state is None:
            lock_state = UploadWorkflowLock(lock=threading.Lock())
            UPLOAD_WORKFLOW_LOCKS[lock_key] = lock_state
        lock_state.ref_count += 1
        return lock_state.lock


def release_upload_workflow_lock_ref(lock_key: str) -> None:
    with UPLOAD_WORKFLOW_LOCKS_GUARD:
        lock_state = UPLOAD_WORKFLOW_LOCKS.get(lock_key)
        if lock_state is None:
            return
        lock_state.ref_count = max(0, lock_state.ref_count - 1)
        if lock_state.ref_count == 0 and not lock_state.lock.locked():
            UPLOAD_WORKFLOW_LOCKS.pop(lock_key, None)


def shutdown_upload_service() -> None:
    with UPLOAD_WORKFLOW_LOCKS_GUARD:
        UPLOAD_WORKFLOW_LOCKS.clear()


def build_upload_workflow_lock_info(csv_path: str | None, meta: dict | None = None) -> UploadWorkflowLockInfo | None:
    if not csv_path:
        return None

    file_desc = FileDescription.build(csv_path, meta=meta)
    if not file_desc or not file_desc.is_parse_successful:
        return None

    config_key = str(file_desc.get("upload_config_key") or "")
    if not config_key:
        return None

    sn = str(file_desc.get("sn") or "")
    model = str(file_desc.get("model") or "")
    if not sn or not model or model == "NA":
        return None

    workflow = get_upload_workflow_from_config_key(config_key)
    return UploadWorkflowLockInfo(
        key=f"{sn}:{model}:{workflow}",
        sn=sn,
        model=model,
        workflow=workflow,
        config_key=config_key,
    )


def finish_failed_upload(
    upload_record_id: str | None,
    *,
    csv_path: str | None,
    zip_path: str | None = None,
    upload_success: bool,
    database_success: bool,
    result: dict | None,
    error_message: str,
    failure_stage: str = "upload",
    failure_code: str = "upload_failed",
    error_detail: str | None = None,
    expected_attempt: int | None = None,
) -> bool:
    finished = upload_record_service.finish_upload_record(
        upload_record_id,
        upload_success=upload_success,
        database_success=database_success,
        slack_success=None,
        result=result,
        error=error_message,
        failure_stage=failure_stage,
        failure_code=failure_code,
        error_detail=error_detail,
        expected_attempt=expected_attempt,
    )
    if not finished:
        return False
    save_upload_message(result or {}, success=False, csv_path=csv_path, error_message=error_message)
    upload_record_service.queue_upload_notification(
        upload_record_id,
        result=result,
        csv_path=csv_path or "",
        zip_path=zip_path,
        error_message=error_message,
        upload_success=upload_success,
        database_success=database_success,
    )
    return True


def upload_data(
    csv_path: str | None,
    zip_path: str | None = None,
    upload_record_id: str | None = None,
    meta: dict | None = None,
    retry_managed: bool = False,
    expected_attempt: int | None = None,
) -> dict:
    logger.info(f"csv_path: {csv_path}, zip_path: {zip_path}")
    if upload_record_id is None:
        upload_record_id = upload_record_service.create_upload_record(csv_path, zip_path)
    if expected_attempt is not None:
        current_record = upload_record_service.get_upload_record(upload_record_id) or {}
        if (
            current_record.get("status") != "running"
            or int(current_record.get("attempt_count") or 0) != int(expected_attempt)
        ):
            return {
                "success": False,
                "record_id": upload_record_id,
                "message": "Upload attempt lease is no longer current",
            }

    lock_info = build_upload_workflow_lock_info(csv_path, meta=meta)
    if lock_info is None:
        return _upload_data_unlocked(
            csv_path=csv_path,
            zip_path=zip_path,
            upload_record_id=upload_record_id,
            meta=meta,
            retry_managed=retry_managed,
            expected_attempt=expected_attempt,
        )

    lock = acquire_upload_workflow_lock_ref(lock_info.key)
    try:
        locked_immediately = lock.acquire(blocking=False)
        if not locked_immediately:
            logger.info(
                "Waiting for upload workflow lock: key=%s config_key=%s",
                lock_info.key,
                lock_info.config_key,
            )
            upload_record_service.update_upload_attempt(
                upload_record_id,
                expected_attempt,
                {
                    "workflow_lock": {
                        "key": lock_info.key,
                        "sn": lock_info.sn,
                        "model": lock_info.model,
                        "workflow": lock_info.workflow,
                        "config_key": lock_info.config_key,
                    },
                },
            )
            upload_record_service.record_upload_progress(
                upload_record_id,
                "waiting_workflow_lock",
                "等待同设备同工作流上传完成",
                expected_attempt=expected_attempt,
            )
            while not lock.acquire(timeout=min(30, max(1, setting.UPLOAD_LEASE_SECONDS // 3))):
                upload_record_service.record_upload_progress(
                    upload_record_id,
                    "waiting_workflow_lock",
                    "等待同设备同工作流上传完成",
                    expected_attempt=expected_attempt,
                )

        try:
            logger.info(
                "Acquired upload workflow lock: key=%s config_key=%s",
                lock_info.key,
                lock_info.config_key,
            )
            if expected_attempt is not None:
                current_record = upload_record_service.get_upload_record(upload_record_id) or {}
                if (
                    current_record.get("status") != "running"
                    or int(current_record.get("attempt_count") or 0) != int(expected_attempt)
                ):
                    logger.warning(
                        "Skipping stale upload attempt: record=%s attempt=%s",
                        upload_record_id,
                        expected_attempt,
                    )
                    return {
                        "success": False,
                        "record_id": upload_record_id,
                        "message": "Upload attempt lease is no longer current",
                    }
            return _upload_data_unlocked(
                csv_path=csv_path,
                zip_path=zip_path,
                upload_record_id=upload_record_id,
                meta=meta,
                retry_managed=retry_managed,
                expected_attempt=expected_attempt,
            )
        finally:
            lock.release()
            logger.info(
                "Released upload workflow lock: key=%s config_key=%s",
                lock_info.key,
                lock_info.config_key,
            )
    finally:
        release_upload_workflow_lock_ref(lock_info.key)


def _upload_data_unlocked(
    csv_path: str | None,
    zip_path: str | None = None,
    upload_record_id: str | None = None,
    meta: dict | None = None,
    retry_managed: bool = False,
    expected_attempt: int | None = None,
) -> dict:
    upload_state: dict = {
        "file_desc": None,
        "raw_result": None,
    }
    current_stage = "initializing"

    def update_upload_progress(event: str, payload: dict) -> None:
        nonlocal current_stage
        if event == "stage":
            current_stage = str(payload.get("stage") or current_stage)
            upload_record_service.record_upload_progress(
                upload_record_id,
                current_stage,
                payload.get("message") or current_stage,
                checkpoint=payload.get("checkpoint"),
                expected_attempt=expected_attempt,
            )
            return

        if event == "file_desc":
            current_stage = "parse_csv"
            upload_state["file_desc"] = payload
            upload_record_service.update_upload_attempt(
                upload_record_id,
                expected_attempt,
                {
                    "file_desc": payload,
                    "progress_stage": "file_desc",
                    "progress_message": "已解析文件描述",
                },
            )
            upload_record_service.record_upload_progress(
                upload_record_id,
                "file_desc",
                "已解析文件描述",
                expected_attempt=expected_attempt,
            )
            return

        if event == "upload_result":
            upload_state["raw_result"] = payload
            upload_success = resolve_upload_success(payload, upload_state.get("file_desc"))
            database_success = resolve_database_success(payload)
            current_stage, _ = infer_upload_failure_stage(payload, None, current_stage)
            progress_message = payload.get("error") or "Google 上传和数据库写入已返回结果"
            upload_record_service.update_upload_attempt(
                upload_record_id,
                expected_attempt,
                {
                    "upload_result": payload,
                    "upload_success": upload_success,
                    "database_success": database_success,
                    "progress_stage": "upload_result",
                    "progress_message": progress_message,
                    "failure_stage": None if upload_success and database_success else current_stage,
                },
            )
            upload_record_service.record_upload_progress(
                upload_record_id,
                "upload_result",
                progress_message,
                expected_attempt=expected_attempt,
            )

    try:
        upload_record_service.record_upload_progress(
            upload_record_id,
            "initializing",
            "正在初始化上传服务",
            expected_attempt=expected_attempt,
        )
        upload_handler = UploadData()
        upload_handler.init_upload_handler()
        upload_record_service.record_upload_progress(
            upload_record_id,
            "uploading",
            "正在上传数据到 Google Drive",
            expected_attempt=expected_attempt,
        )
        record = upload_record_service.get_upload_record(upload_record_id) or {}
        result = upload_handler.update_data_to_google_drive(
            csv_path,
            zip_path,
            progress_callback=update_upload_progress,
            meta=meta,
            upload_record_id=upload_record_id,
            resume_checkpoint=record.get("checkpoint") or {},
        )
    except Exception as exc:
        logger.error(f"Upload data exception: {exc}", exc_info=True)
        failure_code = f"{current_stage}_exception"
        if (
            retry_managed
            and is_retryable_upload_failure(current_stage, failure_code, str(exc))
            and upload_record_service.schedule_upload_retry(
                upload_record_id,
                failure_stage=current_stage,
                failure_code=failure_code,
                error=str(exc),
                error_detail=str(exc),
                expected_attempt=expected_attempt,
            )
        ):
            raise UploadRetryScheduled(str(exc)) from exc
        finish_failed_upload(
            upload_record_id,
            csv_path=csv_path,
            zip_path=zip_path,
            upload_success=False,
            database_success=False,
            result=None,
            error_message=str(exc),
            failure_stage=current_stage,
            failure_code=failure_code,
            error_detail=str(exc),
            expected_attempt=expected_attempt,
        )
        raise

    raw_result = upload_state.get("raw_result")
    upload_success = resolve_upload_success(raw_result, upload_state.get("file_desc"), result)
    database_success = resolve_database_success(raw_result, result)

    if result and result.get("finished"):
        logger.info("uploaded successfully")
        finished = upload_record_service.finish_upload_record(
            upload_record_id,
            upload_success=upload_success,
            database_success=database_success,
            slack_success=None,
            result=result,
            expected_attempt=expected_attempt,
        )
        if not finished:
            logger.warning(
                "Ignoring stale success for upload %s attempt %s",
                upload_record_id,
                expected_attempt,
            )
            return {
                "csv_file": csv_path,
                "zip_file": zip_path,
                "success": False,
                "record_id": upload_record_id,
                "message": "Upload attempt lease is no longer current",
            }
        moved_zip_path = move_uploaded_zip(zip_path)
        if moved_zip_path:
            upload_record_service.update_upload_record(
                upload_record_id,
                {"zip_file": upload_record_service.build_file_info(moved_zip_path)},
            )
        save_upload_message(result, success=True, csv_path=csv_path)
        upload_record_service.queue_upload_notification(
            upload_record_id,
            result=result,
            csv_path=csv_path or "",
            zip_path=moved_zip_path or zip_path,
            error_message=None,
            upload_success=upload_success,
            database_success=database_success,
        )
        cleanup_upload_files(csv_path, zip_path)
        return {
            "csv_file": csv_path,
            "zip_file": moved_zip_path or zip_path,
            "success": True,
            "record_id": upload_record_id,
        }

    error_message = result.get("error") if result else "Unknown error"
    failure_stage, failure_code = infer_upload_failure_stage(raw_result, result, current_stage)
    logger.error(f"Failed to upload data: {error_message}")
    if (
        retry_managed
        and is_retryable_upload_failure(failure_stage, failure_code, error_message)
        and upload_record_service.schedule_upload_retry(
            upload_record_id,
            failure_stage=failure_stage,
            failure_code=failure_code,
            error=error_message,
            error_detail=error_message,
            expected_attempt=expected_attempt,
        )
    ):
        raise UploadRetryScheduled(error_message)
    finish_failed_upload(
        upload_record_id,
        csv_path=csv_path,
        zip_path=zip_path,
        upload_success=upload_success,
        database_success=database_success,
        result=result,
        error_message=error_message,
        failure_stage=failure_stage,
        failure_code=failure_code,
        error_detail=error_message,
        expected_attempt=expected_attempt,
    )
    raise HTTPException(
        status_code=500,
        detail={
            "message": "Failed to upload data",
            "error": error_message,
            "csv_file": csv_path,
            "zip_file": zip_path,
            "success": False,
            "record_id": upload_record_id,
        },
    )


def compute_file_sha256(path: str) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as handle:
        while chunk := handle.read(1024 * 1024):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def run_queued_upload(record: dict) -> None:
    record_id = str(record["_id"])
    job = record.get("job") or {}
    csv_path = str(job.get("csv_path") or "")
    zip_path = job.get("zip_path") or None
    meta = job.get("meta") or {}
    expected_attempt = int(record.get("attempt_count") or 0)
    heartbeat_stop = threading.Event()

    def heartbeat() -> None:
        interval = min(60, max(10, setting.UPLOAD_LEASE_SECONDS // 3))
        while not heartbeat_stop.wait(interval):
            if not upload_record_service.renew_upload_attempt_lease(record_id, expected_attempt):
                return

    heartbeat_thread = threading.Thread(
        target=heartbeat,
        name=f"upload-heartbeat-{record_id[:8]}",
        daemon=True,
    )
    heartbeat_thread.start()

    try:
        if not csv_path or not os.path.isfile(csv_path):
            raise UploadFileIntegrityError(f"Queued CSV file is missing: {csv_path or '<empty>'}")
        csv_info = record.get("csv_file") or {}
        expected_size = csv_info.get("size")
        expected_sha256 = str(csv_info.get("sha256") or "").lower()
        if expected_size is not None or expected_sha256:
            actual_size, actual_sha256 = compute_file_sha256(csv_path)
            if expected_size is not None and int(expected_size) != actual_size:
                raise UploadFileIntegrityError(
                    f"Queued CSV size changed: expected={expected_size}, actual={actual_size}"
                )
            if expected_sha256 and expected_sha256 != actual_sha256:
                raise UploadFileIntegrityError(
                    f"Queued CSV SHA-256 changed: expected={expected_sha256}, actual={actual_sha256}"
                )

        upload_data(
            csv_path=csv_path,
            zip_path=zip_path,
            upload_record_id=record_id,
            meta=meta,
            retry_managed=True,
            expected_attempt=expected_attempt,
        )
    except UploadRetryScheduled as exc:
        logger.warning("Upload %s scheduled for retry: %s", record_id, exc)
    except UploadFileIntegrityError as exc:
        finish_failed_upload(
            record_id,
            csv_path=csv_path,
            zip_path=zip_path,
            upload_success=False,
            database_success=False,
            result=None,
            error_message=str(exc),
            failure_stage="file_integrity",
            failure_code="queued_file_integrity_failed",
            error_detail=str(exc),
            expected_attempt=expected_attempt,
        )
    except HTTPException:
        return
    except Exception as exc:
        logger.error("Queued upload %s failed unexpectedly: %s", record_id, exc, exc_info=True)
        refreshed = upload_record_service.get_upload_record(record_id) or {}
        if refreshed.get("status") not in upload_record_service.ACTIVE_UPLOAD_STATUSES:
            return
        if upload_record_service.schedule_upload_retry(
            record_id,
            failure_stage="request_processing",
            failure_code="background_task_failed",
            error=str(exc),
            error_detail=str(exc),
            expected_attempt=expected_attempt,
        ):
            return
        finish_failed_upload(
            record_id,
            csv_path=csv_path,
            zip_path=zip_path,
            upload_success=False,
            database_success=False,
            result=None,
            error_message=str(exc),
            failure_stage="request_processing",
            failure_code="background_task_failed",
            error_detail=str(exc),
            expected_attempt=expected_attempt,
        )
    finally:
        heartbeat_stop.set()
        heartbeat_thread.join(timeout=1)
