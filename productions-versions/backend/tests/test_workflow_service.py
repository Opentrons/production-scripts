from __future__ import annotations

import time
from pathlib import Path

from workflows.models import WorkflowCreate, WorkflowSchedule, WorkflowStep, WorkflowUpdate
from workflows.repository import WorkflowRepository
from workflows.service import WorkflowService


def make_service(tmp_path: Path) -> WorkflowService:
    return WorkflowService(WorkflowRepository(tmp_path / "workflows.json"))


def test_initialize_creates_duro_bom_workflow(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    service.initialize()

    workflows = service.list_workflows()
    assert len(workflows) == 1
    assert workflows[0].kind == "duro_bom_check"
    assert [step.kind for step in workflows[0].steps] == ["duro_bom_fetch", "bom_compare", "report"]


def test_create_and_schedule_workflow(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    workflow = service.create_workflow(
        WorkflowCreate(
            name="版本核对",
            status="active",
            schedule=WorkflowSchedule(enabled=True, interval_minutes=30),
            steps=[WorkflowStep(name="检查版本")],
        )
    )

    assert workflow.next_run_at is not None

    updated = service.update_workflow(
        workflow.id,
        WorkflowUpdate(schedule=WorkflowSchedule(enabled=False, interval_minutes=30)),
    )
    assert updated.next_run_at is None


def test_manual_duro_run_is_recorded_as_skipped_until_connector_exists(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    workflow = service.list_workflows()[0]

    run = service.trigger_workflow(workflow.id, "manual")

    deadline = time.monotonic() + 2
    current = run
    while current.status in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(0.01)
        current = service.list_runs(workflow_id=workflow.id, limit=1)[0]

    assert current.status == "skipped"
    assert current.message == "Duro API 连接器待配置"
