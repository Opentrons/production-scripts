from __future__ import annotations

import os
import re
import shutil
import threading
import time
import zipfile
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime

import aiofiles
from fastapi import HTTPException, UploadFile

import settings as setting
from database.mongodb import mongodb
from upload_handler.models import FileDescription
from upload_handler.parsers.csv_common import extract_meta_data_from_csv
from upload_handler.product_catalog import (
    get_test_name_from_metadata,
    get_upload_workflow_from_config_key,
    is_combined_upload_config,
    is_upload_result_successful,
)
from upload_handler.upload import UploadData, notify_upload_result_to_slack

from api.services.logging import logger
from api.services import upload_records as upload_record_service


MANUAL_UPLOAD_SOURCE_MAX_FILES = 10
MANUAL_UPLOAD_SOURCE_MAX_ZIP_BYTES = 10 * 1024 * 1024
MANUAL_UPLOAD_SOURCE_TIMEOUT_SECONDS = 10
MANUAL_UPLOAD_EXECUTOR = ThreadPoolExecutor(max_workers=2)
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
) -> str:
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
    async with aiofiles.open(csv_path, "wb") as out_file:
        content = await csv_file.read()
        await out_file.write(content)

    for source_file in source_files or []:
        source_name = os.path.basename(source_file.filename or "")
        if not source_name or source_name == filename:
            continue
        source_path = os.path.join(upload_dir, source_name)
        async with aiofiles.open(source_path, "wb") as out_file:
            content = await source_file.read()
            await out_file.write(content)

    return csv_path


