from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


TestCaseStatus = Literal["draft", "active", "archived"]
TestNodeKind = Literal["start", "expect", "end"]
TestInputKind = Literal["none", "boolean", "text", "radio"]
TestExecutionStatus = Literal[
    "created",
    "running",
    "waiting_input",
    "passed",
    "failed",
    "error",
    "timeout",
    "stopped",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class NodePosition(BaseModel):
    x: float = 0
    y: float = 0


class TestCaseInputOption(BaseModel):
    label: str
    value: str


class TestCaseNode(BaseModel):
    id: str = Field(default_factory=lambda: new_id("node"))
    name: str
    kind: TestNodeKind = "expect"
    expect: str | None = None
    input_kind: TestInputKind = "none"
    input_options: list[TestCaseInputOption] = Field(default_factory=list)
    position: NodePosition = Field(default_factory=NodePosition)


class TestCaseEdge(BaseModel):
    id: str = Field(default_factory=lambda: new_id("edge"))
    source: str
    target: str
    condition: str | None = None


class TestCaseErrorPattern(BaseModel):
    name: str
    pattern: str
    severity: Literal["warning", "error", "fatal"] = "error"


class TestCaseBase(BaseModel):
    name: str
    product_id: str
    product_name: str
    test_type: str
    command: str
    description: str | None = None
    timeout_seconds: int = 300
    status: TestCaseStatus = "draft"
    nodes: list[TestCaseNode] = Field(default_factory=list)
    edges: list[TestCaseEdge] = Field(default_factory=list)
    error_patterns: list[TestCaseErrorPattern] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TestCaseCreate(TestCaseBase):
    pass


class TestCaseUpdate(BaseModel):
    name: str | None = None
    product_id: str | None = None
    product_name: str | None = None
    test_type: str | None = None
    command: str | None = None
    description: str | None = None
    timeout_seconds: int | None = None
    status: TestCaseStatus | None = None
    nodes: list[TestCaseNode] | None = None
    edges: list[TestCaseEdge] | None = None
    error_patterns: list[TestCaseErrorPattern] | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


class TestCase(TestCaseBase):
    id: str = Field(default_factory=lambda: new_id("case"))
    revision: int = 1
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    last_run_at: datetime | None = None
    run_count: int = 0
    success_count: int = 0
    failed_count: int = 0


class TestProductCreate(BaseModel):
    product_id: str
    product_name: str


class TestProduct(TestProductCreate):
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class TestTypeCreate(BaseModel):
    test_type: str


class TestType(TestTypeCreate):
    product_id: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class TestCaseListResponse(BaseModel):
    cases: list[TestCase]
    total: int


class TestCaseTreeCase(BaseModel):
    id: str
    name: str
    status: TestCaseStatus
    test_type: str
    updated_at: datetime


class TestCaseTreeGroup(BaseModel):
    test_type: str
    total: int
    cases: list[TestCaseTreeCase]


class TestCaseTreeProduct(BaseModel):
    product_id: str
    product_name: str
    total: int
    groups: list[TestCaseTreeGroup]


class TestCaseTreeResponse(BaseModel):
    products: list[TestCaseTreeProduct]
    total: int


class ExecutionStatusResponse(BaseModel):
    max_sessions: int = 20
    active_ssh_sessions: int = 0
    observer_clients: int = 0
    running_tests: int = 0
    waiting_input_tests: int = 0
    queued_tests: int = 0
    available_sessions: int = 20


class TestExecutionStartRequest(BaseModel):
    case_id: str
    device_ip: str | None = None


class TestExecutionWaitingInputRequest(BaseModel):
    node_id: str
    expect: str | None = None
    input_kind: TestInputKind
    input_options: list[TestCaseInputOption] = Field(default_factory=list)


class TestExecutionInputRequest(BaseModel):
    node_id: str
    value: str


class TestExecutionNodeRequest(BaseModel):
    node_id: str


class TestExecutionCompleteRequest(BaseModel):
    status: Literal["passed", "failed", "error", "timeout", "stopped"] = "passed"
    message: str | None = None


class TestExecutionEvent(BaseModel):
    type: str
    node_id: str | None = None
    value: str | None = None
    message: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class TestExecutionRunResponse(BaseModel):
    id: str
    case_id: str
    case_name: str
    command: str
    status: TestExecutionStatus
    device_ip: str | None = None
    current_node_id: str | None = None
    waiting_node_id: str | None = None
    waiting_input_kind: TestInputKind | None = None
    waiting_options: list[TestCaseInputOption] = Field(default_factory=list)
    events: list[TestExecutionEvent] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
