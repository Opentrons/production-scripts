from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status

from workflows.models import (
    Workflow,
    WorkflowCreate,
    WorkflowRun,
    WorkflowRunDetailResponse,
    WorkflowRunDeleteRequest,
    WorkflowRunDeleteResponse,
    WorkflowRunPage,
    WorkflowTriggerRequest,
    WorkflowUpdate,
)
from workflows.runtime import workflow_service
from workflows.service import WorkflowNotFoundError
from duro.routes import router as duro_router
from google_driver.proxy_manager import google_proxy_manager
from sop.routes import router as sop_router
from llm.routes import router as sop_ai_router


router = APIRouter()
router.include_router(duro_router)
router.include_router(sop_router)
router.include_router(sop_ai_router)


@router.get("/health")
def health() -> dict[str, object]:
    return {"success": True, "service": "productions-versions"}


@router.get("/google/status")
def google_status() -> dict[str, object]:
    return google_proxy_manager.status()


@router.post("/google/proxy/refresh")
def refresh_google_proxy() -> dict[str, object]:
    started = google_proxy_manager.refresh_async()
    return {**google_proxy_manager.status(), "started": started}


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


@router.get("/workflow-runs", response_model=WorkflowRunPage)
def list_workflow_runs(
    workflow_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
) -> WorkflowRunPage:
    return workflow_service.list_run_page(
        workflow_id=workflow_id,
        page=page,
        page_size=page_size,
        created_from=created_from.isoformat() if created_from else None,
        created_to=created_to.isoformat() if created_to else None,
    )


@router.delete("/workflow-runs", response_model=WorkflowRunDeleteResponse)
def delete_workflow_runs(payload: WorkflowRunDeleteRequest) -> WorkflowRunDeleteResponse:
    return workflow_service.delete_runs(payload.run_ids)


@router.get("/workflow-runs/{run_id}", response_model=WorkflowRunDetailResponse)
def get_workflow_run_detail(
    run_id: str,
    difference_offset: int = Query(default=0, ge=0),
    difference_limit: int = Query(default=5000, ge=1, le=5000),
) -> WorkflowRunDetailResponse:
    try:
        return workflow_service.get_run_detail(run_id, difference_offset, difference_limit)
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
