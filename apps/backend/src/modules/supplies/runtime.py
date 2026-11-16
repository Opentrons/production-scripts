from core.config import (
    SUPPLIES_SOURCE_SPREADSHEET_ID, SUPPLIES_SOURCE_SHEET_GID, SUPPLIES_SOURCE_SHEET_TITLE,
    SUPPLIES_AUTO_SYNC_SECONDS, SUPPLIES_AUTO_SYNC_ENABLED, resolve_sqlite_path, use_sqlite_persistence,
)
from core.google import GoogleDriver
from core.runtime_mode import is_simulating
from modules.supplies.mongo_repository import MongoSupplementaryMaterialRepository
from modules.supplies.repository import SupplementaryMaterialRepository
from modules.supplies.service import SupplementaryMaterialService
from modules.supplies.source import GoogleSupplementaryMaterialSource
from modules.supplies.scheduler import SupplementaryMaterialSyncScheduler


def create_supplementary_material_repository():
    if use_sqlite_persistence():
        return SupplementaryMaterialRepository(
            resolve_sqlite_path(
                "supplementary_materials.sqlite3",
                env_var="PRODUCTION_PLATFORM_SUPPLEMENTARY_MATERIALS_DB_PATH",
            ),
            seed_initial=True,
        )
    return MongoSupplementaryMaterialRepository(seed_initial=True)


supplementary_material_repository = create_supplementary_material_repository()
supplementary_material_service = SupplementaryMaterialService(
    supplementary_material_repository,
    GoogleSupplementaryMaterialSource(
        GoogleDriver(allow_interactive_auth=False), SUPPLIES_SOURCE_SPREADSHEET_ID, SUPPLIES_SOURCE_SHEET_GID, SUPPLIES_SOURCE_SHEET_TITLE,
    ),
    sync_interval_seconds=SUPPLIES_AUTO_SYNC_SECONDS,
    auto_sync_enabled=SUPPLIES_AUTO_SYNC_ENABLED and not is_simulating(),
)
supplementary_material_sync_scheduler = SupplementaryMaterialSyncScheduler(
    supplementary_material_service, SUPPLIES_AUTO_SYNC_SECONDS,
)


def configure_supplementary_material_repository():
    """Apply the persistence backend selected during application startup."""

    global supplementary_material_repository
    supplementary_material_repository = create_supplementary_material_repository()
    supplementary_material_service.repository = supplementary_material_repository
    return supplementary_material_repository
