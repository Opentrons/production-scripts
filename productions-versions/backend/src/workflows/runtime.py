from duro.runtime import duro_service
from settings import SCHEDULER_POLL_SECONDS, WORKFLOW_STORE_PATH
from sop.runtime import sop_service
from workflows.repository import WorkflowRepository
from workflows.scheduler import WorkflowScheduler
from workflows.service import WorkflowService


workflow_repository = WorkflowRepository(WORKFLOW_STORE_PATH)
workflow_service = WorkflowService(
    workflow_repository,
    sop_service=sop_service,
    duro_service=duro_service,
)
workflow_scheduler = WorkflowScheduler(workflow_service, SCHEDULER_POLL_SECONDS)
