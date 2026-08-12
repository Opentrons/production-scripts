from contextlib import asynccontextmanager
import asyncio
import os

from fastapi import FastAPI

from core.config import DURO_TOKEN_AUTO_REFRESH_SECONDS
from core.database import mongodb
from core.google.proxy_manager import google_proxy_manager
from core.logging import get_logger
from core.runtime_mode import ensure_db_layout, is_simulating
from modules.duro.runtime import (
    duro_browser_token_provider,
    ensure_duro_remote_chrome_running,
)
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
    mongodb.connect()
    fail_interrupted_diagnostic_log_downloads()
    resume_pending_diagnostic_log_cleanups()
    start_robot_scan_scheduler()
    google_proxy_manager.start()
    ensure_duro_remote_chrome_running()
    if duro_browser_token_provider is not None:
        duro_browser_token_provider.start_auto_refresh(DURO_TOKEN_AUTO_REFRESH_SECONDS)
    workflow_service.initialize()
    workflow_scheduler.start()

    if runtime_config.USE_PROXY and should_refresh_proxy_on_startup():
        try:
            await asyncio.to_thread(refresh_best_proxy_config)
        except Exception as exc:
            logger.warning("Startup proxy refresh failed: %s", exc)

    try:
        yield
    finally:
        workflow_scheduler.stop()
        google_proxy_manager.stop()
        if duro_browser_token_provider is not None:
            duro_browser_token_provider.close()
        shutdown_robot_service()
        shutdown_diagnostic_log_service()
        shutdown_upload_service()
        GoogleDriveDriver.shutdown_shared_services()
        mongodb.close()
