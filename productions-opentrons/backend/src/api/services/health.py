from __future__ import annotations

import platform
import subprocess
import time

import settings as setting
from slack_driver.message import SlackBotMessenger
from upload_handler.utils import google_drive_health_check

from api.services.logging import logger


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
            {"status": "unhealthy", "message": f"Slack connection failed: {str(exc)}"},
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
            {"status": "unhealthy", "message": f"Google Drive connection failed: {str(exc)}"},
            started_at,
        )


def get_health_status() -> dict:
    started_at = time.perf_counter()
    service_check = check_systemctl_service("data-handler")
    slack_ok, slack_status = check_slack_health()
    google_ok, google_status = check_google_drive_health()
    service_ok = service_check.get("status") == "running"
    return {
        "status": service_ok and slack_ok and google_ok,
        "elapsed_ms": round((time.perf_counter() - started_at) * 1000, 2),
        "services": {
            "system_service": service_check,
            "slack": slack_status,
            "google_drive": google_status,
        },
    }
