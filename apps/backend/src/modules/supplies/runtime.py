from core.config import resolve_sqlite_path
from modules.supplies.repository import SupplementaryMaterialRepository
from modules.supplies.service import SupplementaryMaterialService


supplementary_material_repository = SupplementaryMaterialRepository(
    resolve_sqlite_path(
        "supplementary_materials.sqlite3",
        env_var="PRODUCTION_PLATFORM_SUPPLEMENTARY_MATERIALS_DB_PATH",
    ),
    seed_initial=True,
)
supplementary_material_service = SupplementaryMaterialService(supplementary_material_repository)
