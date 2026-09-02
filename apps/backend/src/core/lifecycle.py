from contextlib import asynccontextmanager
import asyncio
import os

from fastapi import FastAPI

from core.config import (
    DEV_SQLITE_FALLBACK_ENABLED,
    IS_DEV_ENV,
    MONGO_HOST,
    MONGO_URI,
    use_sqlite_persistence,
)
from core.database import mongodb
from core.google.proxy_manager import google_proxy_manager
from core.logging import get_logger
from core.runtime_mode import (
    ensure_db_layout,
    is_simulating,
    set_sqlite_fallback,
)
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
from modules.uploads.scheduler import upload_scheduler
from modules.workflows.runtime import (
    configure_workflow_repository,
    workflow_scheduler,
    workflow_service,
)
from modules.agent.schedules import agent_schedule_scheduler
from modules.bridge_tokens.runtime import (
    bridge_token_configuration_service,
    bridge_token_scheduler,
    bridge_token_service,
)
from modules.supplies.runtime import configure_supplementary_material_repository


logger = get_logger(__name__)


def should_refresh_proxy_on_startup() -> bool:
    raw_value = os.getenv("PRODUCTION_PLATFORM_REFRESH_PROXY_ON_STARTUP", "true")
    return raw_value.strip().lower() not in {"0", "false", "no", "off"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_db_layout()
    get_auth_service().initialize()
    simulating = is_simulating()
    if simulating:
        ensure_simulating_seed()
        set_sqlite_fallback(False)
        mongo_available = False
    else:
        mongo_available = mongodb.connect()
    if not mongo_available and not simulating:
        target = "PRODUCTION_PLATFORM_MONGO_URI" if MONGO_URI else f"{MONGO_HOST}:27017"
        if not IS_DEV_ENV:
            raise RuntimeError(
                "MongoDB is required for non-development business persistence but is "
                f"unavailable ({target}). Start MongoDB or set "
                "PRODUCTION_PLATFORM_MONGO_URI to a reachable server."
            )
        if DEV_SQLITE_FALLBACK_ENABLED:
            set_sqlite_fallback(True, reason=f"MongoDB unavailable ({target})")
            logger.warning(
                "MongoDB is unavailable (%s). Development business persistence "
                "is using SQLite fallback for this process.",
                target,
            )
        else:
            set_sqlite_fallback(False)
            logger.error(
                "MongoDB is unavailable (%s). Development SQLite fallback is disabled; "
                "Mongo-backed business features are paused.",
                target,
            )
    elif mongo_available:
        set_sqlite_fallback(False)

    configure_supplementary_material_repository()
    configure_workflow_repository()
    business_persistence_available = mongo_available or use_sqlite_persistence()

    if mongo_available:
        fail_interrupted_diagnostic_log_downloads()
        resume_pending_diagnostic_log_cleanups()
    start_robot_scan_scheduler()
    google_proxy_manager.start()
    if business_persistence_available or IS_DEV_ENV:
        start_health_refresh_scheduler()
    if business_persistence_available:
        workflow_service.initialize()
        bridge_token_service.initialize()
        if mongo_available:
            bridge_token_configuration_service.initialize()
        workflow_scheduler.start()
        bridge_token_scheduler.start()
        agent_schedule_scheduler.start()
        upload_scheduler.start()
    else:
        logger.warning(
            "Business workflow and Agent schedulers are disabled "
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
        upload_scheduler.stop()
        bridge_token_scheduler.stop()
        workflow_scheduler.stop()
        agent_schedule_scheduler.stop()
        stop_health_refresh_scheduler()
        google_proxy_manager.stop()
        shutdown_robot_service()
        shutdown_diagnostic_log_service()
        shutdown_upload_service()
        GoogleDriveDriver.shutdown_shared_services()
        mongodb.close()
