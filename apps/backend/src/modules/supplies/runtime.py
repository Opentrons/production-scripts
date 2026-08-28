from core.config import IS_DEV_ENV, resolve_sqlite_path, use_sqlite_persistence
from modules.supplies.mongo_repository import MongoSupplementaryMaterialRepository
from modules.supplies.repository import SupplementaryMaterialRepository
from modules.supplies.service import SupplementaryMaterialService


if IS_DEV_ENV or use_sqlite_persistence():
    supplementary_material_repository = SupplementaryMaterialRepository(
        resolve_sqlite_path(
            "supplementary_materials.sqlite3",
            env_var="PRODUCTION_PLATFORM_SUPPLEMENTARY_MATERIALS_DB_PATH",
        ),
        seed_initial=True,
    )
else:
    supplementary_material_repository = MongoSupplementaryMaterialRepository(seed_initial=True)
supplementary_material_service = SupplementaryMaterialService(supplementary_material_repository)
