from modules.duro.runtime import duro_service
from core.config import SCHEDULER_POLL_SECONDS, resolve_sqlite_path, use_sqlite_persistence
from modules.sop.runtime import sop_service
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
)
workflow_scheduler = WorkflowScheduler(workflow_service, SCHEDULER_POLL_SECONDS)
