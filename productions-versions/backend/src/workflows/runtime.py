from settings import SCHEDULER_POLL_SECONDS, WORKFLOW_STORE_PATH
from workflows.repository import WorkflowRepository
from workflows.scheduler import WorkflowScheduler
from workflows.service import WorkflowService


workflow_repository = WorkflowRepository(WORKFLOW_STORE_PATH)
workflow_service = WorkflowService(workflow_repository)
workflow_scheduler = WorkflowScheduler(workflow_service, SCHEDULER_POLL_SECONDS)
