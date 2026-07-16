from fastapi import APIRouter, HTTPException, Query, status

from workflows.models import (
    Workflow,
    WorkflowCreate,
    WorkflowRun,
    WorkflowTriggerRequest,
    WorkflowUpdate,
)
from workflows.runtime import workflow_service
from workflows.service import WorkflowNotFoundError
from duro.routes import router as duro_router
from sop.routes import router as sop_router


router = APIRouter()
router.include_router(duro_router)
router.include_router(sop_router)


@router.get("/health")
def health() -> dict[str, object]:
    return {"success": True, "service": "productions-versions"}


@router.get("/workflows", response_model=list[Workflow])
def list_workflows() -> list[Workflow]:
    return workflow_service.list_workflows()


@router.post("/workflows", response_model=Workflow, status_code=status.HTTP_201_CREATED)
def create_workflow(payload: WorkflowCreate) -> Workflow:
    return workflow_service.create_workflow(payload)


@router.get("/workflows/{workflow_id}", response_model=Workflow)
def get_workflow(workflow_id: str) -> Workflow:
    try:
        return workflow_service.get_workflow(workflow_id)
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/workflows/{workflow_id}", response_model=Workflow)
def update_workflow(workflow_id: str, payload: WorkflowUpdate) -> Workflow:
    try:
        return workflow_service.update_workflow(workflow_id, payload)
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/workflows/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workflow(workflow_id: str) -> None:
    try:
        workflow_service.delete_workflow(workflow_id)
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/workflows/{workflow_id}/trigger", response_model=WorkflowRun)
def trigger_workflow(workflow_id: str, payload: WorkflowTriggerRequest) -> WorkflowRun:
    try:
        return workflow_service.trigger_workflow(workflow_id, payload.trigger_type)
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/workflow-runs", response_model=list[WorkflowRun])
def list_workflow_runs(
    workflow_id: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=200),
) -> list[WorkflowRun]:
    return workflow_service.list_runs(workflow_id=workflow_id, limit=limit)
