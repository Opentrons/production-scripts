from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


WorkflowKind = Literal["duro_bom_check", "custom"]
WorkflowStatus = Literal["draft", "active", "paused"]
WorkflowRunStatus = Literal["queued", "running", "succeeded", "failed", "skipped"]
WorkflowTriggerType = Literal["manual", "scheduled"]
WorkflowStepKind = Literal["duro_bom_fetch", "bom_compare", "report", "custom"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class WorkflowStep(BaseModel):
    id: str = Field(default_factory=lambda: new_id("step"))
    name: str
    kind: WorkflowStepKind = "custom"
    description: str = ""
    configuration: dict[str, Any] = Field(default_factory=dict)


class WorkflowSchedule(BaseModel):
    enabled: bool = False
    interval_minutes: int = Field(default=60, ge=1, le=10080)


class WorkflowBase(BaseModel):
    name: str
    description: str = ""
    kind: WorkflowKind = "custom"
    status: WorkflowStatus = "draft"
    schedule: WorkflowSchedule = Field(default_factory=WorkflowSchedule)
    steps: list[WorkflowStep] = Field(default_factory=list)
    configuration: dict[str, Any] = Field(default_factory=dict)


class WorkflowCreate(WorkflowBase):
    pass


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    kind: WorkflowKind | None = None
    status: WorkflowStatus | None = None
    schedule: WorkflowSchedule | None = None
    steps: list[WorkflowStep] | None = None
    configuration: dict[str, Any] | None = None


class Workflow(WorkflowBase):
    id: str = Field(default_factory=lambda: new_id("workflow"))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None


class WorkflowTriggerRequest(BaseModel):
    trigger_type: WorkflowTriggerType = "manual"


class WorkflowRun(BaseModel):
    id: str = Field(default_factory=lambda: new_id("run"))
    workflow_id: str
    workflow_name: str
    trigger_type: WorkflowTriggerType
    status: WorkflowRunStatus = "queued"
    message: str = ""
    logs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
