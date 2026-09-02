from modules.duro.runtime import duro_service
from core.config import SCHEDULER_POLL_SECONDS, resolve_sqlite_path, use_sqlite_persistence
from modules.sop.runtime import sop_service
from modules.supplies.runtime import supplementary_material_service
from modules.workflows.mongo_repository import MongoWorkflowRepository
from modules.workflows.repository import WorkflowRepository
from modules.workflows.scheduler import WorkflowScheduler
from modules.workflows.service import WorkflowService


def create_workflow_repository() -> WorkflowRepository | MongoWorkflowRepository:
    if use_sqlite_persistence():
        return WorkflowRepository(
            resolve_sqlite_path(
                "workflows.sqlite3",
                env_var="PRODUCTION_PLATFORM_WORKFLOW_DB_PATH",
            )
        )
    return MongoWorkflowRepository()


workflow_repository = create_workflow_repository()
workflow_service = WorkflowService(
    workflow_repository,
    sop_service=sop_service,
    duro_service=duro_service,
    supplies_service=supplementary_material_service,
)
workflow_scheduler = WorkflowScheduler(workflow_service, SCHEDULER_POLL_SECONDS)


def configure_workflow_repository() -> WorkflowRepository | MongoWorkflowRepository:
    """Apply the persistence backend selected during application startup."""

    global workflow_repository
    workflow_repository = create_workflow_repository()
    workflow_service.set_repository(workflow_repository)
    return workflow_repository
