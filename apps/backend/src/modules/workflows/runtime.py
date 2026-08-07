from modules.duro.runtime import duro_service
from core.config import SCHEDULER_POLL_SECONDS, WORKFLOW_STORE_PATH
from modules.sop.runtime import sop_service
from modules.workflows.repository import WorkflowRepository
from modules.workflows.scheduler import WorkflowScheduler
from modules.workflows.service import WorkflowService


workflow_repository = WorkflowRepository(WORKFLOW_STORE_PATH)
workflow_service = WorkflowService(
    workflow_repository,
    sop_service=sop_service,
    duro_service=duro_service,
)
workflow_scheduler = WorkflowScheduler(workflow_service, SCHEDULER_POLL_SECONDS)
