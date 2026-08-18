from contextlib import asynccontextmanager
import asyncio
import os

from fastapi import FastAPI

from core.config import IS_DEV_ENV, MONGO_HOST, MONGO_URI
from core.database import mongodb
from core.google.proxy_manager import google_proxy_manager
from core.logging import get_logger
from core.runtime_mode import ensure_db_layout, is_simulating
from modules.system.health import start_health_refresh_scheduler, stop_health_refresh_scheduler
from modules.auth.dependencies import get_auth_service
from modules.system.simulating_seed import ensure_simulating_seed
from modules.robots.diagnostic_logs import (
    fail_interrupted_diagnostic_log_downloads,
    resume_pending_diagnostic_log_cleanups,
    shutdown_diagnostic_log_service,
)
from modules.robots.robots import (
    shutdown_robot_service,
    start_robot_scan_scheduler,
)
from modules.uploads.handler.drivers.google_drive import (
    GoogleDriveDriver,
    refresh_best_proxy_config,
)
from modules.uploads.handler.utils import runtime_config
from modules.uploads.upload import shutdown_upload_service
from modules.workflows.runtime import workflow_scheduler, workflow_service
from modules.agent.schedules import agent_schedule_scheduler


logger = get_logger(__name__)


def should_refresh_proxy_on_startup() -> bool:
    raw_value = os.getenv("PRODUCTION_PLATFORM_REFRESH_PROXY_ON_STARTUP", "true")
    return raw_value.strip().lower() not in {"0", "false", "no", "off"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_db_layout()
    get_auth_service().initialize()
    if is_simulating():
        ensure_simulating_seed()
    mongo_available = is_simulating() or mongodb.connect()
    if not mongo_available:
        target = "PRODUCTION_PLATFORM_MONGO_URI" if MONGO_URI else f"{MONGO_HOST}:27017"
        if not IS_DEV_ENV:
            raise RuntimeError(
                "MongoDB is required for non-development business persistence but is "
                f"unavailable ({target}). Start MongoDB or set "
                "PRODUCTION_PLATFORM_MONGO_URI to a reachable server."
            )
        logger.error(
            "MongoDB is unavailable (%s). Starting in degraded local mode: "
            "SQLite authentication and real device scanning remain available; "
            "Mongo-backed business features are paused until MongoDB recovers.",
            target,
        )
    if mongo_available:
        fail_interrupted_diagnostic_log_downloads()
        resume_pending_diagnostic_log_cleanups()
    start_robot_scan_scheduler()
    google_proxy_manager.start()
    if mongo_available or IS_DEV_ENV:
        start_health_refresh_scheduler()
    if mongo_available:
        workflow_service.initialize()
        workflow_scheduler.start()
        agent_schedule_scheduler.start()
    else:
        logger.warning(
            "Mongo-backed workflow and Agent schedulers are disabled "
            "for this process"
        )

    # Do not block API readiness on proxy probing; login and other routes must
    # stay available while the optional Google proxy refresh runs in background.
    if runtime_config.USE_PROXY and should_refresh_proxy_on_startup():
        async def _refresh_proxy_in_background() -> None:
            try:
                await asyncio.to_thread(refresh_best_proxy_config)
            except Exception as exc:
                logger.warning("Startup proxy refresh failed: %s", exc)

        asyncio.create_task(_refresh_proxy_in_background())

    try:
        yield
    finally:
        workflow_scheduler.stop()
        agent_schedule_scheduler.stop()
        stop_health_refresh_scheduler()
        google_proxy_manager.stop()
        shutdown_robot_service()
        shutdown_diagnostic_log_service()
        shutdown_upload_service()
        GoogleDriveDriver.shutdown_shared_services()
        mongodb.close()
