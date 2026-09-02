from core.config import resolve_sqlite_path, use_sqlite_persistence
from modules.supplies.mongo_repository import MongoSupplementaryMaterialRepository
from modules.supplies.repository import SupplementaryMaterialRepository
from modules.supplies.service import SupplementaryMaterialService


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
supplementary_material_service = SupplementaryMaterialService(supplementary_material_repository)


def configure_supplementary_material_repository():
    """Apply the persistence backend selected during application startup."""

    global supplementary_material_repository
    supplementary_material_repository = create_supplementary_material_repository()
    supplementary_material_service.repository = supplementary_material_repository
    return supplementary_material_repository