async def upload_manual_data(
    csv_file: UploadFile,
    include_source_zip: bool = False,
    all_files: bool = False,
    meta: str | dict | None = None,
    source_files: list[UploadFile] | None = None,
) -> dict:
    csv_filename = os.path.basename(csv_file.filename or "") or "unknown"
    upload_record_id = upload_record_service.create_upload_record(
        None,
        None,
        csv_name=csv_filename,
        source="manual",
    )
    csv_path = None

    try:
        meta_override = parse_manual_meta(meta)
        csv_path = await save_manual_upload_files(csv_file, source_files)
        upload_record_service.update_upload_record(
            upload_record_id,
            {
                "csv_file": upload_record_service.build_file_info(csv_path, csv_filename),
                "manual_meta": meta_override,
                "progress_stage": "saved",
                "progress_message": "已保存上传文件",
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

    MANUAL_UPLOAD_EXECUTOR.submit(
        run_upload_data_background,
        csv_path,
        zip_path,
        upload_record_id,
        meta_override,
    )

    return {
        "csv_file": csv_path,
        "zip_file": zip_path,
        "success": True,
        "record_id": upload_record_id,
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
    MANUAL_UPLOAD_EXECUTOR.shutdown(wait=False, cancel_futures=True)
    with UPLOAD_WORKFLOW_LOCKS_GUARD:
        UPLOAD_WORKFLOW_LOCKS.clear()


def build_combined_upload_lock_info(csv_path: str | None, meta: dict | None = None) -> UploadWorkflowLockInfo | None:
    if not csv_path:
        return None

    file_desc = FileDescription.build(csv_path, meta=meta)
    if not file_desc or not file_desc.is_parse_successful:
        return None

    config_key = str(file_desc.get("upload_config_key") or "")
    if not config_key or not is_combined_upload_config(config_key):
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
) -> None:
    save_upload_message(result or {}, success=False, csv_path=csv_path, error_message=error_message)
    upload_record_service.finish_upload_record(
        upload_record_id,
        upload_success=upload_success,
        database_success=database_success,
        slack_success=None,
        result=result,
        error=error_message,
    )
    slack_success = notify_upload_result_to_slack(
        result,
        csv_path or "",
        error_message=error_message,
        zip_path=zip_path,
        record_id=upload_record_id,
        upload_success=upload_success,
        database_success=database_success,
    )
    upload_record_service.finish_upload_record(
        upload_record_id,
        upload_success=upload_success,
        database_success=database_success,
        slack_success=slack_success,
        result=result,
        error=error_message,
    )


def upload_data(
    csv_path: str | None,
    zip_path: str | None = None,
    upload_record_id: str | None = None,
    meta: dict | None = None,
) -> dict:
    logger.info(f"csv_path: {csv_path}, zip_path: {zip_path}")
    if upload_record_id is None:
        upload_record_id = upload_record_service.create_upload_record(csv_path, zip_path)

    lock_info = build_combined_upload_lock_info(csv_path, meta=meta)
    if lock_info is None:
        return _upload_data_unlocked(
            csv_path=csv_path,
            zip_path=zip_path,
            upload_record_id=upload_record_id,
            meta=meta,
        )

    lock = acquire_upload_workflow_lock_ref(lock_info.key)
    try:
        locked_immediately = lock.acquire(blocking=False)
        if not locked_immediately:
            logger.info(
                "Waiting for combined upload workflow lock: key=%s config_key=%s",
                lock_info.key,
                lock_info.config_key,
            )
            upload_record_service.update_upload_record(
                upload_record_id,
                {
                    "progress_stage": "waiting_workflow_lock",
                    "progress_message": "等待同设备组合测试上传完成",
                    "workflow_lock": {
                        "key": lock_info.key,
                        "sn": lock_info.sn,
                        "model": lock_info.model,
                        "workflow": lock_info.workflow,
                        "config_key": lock_info.config_key,
                    },
                },
            )
            lock.acquire()

        try:
            logger.info(
                "Acquired combined upload workflow lock: key=%s config_key=%s",
                lock_info.key,
                lock_info.config_key,
            )
            return _upload_data_unlocked(
                csv_path=csv_path,
                zip_path=zip_path,
                upload_record_id=upload_record_id,
                meta=meta,
            )
        finally:
            lock.release()
            logger.info(
                "Released combined upload workflow lock: key=%s config_key=%s",
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
) -> dict:
    upload_state: dict = {
        "file_desc": None,
        "raw_result": None,
    }

    def update_upload_progress(event: str, payload: dict) -> None:
        if event == "file_desc":
            upload_state["file_desc"] = payload
            upload_record_service.update_upload_record(
                upload_record_id,
                {
                    "file_desc": payload,
                    "progress_stage": "file_desc",
                    "progress_message": "已解析文件描述",
                },
            )
            return

        if event == "upload_result":
            upload_state["raw_result"] = payload
            upload_success = resolve_upload_success(payload, upload_state.get("file_desc"))
            database_success = resolve_database_success(payload)
            progress_message = payload.get("error") or "Google 上传和数据库写入已返回结果"
            upload_record_service.update_upload_record(
                upload_record_id,
                {
                    "upload_result": payload,
                    "upload_success": upload_success,
                    "database_success": database_success,
                    "progress_stage": "upload_result",
                    "progress_message": progress_message,
                },
            )

    try:
        upload_record_service.update_upload_record(
            upload_record_id,
            {
                "progress_stage": "initializing",
                "progress_message": "正在初始化上传服务",
            },
        )
        upload_handler = UploadData()
        upload_handler.init_upload_handler()
        upload_record_service.update_upload_record(
            upload_record_id,
            {
                "progress_stage": "uploading",
                "progress_message": "正在上传数据到 Google Drive",
            },
        )
        result = upload_handler.update_data_to_google_drive(
            csv_path,
            zip_path,
            progress_callback=update_upload_progress,
            meta=meta,
        )
    except Exception as exc:
        logger.error(f"Upload data exception: {exc}", exc_info=True)
        finish_failed_upload(
            upload_record_id,
            csv_path=csv_path,
            zip_path=zip_path,
            upload_success=False,
            database_success=False,
            result=None,
            error_message=str(exc),
        )
        raise

    raw_result = upload_state.get("raw_result")
    upload_success = resolve_upload_success(raw_result, upload_state.get("file_desc"), result)
    database_success = resolve_database_success(raw_result, result)

    if result and result.get("finished"):
        logger.info("uploaded successfully")
        moved_zip_path = move_uploaded_zip(zip_path)
        if moved_zip_path:
            upload_record_service.update_upload_record(
                upload_record_id,
                {"zip_file": upload_record_service.build_file_info(moved_zip_path)},
            )
        save_upload_message(result, success=True, csv_path=csv_path)
        upload_record_service.update_upload_record(
            upload_record_id,
            {
                "progress_stage": "slack",
                "progress_message": "正在发送 Slack 通知",
            },
        )
        slack_success = notify_upload_result_to_slack(result, csv_path or "")
        upload_record_service.finish_upload_record(
            upload_record_id,
            upload_success=upload_success,
            database_success=database_success,
            slack_success=slack_success,
            result=result,
        )
        cleanup_upload_files(csv_path, zip_path)
        return {
            "csv_file": csv_path,
            "zip_file": moved_zip_path or zip_path,
            "success": True,
            "record_id": upload_record_id,
        }

    error_message = result.get("error") if result else "Unknown error"
    logger.error(f"Failed to upload data: {error_message}")
    finish_failed_upload(
        upload_record_id,
        csv_path=csv_path,
        zip_path=zip_path,
        upload_success=upload_success,
        database_success=database_success,
        result=result,
        error_message=error_message,
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


def run_upload_data_background(
    csv_path: str | None,
    zip_path: str | None = None,
    upload_record_id: str | None = None,
    meta: dict | None = None,
) -> None:
    try:
        upload_data(csv_path=csv_path, zip_path=zip_path, upload_record_id=upload_record_id, meta=meta)
    except HTTPException:
        return
    except Exception as exc:
        logger.error(f"Background upload task failed: {exc}", exc_info=True)
