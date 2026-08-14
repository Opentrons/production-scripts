from __future__ import annotations

import asyncio
import platform
import subprocess
import threading
import time
from datetime import datetime, timezone
from typing import Any

import core.config as setting
from core.persistence import get_document_collection
from core.slack.message import SlackBotMessenger
from modules.uploads.handler.utils import google_drive_health_check

from core.logging import get_logger

logger = get_logger(__name__)

_CACHE_ID = "latest"
_refresh_state_lock = threading.Lock()
_refresh_complete: threading.Event | None = None
_scheduler_task: asyncio.Task[None] | None = None


def with_elapsed(status: dict, started_at: float) -> dict:
    status["elapsed_ms"] = round((time.perf_counter() - started_at) * 1000, 2)
    return status


def check_systemctl_service(service_name: str) -> dict:
    started_at = time.perf_counter()
    if setting.IS_DEV_ENV:
        return with_elapsed(
            {
                "status": "running",
                "message": f"Backend process is running in {setting.RUN_ENV} environment",
            },
            started_at,
        )

    system = platform.system()
    if system != "Linux":
        return with_elapsed(
            {
                "status": "unknown",
                "message": f"Platform {system} does not support systemctl",
            },
            started_at,
        )

    try:
        result = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        service_state = result.stdout.strip()
        if service_state == "active":
            return with_elapsed(
                {"status": "running", "message": f"Service {service_name} is running"},
                started_at,
            )
        if service_state == "inactive":
            return with_elapsed(
                {"status": "stopped", "message": f"Service {service_name} is stopped"},
                started_at,
            )
        if service_state == "failed":
            return with_elapsed(
                {"status": "failed", "message": f"Service {service_name} has failed"},
                started_at,
            )
        return with_elapsed(
            {"status": "unknown", "message": f"Service state: {service_state}"},
            started_at,
        )
    except subprocess.TimeoutExpired:
        return with_elapsed(
            {"status": "unknown", "message": "systemctl command timed out"},
            started_at,
        )
    except FileNotFoundError:
        return with_elapsed(
            {"status": "unknown", "message": "systemctl command not found"},
            started_at,
        )
    except Exception as exc:
        return with_elapsed(
            {"status": "unknown", "message": f"Failed to check service: {str(exc)}"},
            started_at,
        )


def check_slack_health() -> tuple[bool, dict]:
    started_at = time.perf_counter()
    try:
        bot = SlackBotMessenger(timeout=5)
        if bot.client:
            bot.client.auth_test()
            logger.info("Slack health check passed")
            return True, with_elapsed(
                {"status": "healthy", "message": "Slack connection OK"},
                started_at,
            )
        logger.warning("Slack health check failed: no client")
        return False, with_elapsed(
            {"status": "unhealthy", "message": "Slack client not initialized (no token)"},
            started_at,
        )
    except Exception as exc:
        logger.error(f"Slack health check failed: {exc}")
        return False, with_elapsed(
            {"status": "unhealthy", "message": "Slack connection failed"},
            started_at,
        )


def check_google_drive_health() -> tuple[bool, dict]:
    started_at = time.perf_counter()
    try:
        google_ok = google_drive_health_check()
        if google_ok:
            logger.info("Google Drive health check passed")
            return True, with_elapsed(
                {"status": "healthy", "message": "Google Drive connection OK"},
                started_at,
            )
        logger.warning("Google Drive health check failed")
        return False, with_elapsed(
            {"status": "unhealthy", "message": "Google Drive connection failed"},
            started_at,
        )
    except Exception as exc:
        logger.error(f"Google Drive health check failed: {exc}")
        return False, with_elapsed(
            {"status": "unhealthy", "message": "Google Drive connection failed"},
            started_at,
        )


def _health_collection():
    return get_document_collection(setting.SYSTEM_HEALTH_COLLECTION)


def _empty_health_status() -> dict[str, Any]:
    missing = {"status": "unknown", "message": "No cached health status"}
    return {
        "status": False,
        "elapsed_ms": None,
        "checked_at": None,
        "services": {
            "system_service": dict(missing),
            "slack": dict(missing),
            "google_drive": dict(missing),
        },
    }


def get_cached_health_status() -> dict[str, Any]:
    document = _health_collection().find_one({"_id": _CACHE_ID})
    if not isinstance(document, dict):
        return _empty_health_status()
    services = document.get("services")
    if not isinstance(services, dict):
        return _empty_health_status()
    return {
        "status": bool(document.get("status")),
        "elapsed_ms": document.get("elapsed_ms"),
        "checked_at": document.get("checked_at"),
        "services": services,
    }


def _probe_health_status() -> dict[str, Any]:
    started_at = time.perf_counter()
    service_check = check_systemctl_service("production-backend")
    slack_ok, slack_status = check_slack_health()
    google_ok, google_status = check_google_drive_health()
    service_ok = service_check.get("status") == "running"
    return {
        "status": service_ok and slack_ok and google_ok,
        "elapsed_ms": round((time.perf_counter() - started_at) * 1000, 2),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "services": {
            "system_service": service_check,
            "slack": slack_status,
            "google_drive": google_status,
        },
    }


def refresh_health_status() -> dict[str, Any]:
    global _refresh_complete
    with _refresh_state_lock:
        if _refresh_complete is not None:
            completion = _refresh_complete
            should_probe = False
        else:
            completion = threading.Event()
            _refresh_complete = completion
            should_probe = True

    if not should_probe:
        completion.wait()
        return get_cached_health_status()

    try:
        status = _probe_health_status()
        _health_collection().update_one(
            {"_id": _CACHE_ID},
            {"$set": {"_id": _CACHE_ID, **status}},
            upsert=True,
        )
        return status
    finally:
        with _refresh_state_lock:
            _refresh_complete = None
            completion.set()


def get_health_status() -> dict[str, Any]:
    return get_cached_health_status()


async def _health_refresh_scheduler() -> None:
    try:
        cached = await asyncio.to_thread(get_cached_health_status)
    except Exception:
        logger.exception("Initial system health cache read failed")
        cached = _empty_health_status()
    if cached.get("checked_at") is None:
        try:
            await asyncio.to_thread(refresh_health_status)
        except Exception:
            logger.exception("Initial system health refresh failed")

    interval = max(10, int(setting.SYSTEM_HEALTH_REFRESH_SECONDS))
    while True:
        await asyncio.sleep(interval)
        try:
            await asyncio.to_thread(refresh_health_status)
        except Exception:
            logger.exception("Scheduled system health refresh failed")


def start_health_refresh_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task is not None and not _scheduler_task.done():
        return
    _scheduler_task = asyncio.create_task(
        _health_refresh_scheduler(),
        name="system-health-refresh-scheduler",
    )
    logger.info(
        "System health refresh scheduler started, interval=%ss",
        setting.SYSTEM_HEALTH_REFRESH_SECONDS,
    )


def stop_health_refresh_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task is not None:
        _scheduler_task.cancel()
        _scheduler_task = None
