from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace

from duro.models import DuroBomNode
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
    assert workflows[0].configuration["sop_drive_file_id"] == ""
    assert workflows[0].configuration["duro_product_id"] == ""
    assert workflows[0].configuration["ignored_part_numbers"] == []
    assert [step.kind for step in workflows[0].steps] == ["bom_compare", "report"]
    assert [step.name for step in workflows[0].steps] == ["核对 Duro BOM", "核对报告"]


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


def test_workflow_persists_sop_and_duro_source_configuration(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    workflow = service.create_workflow(
        WorkflowCreate(
            name="SOP 与 Duro 核对",
            kind="duro_bom_check",
            configuration={
                "sop_drive_file_id": "drive-file-id",
                "sop_project": "Flex Robot",
                "sop_process": "Assembly",
                "duro_product_id": "duro-product-id",
                "duro_product_name": "Flex Robot",
                "duro_product_revision": "A1",
                "target_revision": "A1",
                "ignored_part_numbers": [" 100-00001 ", "100-00001"],
            },
        )
    )

    stored = service.get_workflow(workflow.id)

    assert stored.configuration["sop_drive_file_id"] == "drive-file-id"
    assert stored.configuration["sop_drive_file_ids"] == ["drive-file-id"]
    assert stored.configuration["sop_sources"][0]["project"] == "Flex Robot"
    assert stored.configuration["duro_product_id"] == "duro-product-id"
    assert stored.configuration["target_revision"] == "A1"
    assert stored.configuration["ignored_part_numbers"] == ["100-00001"]


def test_manual_duro_run_requires_sop_and_duro_sources(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    workflow = service.list_workflows()[0]

    run = service.trigger_workflow(workflow.id, "manual")

    deadline = time.monotonic() + 2
    current = run
    while current.status in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(0.01)
        current = service.list_runs(workflow_id=workflow.id, limit=1)[0]

    assert current.status == "skipped"
    assert current.message == "请先配置数据源：SOP Include Assembly、Duro 产品"


class FakeSopService:
    def analyze_pdf(self, file_id: str):
        materials = {
            "sop-a": [
                SimpleNamespace(part_number="100-00001", name="Bolt", occurrences=2, pages=[1]),
                SimpleNamespace(part_number="100-00002", name="Washer", occurrences=1, pages=[2]),
                SimpleNamespace(part_number="100-00003", name="Grease", occurrences=1, pages=[3]),
            ],
            "sop-b": [
                SimpleNamespace(part_number="100-00001", name="Bolt", occurrences=3, pages=[4]),
                SimpleNamespace(part_number="100-00005", name="Clip", occurrences=4, pages=[5]),
            ],
        }
        return SimpleNamespace(full_text_references=materials[file_id])


class FakeDuroService:
    def get_product_bom(self, product_id: str):
        assert product_id == "duro-product"
        return SimpleNamespace(
            root=DuroBomNode(
                id="root",
                node_type="product",
                name="Product",
                cpn="999-00001",
                children=[
                    DuroBomNode(id="bolt", name="Bolt", cpn="100-00001", quantity=5),
                    DuroBomNode(id="assembly", name="Sub Assembly", cpn="200-00001", quantity=2, has_children=True),
                    DuroBomNode(id="grease", name="Grease", cpn="100-00003", quantity=1),
                ],
            )
        )

    def get_component_children(self, component_id: str):
        assert component_id == "assembly"
        return SimpleNamespace(
            children=[
                DuroBomNode(id="washer", name="Washer", cpn="100-00002", quantity=1),
                DuroBomNode(id="extra", name="Extra", cpn="100-00004", quantity=1),
            ]
        )


class EmptySopService:
    def analyze_pdf(self, file_id: str):
        return SimpleNamespace(full_text_references=[])


def test_manual_duro_run_generates_bom_difference_report(tmp_path: Path) -> None:
    service = WorkflowService(
        WorkflowRepository(tmp_path / "workflows.json"),
        sop_service=FakeSopService(),  # type: ignore[arg-type]
        duro_service=FakeDuroService(),  # type: ignore[arg-type]
    )
    workflow = service.create_workflow(
        WorkflowCreate(
            name="真实 BOM 核对",
            kind="duro_bom_check",
            configuration={
                "sop_drive_file_ids": ["sop-a", "sop-b"],
                "sop_sources": [
                    {"drive_file_id": "sop-a", "project": "Robot", "process": "Assembly A"},
                    {"drive_file_id": "sop-b", "project": "Robot", "process": "Assembly B"},
                ],
                "duro_product_id": "duro-product",
                "duro_product_name": "Product",
                "ignored_part_numbers": [" 100-00004 ", "100-00004"],
            },
        )
    )

    run = service.trigger_workflow(workflow.id, "manual")
    deadline = time.monotonic() + 2
    current = run
    while current.status in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(0.01)
        current = service.list_runs(workflow_id=workflow.id, limit=1)[0]

    assert current.status == "succeeded"
    assert current.report is not None
    assert current.report.sop_source_count == 2
    assert current.report.matched_count == 2
    assert current.report.missing_in_duro_count == 1
    assert current.report.extra_in_duro_count == 1
    assert current.report.quantity_mismatch_count == 1
    assert current.report.quantity_unknown_count == 0
    assert len(current.report.differences) == 3
    assert all(item.part_number != "100-00004" for item in current.report.differences)


def test_manual_duro_run_rejects_sop_without_full_text_references(tmp_path: Path) -> None:
    service = WorkflowService(
        WorkflowRepository(tmp_path / "workflows.json"),
        sop_service=EmptySopService(),  # type: ignore[arg-type]
        duro_service=FakeDuroService(),  # type: ignore[arg-type]
    )
    workflow = service.create_workflow(
        WorkflowCreate(
            name="无 BOM SOP",
            kind="duro_bom_check",
            configuration={
                "sop_sources": [
                    {"drive_file_id": "sop-empty", "project": "Robot", "process": "Assembly"},
                ],
                "duro_product_id": "duro-product",
            },
        )
    )

    run = service.trigger_workflow(workflow.id, "manual")
    deadline = time.monotonic() + 2
    current = run
    while current.status in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(0.01)
        current = service.list_runs(workflow_id=workflow.id, limit=1)[0]

    assert current.status == "failed"
    assert "未识别到全文料号引用" in current.message
    assert current.report is None
