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
WorkflowBomDifferenceStatus = Literal[
    "missing_in_duro",
    "extra_in_duro",
    "quantity_mismatch",
    "quantity_unknown",
]


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
    run_count: int = 0


class WorkflowTriggerRequest(BaseModel):
    trigger_type: WorkflowTriggerType = "manual"


class WorkflowSopQuantityDecision(BaseModel):
    source: str = ""
    event_id: str = ""
    page_numbers: list[int] = Field(default_factory=list)
    action: str = ""
    target: str = ""
    location: str = ""
    quantity_delta: float = 0
    accumulate: bool = False
    duplicate_of: str | None = None
    reason: str = ""
    evidence: str = ""


class WorkflowBomDifference(BaseModel):
    status: WorkflowBomDifferenceStatus
    part_number: str
    name: str = ""
    sop_quantity: float | None = None
    duro_quantity: float | None = None
    quantity_delta: float | None = None
    sop_locations: list[str] = Field(default_factory=list)
    sop_quantity_explanations: list[str] = Field(default_factory=list)
    sop_quantity_decisions: list[WorkflowSopQuantityDecision] = Field(default_factory=list)
    duro_paths: list[str] = Field(default_factory=list)
    duro_submenu_ids: list[str] = Field(default_factory=list)
    duro_submenu_labels: list[str] = Field(default_factory=list)


class WorkflowBomIgnoredItem(WorkflowBomDifference):
    ignore_type: Literal["sop_product_keyword", "part_number", "part_number_cleanup"]
    ignore_value: str
    ignore_reason: str
    normalized_part_number: str | None = None


class WorkflowBomReport(BaseModel):
    generated_at: datetime = Field(default_factory=utc_now)
    sop_source_count: int = 0
    sop_material_count: int = 0
    duro_material_count: int = 0
    matched_count: int = 0
    missing_in_duro_count: int = 0
    extra_in_duro_count: int = 0
    quantity_mismatch_count: int = 0
    quantity_unknown_count: int = 0
    duro_submenus: list[dict[str, str]] = Field(default_factory=list)
    differences: list[WorkflowBomDifference] = Field(default_factory=list)
    total_difference_count: int = 0
    ignored_items: list[WorkflowBomIgnoredItem] = Field(default_factory=list)
    total_ignored_count: int = 0
    warning_difference_count: int | None = None

    @property
    def difference_count(self) -> int:
        return len(self.differences)


class WorkflowRun(BaseModel):
    id: str = Field(default_factory=lambda: new_id("run"))
    workflow_id: str
    workflow_name: str
    trigger_type: WorkflowTriggerType
    status: WorkflowRunStatus = "queued"
    message: str = ""
    logs: list[str] = Field(default_factory=list)
    report: WorkflowBomReport | None = None
    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None


class WorkflowRunDetailResponse(BaseModel):
    run: WorkflowRun
    difference_offset: int = 0
    difference_limit: int = 5000
    difference_total: int = 0
    has_more: bool = False


class WorkflowRunPage(BaseModel):
    items: list[WorkflowRun] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 10
    success_count: int = 0
    failed_count: int = 0
    warning_count: int = 0


class WorkflowRunDeleteRequest(BaseModel):
    run_ids: list[str] = Field(min_length=1, max_length=200)


class WorkflowRunDeleteResponse(BaseModel):
    deleted_count: int = 0
