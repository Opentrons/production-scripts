from __future__ import annotations

import time
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from modules.duro.models import DuroBomNode
from modules.workflows.models import (
    Workflow,
    WorkflowBomDifference,
    WorkflowBomReport,
    WorkflowCreate,
    WorkflowRun,
    WorkflowSchedule,
    WorkflowStep,
    WorkflowUpdate,
    utc_now,
)
from modules.workflows.repository import WorkflowRepository
from modules.workflows.service import WorkflowService


def make_service(tmp_path: Path) -> WorkflowService:
    return WorkflowService(WorkflowRepository(tmp_path / "workflows.sqlite3"))


def test_initialize_creates_duro_bom_workflow(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    service.initialize()

    workflows = service.list_workflows()
    assert len(workflows) == 1
    assert workflows[0].kind == "duro_bom_check"
    assert workflows[0].configuration["sop_drive_file_id"] == ""
    assert workflows[0].configuration["duro_product_id"] == ""
    assert workflows[0].configuration["duro_submenu_ids"] == []
    assert workflows[0].configuration["duro_auto_select_submenus"] is False
    assert workflows[0].configuration["duro_auto_excluded_keywords"] == ["PACKAGING", "SOFTWARE", "TOUCHPOINTS"]
    assert workflows[0].configuration["duro_auto_zero_quantity_parent_prefixes"] == ["991-"]
    assert workflows[0].configuration["sop_bom_processes"] == ["packaging"]
    assert workflows[0].configuration["check_parent_bom"] is False
    assert workflows[0].configuration["check_supplies"] is False
    assert workflows[0].configuration["ignored_sop_product_keywords"] == []
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


def test_workflow_persists_after_repository_reopens(tmp_path: Path) -> None:
    database_path = tmp_path / "workflows.sqlite3"
    first_service = WorkflowService(WorkflowRepository(database_path))
    created = first_service.create_workflow(WorkflowCreate(name="SQLite 工作流"))

    second_service = WorkflowService(WorkflowRepository(database_path))

    assert second_service.get_workflow(created.id).name == "SQLite 工作流"


def test_initialize_marks_interrupted_runs_failed(tmp_path: Path) -> None:
    repository = WorkflowRepository(tmp_path / "workflows.sqlite3")
    workflow = repository.save_workflow(Workflow(name="Interrupted workflow"))
    run = repository.save_run(
        WorkflowRun(
            workflow_id=workflow.id,
            workflow_name=workflow.name,
            trigger_type="manual",
            status="running",
            logs=["开始执行工作流"],
            started_at=utc_now(),
        )
    )

    service = WorkflowService(repository)
    recovered = service.list_runs(workflow_id=workflow.id)[0]

    assert recovered.id == run.id
    assert recovered.status == "failed"
    assert recovered.finished_at is not None
    assert recovered.message == "后端服务重启，原执行线程已中断"
    assert recovered.logs[-1] == recovered.message


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
                "duro_submenu_ids": ["submenu-a"],
                "duro_submenus": [{"id": "submenu-a", "label": "930-00004"}],
                "ignored_sop_product_keywords": [" Robot ", "robot", "Legacy"],
                "ignored_part_numbers": [" 100-00001 ", "100-00001"],
                "check_parent_bom": True,
                "check_supplies": True,
                "sop_bom_processes": [" Packaging ", "Assembly "],
            },
        )
    )

    stored = service.get_workflow(workflow.id)

    assert stored.configuration["sop_drive_file_id"] == "drive-file-id"
    assert stored.configuration["sop_drive_file_ids"] == ["drive-file-id"]
    assert stored.configuration["sop_sources"][0]["project"] == "Flex Robot"
    assert stored.configuration["duro_product_id"] == "duro-product-id"
    assert stored.configuration["target_revision"] == "A1"
    assert stored.configuration["duro_submenu_ids"] == ["submenu-a"]
    assert stored.configuration["sop_bom_processes"] == ["packaging", "assembly"]
    assert stored.configuration["check_parent_bom"] is True
    assert stored.configuration["check_supplies"] is True
    assert stored.configuration["ignored_sop_product_keywords"] == ["Robot", "Legacy"]
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
    assert current.message == "请先配置数据源：SOP、Duro 产品"


@pytest.mark.parametrize(("name", "part_number"), [
    ("P50 O-ring", "435-12345"),
    ("P50 O-ring 435-12345", "435-12345"),
    ("P50 O-ring 999-54321", "999-54321"),
    ("P50 O-ring 1234-54321", "1234-54321"),
    ("P50 O-ring 435-012345", "435-12345"),
    ("P50 O-ring ABC-123", "ABC-123"),
    ("p50  o-RING 435-12345", "435-12345"),
    ("Ｐ５０ O-ring 435-12345", "435-12345"),
    ("P50 密封圈 435-12345", "435-12345"),
    ("P50密封圈435-12345", "435-12345"),
    ("P50 Spring 435-12345", "435-12345"),
])
def test_sop_product_rule_matches_listed_names_without_restricting_part_numbers(name: str, part_number: str) -> None:
    match = WorkflowService._matching_sop_product_rule(name, {"P50": ["O-ring", "密封圈", "Spring"]}, part_number)
    assert match is not None
    assert match[0] == "P50"
    assert match[1] in {"O-ring", "密封圈", "Spring"}


@pytest.mark.parametrize("name", [
    "P50 ------------------- 435-12345", "P50 O-ring -------- 435-12345",
    "P50 -------- O-ring 435-12345", "P50 Screw 435-12345",
    "P500 O-ring 435-12345", "P50M O-ring 435-12345", "XP50 O-ring 435-12345",
    "P50O-ring 435-12345", "P50 O-rings 435-12345", "P50 Big O-ring 435-12345",
    "P50 Retaining Ring 435-12345", "P50 O-ring holder 435-12345",
    "P50\nO-ring 435-12345", "P50\rO-ring 435-12345",
    "P50 | O-ring 435-12345", "P50 P1000 O-ring 435-12345",
    "P50 435-12345 O-ring 999-12345", "P50 435-12345", "O-ring P50 435-12345",
])
def test_sop_product_rule_preserves_unlisted_or_ambiguous_materials(name: str) -> None:
    assert WorkflowService._matching_sop_product_rule(name, {"P50": ["O-ring", "Ring"]}, "435-12345") is None


@pytest.mark.parametrize("names", [None, [], "O-ring", ["", "---", "123"], ["O-ring\nSpring"]])
def test_sop_product_rule_without_valid_list_rejects_intervening_names(names) -> None:
    assert WorkflowService._matching_sop_product_rule("P50 O-ring 435-12345", {"P50": names}, "435-12345") is None


@pytest.mark.parametrize(("name", "part_number"), [
    ("P50 435-12345", "435-12345"),
    ("P50 999-54321", "999-54321"),
    ("P50 ABC-123", "ABC-123"),
    ("p50   435-12345", "435-12345"),
    ("Ｐ５０ 435-12345", "435-12345"),
    ("P50 435-012345", "435-12345"),
    ("P50", "435-12345"),  # Extracted name and number are separate fields.
])
def test_sop_product_rule_empty_list_matches_product_directly_before_any_part_number(name: str, part_number: str) -> None:
    assert WorkflowService._matching_sop_product_rule(name, {"P50": []}, part_number) == ("P50", "")


@pytest.mark.parametrize(("name", "part_number"), [
    ("P50 O-ring 435-12345", "435-12345"),
    ("P50 Screw 435-12345", "435-12345"),
    ("P50 ------------------- 435-12345", "435-12345"),
    ("P50 | 435-12345", "435-12345"),
    ("P500 435-12345", "435-12345"),
    ("P50M 435-12345", "435-12345"),
    ("XP50 435-12345", "435-12345"),
    ("P50\n435-12345", "435-12345"),
    ("P50 435-12345 999-54321", "999-54321"),
    ("P50", ""),
    ("P50", " "),
])
def test_sop_product_rule_empty_list_keeps_ambiguous_names(name: str, part_number: str) -> None:
    assert WorkflowService._matching_sop_product_rule(name, {"P50": []}, part_number) is None


@pytest.mark.parametrize("material_names", [None, {}, {"P50": []}])
def test_sop_product_rule_missing_or_empty_list_uses_direct_product_match(tmp_path: Path, material_names) -> None:
    service = make_service(tmp_path)
    configuration = {
        "ignored_sop_product_keywords": ["P50"],
        "ignored_sop_product_keyword_reasons": {"P50": "直接产品料号不核对"},
    }
    if material_names is not None:
        configuration["ignored_sop_product_material_names"] = material_names
    workflow = service.create_workflow(WorkflowCreate(name="产品料号规则", kind="duro_bom_check", configuration=configuration))
    report = WorkflowBomReport(sop_material_count=4, duro_material_count=1, differences=[
        WorkflowBomDifference(status=status, part_number=part, name=name)
        for status, part, name in [
            ("missing_in_duro", "435-12345", "P50 435-12345"),
            ("missing_in_duro", "999-54321", "P50"),
            ("missing_in_duro", "435-12346", "P50 O-ring"),
            ("missing_in_duro", "435-12347", "P50 ------- 435-12347"),
            ("extra_in_duro", "435-12348", "P50"),
        ]
    ])
    result = service._apply_ignored_differences(service.get_workflow(workflow.id), report)
    assert {item.part_number for item in result.ignored_items} == {"435-12345", "999-54321"}
    assert {item.ignore_value for item in result.ignored_items} == {"P50 + 435-12345", "P50 + 999-54321"}
    assert {item.ignore_reason for item in result.ignored_items} == {"直接产品料号不核对"}
    assert result.sop_material_count == 2
    assert result.missing_in_duro_count == 2
    assert result.extra_in_duro_count == 1


def test_sop_product_material_lists_persist_and_update(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    workflow = service.create_workflow(WorkflowCreate(
        name="产品与料名规则", kind="duro_bom_check",
        configuration={
            "ignored_sop_product_keywords": ["P50", "P1000", "Legacy"],
            "ignored_sop_product_material_names": {
                "P50": [" O-ring ", "o-RING", "密封圈", "---", "123", None],
                "P1000": ["Spring"], "orphan": ["Screw"],
            },
        },
    ))
    assert service.get_workflow(workflow.id).configuration["ignored_sop_product_material_names"] == {
        "P50": ["O-ring", "密封圈"], "P1000": ["Spring"], "Legacy": [],
    }
    configuration = dict(workflow.configuration)
    configuration["ignored_sop_product_material_names"]["P50"] = ["Spring"]
    service.update_workflow(workflow.id, WorkflowUpdate(configuration=configuration))
    assert service.get_workflow(workflow.id).configuration["ignored_sop_product_material_names"]["P50"] == ["Spring"]
    configuration["ignored_sop_product_material_names"]["P50"] = []
    service.update_workflow(workflow.id, WorkflowUpdate(configuration=configuration))
    stored = service.get_workflow(workflow.id)
    assert stored.configuration["ignored_sop_product_material_names"]["P50"] == []
    assert service._matching_sop_product_rule("P50 435-12345", stored.configuration["ignored_sop_product_material_names"], "435-12345") == ("P50", "")
    assert service._matching_sop_product_rule("P50 Spring", stored.configuration["ignored_sop_product_material_names"], "435-12345") is None


def test_sop_product_rule_audits_product_and_material_and_preserves_other_differences(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    workflow = Workflow(name="忽略规则", configuration={
        "ignored_sop_product_keywords": ["P50"],
        "ignored_sop_product_material_names": {"P50": ["O-ring"]},
        "ignored_sop_product_keyword_reasons": {"P50": "不核对密封圈"},
    })
    differences = [
        WorkflowBomDifference(status=status, part_number=part, name=name)
        for status, part, name in [
            ("missing_in_duro", "435-12345", "P50 O-ring 435-12345"),
            ("quantity_mismatch", "999-54321", "P50 O-ring"),
            ("missing_in_duro", "435-12346", "P50 -------- 435-12346"),
            ("missing_in_duro", "435-12347", "P50 Screw"),
            ("extra_in_duro", "435-12348", "P50 O-ring"),
        ]
    ]
    report = WorkflowBomReport(sop_material_count=4, duro_material_count=2, differences=differences)
    result = service._apply_ignored_differences(workflow, report)
    assert {item.part_number for item in result.ignored_items} == {"435-12345", "999-54321"}
    assert {item.ignore_value for item in result.ignored_items} == {"P50 + O-ring"}
    assert {item.ignore_reason for item in result.ignored_items} == {"不核对密封圈"}
    assert result.missing_in_duro_count == 2
    assert result.quantity_mismatch_count == 0
    assert result.extra_in_duro_count == 1
    assert result.sop_material_count == 2
    assert result.duro_material_count == 2
    for mapping in ({}, {"P50": []}):
        workflow.configuration["ignored_sop_product_material_names"] = mapping
        assert not service._apply_ignored_differences(workflow, report).ignored_items
    del workflow.configuration["ignored_sop_product_material_names"]
    assert not service._apply_ignored_differences(workflow, report).ignored_items


def test_database_ignore_rule_marks_history_detail_and_future_report(tmp_path: Path) -> None:
    repository = WorkflowRepository(tmp_path / "workflows.sqlite3")
    service = WorkflowService(repository)
    workflow = repository.save_workflow(Workflow(name="独立忽略库", kind="duro_bom_check"))
    run = repository.save_run(
        WorkflowRun(
            workflow_id=workflow.id,
            workflow_name=workflow.name,
            trigger_type="manual",
            status="succeeded",
            report=WorkflowBomReport(
                sop_material_count=1,
                duro_material_count=1,
                differences=[
                    WorkflowBomDifference(
                        status="extra_in_duro",
                        part_number="438-00147",
                        name="Screw",
                        duro_quantity=4,
                    )
                ]
            ),
        )
    )

    rule = service.save_ignored_part_rule(workflow.id, "438-00147", "测试阶段不参与核对")
    detail = service.get_run_detail(run.id).run
    stored_workflow = service.get_workflow(workflow.id)

    assert detail.report is not None
    assert stored_workflow.configuration["ignored_part_numbers"] == ["438-00147"]
    assert stored_workflow.configuration["ignored_part_number_reasons"] == {
        "438-00147": "测试阶段不参与核对"
    }
    assert detail.report.differences[0].is_ignored is True
    assert detail.report.differences[0].active_ignore_reason == "测试阶段不参与核对"
    assert detail.report.differences[0].active_ignored_at == rule.ignored_at

    updated_report = service._apply_ignored_differences(
        workflow,
        WorkflowBomReport(
            duro_material_count=1,
            differences=[
                WorkflowBomDifference(
                    status="extra_in_duro",
                    part_number="438-00147",
                    name="Screw",
                    duro_quantity=4,
                )
            ],
        ),
    )

    assert updated_report.differences == []
    assert updated_report.total_ignored_count == 1
    assert updated_report.ignored_items[0].ignore_reason == "测试阶段不参与核对"
    assert updated_report.ignored_items[0].ignored_at == rule.ignored_at

    assert service.delete_ignored_part_rule(workflow.id, "438-00147") is True
    assert service.list_ignored_part_rules(workflow.id) == []
    assert service.get_workflow(workflow.id).configuration["ignored_part_numbers"] == []


def test_workflow_configuration_and_persisted_ignore_rules_stay_synchronized(tmp_path: Path) -> None:
    repository = WorkflowRepository(tmp_path / "workflows.sqlite3")
    workflow = repository.save_workflow(
        Workflow(
            name="同步忽略规则",
            kind="duro_bom_check",
            configuration={
                "ignored_part_numbers": ["100-00001"],
                "ignored_part_number_reasons": {"100-00001": "历史配置"},
            },
        )
    )
    service = WorkflowService(repository)

    loaded = service.get_workflow(workflow.id)

    assert loaded.configuration["ignored_part_numbers"] == ["100-00001"]
    assert [(rule.part_number, rule.reason) for rule in service.list_ignored_part_rules(workflow.id)] == [
        ("100-00001", "历史配置")
    ]

    updated_configuration = dict(loaded.configuration)
    updated_configuration["ignored_part_numbers"] = ["100-00002"]
    updated_configuration["ignored_part_number_reasons"] = {"100-00002": "编辑后配置"}
    service.update_workflow(
        workflow.id,
        WorkflowUpdate(configuration=updated_configuration),
    )

    assert [(rule.part_number, rule.reason) for rule in service.list_ignored_part_rules(workflow.id)] == [
        ("100-00002", "编辑后配置")
    ]


class FakeSopService:
    def get_master_sheet(self, refresh: bool = False):
        assert refresh is True
        return SimpleNamespace(
            cached=False,
            entries=[
                SimpleNamespace(
                    row_number=2,
                    project="Robot",
                    process="Assembly A",
                    issue_date="2026-01-01",
                    link_url="https://drive.google.com/file/d/sop-a/view",
                    drive_file_id="sop-a",
                ),
                SimpleNamespace(
                    row_number=3,
                    project="Robot",
                    process="Assembly B",
                    issue_date="2026-01-01",
                    link_url="https://drive.google.com/file/d/sop-b/view",
                    drive_file_id="sop-b",
                ),
            ],
        )

    def analyze_pdf(self, file_id: str, refresh: bool = False, excluded_part_numbers=None):
        assert refresh is True
        materials = {
            "sop-a": [
                SimpleNamespace(part_number="100-00001", name="Bolt", occurrences=2, pages=[1]),
                SimpleNamespace(part_number="100-00002", name="Washer", occurrences=1, pages=[2]),
                SimpleNamespace(part_number="100-00003", name="Grease", occurrences=1, pages=[3]),
            ],
            "sop-b": [
                SimpleNamespace(part_number="100-00001", name="Bolt", occurrences=3, pages=[4]),
                SimpleNamespace(part_number="100-00005", name="P50 Clip", occurrences=4, pages=[5]),
            ],
        }
        return SimpleNamespace(full_text_references=materials[file_id])


class BomSelectionSopService:
    def analyze_pdf(self, file_id: str, refresh: bool = False, excluded_part_numbers=None):
        assert file_id == "sop-packaging"
        assert refresh is True
        return SimpleNamespace(
            cached=False,
            full_text_references=[
                SimpleNamespace(
                    part_number="100-00001",
                    name="正文物料",
                    quantity=2,
                    occurrences=2,
                    pages=[1],
                    source_lines=["Install 2×100-00001"],
                ),
                SimpleNamespace(
                    part_number="920-00084",
                    name="Motor cable",
                    quantity=1,
                    occurrences=1,
                    pages=[62],
                    source_lines=["920-00084"],
                ),
            ],
            bom_materials=[
                SimpleNamespace(
                    part_number="100-00001",
                    name="BOM 物料",
                    quantity=8,
                    quantity_complete=True,
                    occurrences=1,
                    pages=[3],
                    source_lines=["100-00001 8"],
                )
            ],
        )


class FakeDuroService:
    def list_products(self, refresh: bool = False):
        assert refresh is True
        return SimpleNamespace(
            cached=False,
            products=[
                SimpleNamespace(
                    id="duro-product",
                    name="Product",
                    cpn="999-00001",
                    revision="A1",
                )
            ],
        )

    def get_product_bom(self, product_id: str, refresh: bool = False):
        assert refresh is True
        assert product_id == "duro-product"
        return SimpleNamespace(
            root=DuroBomNode(
                id="root",
                node_type="product",
                name="Product",
                cpn="999-00001",
                children=[
                    DuroBomNode(id="assembly", name="Scan Menu", cpn="930-00004", quantity=1, has_children=True),
                ],
            )
        )

    def get_component_children(self, component_id: str, refresh: bool = False):
        assert refresh is True
        children = {
            "assembly": [
                DuroBomNode(id="bolt", name="Bolt", cpn="100-00001", quantity=5),
                DuroBomNode(id="nested", name="Nested Assembly", cpn="200-00001", quantity=2, has_children=True),
                DuroBomNode(id="grease", name="Grease", cpn="100-00003", quantity=1),
            ],
            "nested": [
                DuroBomNode(id="washer", name="Washer", cpn="100-00002", quantity=1),
                DuroBomNode(id="extra", name="Extra", cpn="100-00004", quantity=1),
            ],
        }
        return SimpleNamespace(children=children[component_id])


class FakeSuppliesService:
    def list(self):
        return [SimpleNamespace(material_number="100-00004")]


class BlockingProductDuroService(FakeDuroService):
    def __init__(self, started: Event, release: Event) -> None:
        self.started = started
        self.release = release

    def list_products(self, refresh: bool = False):
        self.started.set()
        if not self.release.wait(timeout=2):
            raise RuntimeError("test release timeout")
        return super().list_products(refresh)


class EmptySopService:
    def get_master_sheet(self, refresh: bool = False):
        assert refresh is True
        return SimpleNamespace(
            cached=False,
            entries=[
                SimpleNamespace(
                    row_number=2,
                    project="Robot",
                    process="Assembly",
                    issue_date="2026-01-01",
                    link_url="https://drive.google.com/file/d/sop-empty/view",
                    drive_file_id="sop-empty",
                )
            ],
        )

    def analyze_pdf(self, file_id: str, refresh: bool = False, excluded_part_numbers=None):
        assert refresh is True
        return SimpleNamespace(full_text_references=[])


def test_workflow_adds_quantity_explanation_when_semantic_details_are_missing(tmp_path: Path) -> None:
    service = WorkflowService(
        WorkflowRepository(tmp_path / "workflows.sqlite3"),
        sop_service=FakeSopService(),  # type: ignore[arg-type]
    )

    materials = service._collect_sop_references(
        [{"drive_file_id": "sop-a", "project": "Robot", "process": "Assembly"}]
    )

    assert materials["100-00001"]["quantity_explanations"] == [
        "Robot / Assembly：大模型未返回该料号的完整语义累加明细，"
        "当前采用 SOP 正文规则统计数量 2"
    ]
    assert materials["100-00001"]["occurrence_count"] == 2


def test_selected_sop_process_uses_bom_material_summary(tmp_path: Path) -> None:
    service = WorkflowService(
        WorkflowRepository(tmp_path / "workflows.sqlite3"),
        sop_service=BomSelectionSopService(),  # type: ignore[arg-type]
    )

    materials = service._collect_sop_references(
        [{"drive_file_id": "sop-packaging", "project": "Robot", "process": "Packaging"}],
        {"packaging"},
    )

    assert materials["100-00001"]["quantity"] == 8
    assert materials["100-00001"]["quantity_known"] is True
    assert materials["100-00001"]["occurrence_count"] == 1
    assert materials["100-00001"]["quantity_explanations"] == [
        "Robot / Packaging：使用 SOP BOM 物料汇总结果"
    ]
    assert materials["920-00084"]["quantity"] == 1
    assert materials["920-00084"]["quantity_explanations"] == [
        "Robot / Packaging：使用 SOP 上下文引用（非物料清单页）"
    ]


def test_workflow_maps_every_sop_occurrence_to_a_delta_step(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    material = SimpleNamespace(
        occurrence_details=[
            SimpleNamespace(page_number=14, evidence="固定 1 个压块 415-01005 到 plunger"),
            SimpleNamespace(page_number=15, evidence="检查压块 415-01005 是否固定"),
        ],
        source_lines=[],
        pages=[14, 15],
        quantity_decisions=[
            SimpleNamespace(
                page_numbers=[14],
                evidence="固定 1 个压块 415-01005 到 plunger",
                quantity_delta=1,
                accumulate=True,
                action="固定",
                reason="新增一个压块",
            )
        ],
    )

    steps = service._build_sop_occurrence_steps("Gen3 96ch / Assembly", material)

    assert [(step.page_number, step.quantity_delta) for step in steps] == [(14, 1), (15, 0)]
    assert steps[0].evidence == "固定 1 个压块 415-01005 到 plunger"
    assert steps[1].reason == "该正文出现未被判定为新增装配，计入 +0"


def test_workflow_refines_only_preexisting_quantity_mismatches(tmp_path: Path) -> None:
    class RefiningSopService:
        def __init__(self) -> None:
            self.calls: list[set[str]] = []

        def refine_semantic_quantities_with_names(self, file_id, material_names, targets):
            assert file_id == "sop-a"
            self.calls.append(set(targets))
            return [
                SimpleNamespace(
                    part_number="100-00001",
                    name="扎带/zip-tie",
                    quantity=5,
                    occurrences=3,
                    pages=[1, 2],
                    source_lines=["1×100-00001", "Use four zip-tie"],
                    occurrence_details=[
                        SimpleNamespace(page_number=1, evidence="Install 1×100-00001"),
                        SimpleNamespace(page_number=2, evidence="Use four zip-tie"),
                    ],
                    quantity_explanation="数量差异二次复核后为 5",
                    quantity_decisions=[],
                )
            ]

    sop_service = RefiningSopService()
    service = WorkflowService(
        WorkflowRepository(tmp_path / "workflows.sqlite3"),
        sop_service=sop_service,  # type: ignore[arg-type]
    )
    materials = {
        "100-00001": {
            "name": "扎带/zip-tie",
            "quantity": 1.0,
            "quantity_known": True,
            "occurrence_count": 1,
            "occurrence_steps": [],
            "locations": ["Robot / Assembly：第 1 页"],
            "quantity_explanations": ["Robot / Assembly：第一阶段数量为 1"],
            "quantity_decisions": [],
            "source_quantities": {"sop-a": 1.0},
            "source_occurrence_counts": {"sop-a": 1},
            "source_labels": {"sop-a": "Robot / Assembly"},
        },
        "100-00002": {
            "name": "Matched part",
            "quantity": 2.0,
            "quantity_known": True,
            "occurrence_count": 1,
            "occurrence_steps": [],
            "locations": ["Robot / Assembly：第 3 页"],
            "quantity_explanations": ["Robot / Assembly：第一阶段数量为 2"],
            "quantity_decisions": [],
            "source_quantities": {"sop-a": 2.0},
            "source_occurrence_counts": {"sop-a": 1},
            "source_labels": {"sop-a": "Robot / Assembly"},
        },
    }

    updated = service._refine_sop_quantity_mismatches(
        [{"drive_file_id": "sop-a", "project": "Robot", "process": "Assembly"}],
        materials,
        {"100-00001"},
    )

    assert sop_service.calls == [{"100-00001"}]
    assert updated == 1
    assert materials["100-00001"]["quantity"] == 5
    assert materials["100-00001"]["occurrence_count"] == 3
    assert materials["100-00002"]["quantity"] == 2
    assert materials["100-00002"]["quantity_explanations"] == [
        "Robot / Assembly：第一阶段数量为 2"
    ]


def test_workflow_refinement_batches_and_continues_after_batch_failure(tmp_path: Path, monkeypatch) -> None:
    class PartiallyFailingSopService:
        def __init__(self) -> None:
            self.calls: list[set[str]] = []

        def refine_semantic_quantities_for_targets(self, file_id, material_names, targets):
            assert file_id == "sop-a"
            batch = set(targets)
            self.calls.append(batch)
            if "100-00001" in batch:
                raise RuntimeError("Server disconnected without sending a response.")
            return [
                SimpleNamespace(
                    part_number=part_number,
                    name=f"复核物料 {part_number}",
                    quantity=9,
                    occurrences=1,
                    pages=[2],
                    source_lines=[f"安装 {part_number}"],
                    occurrence_details=[
                        SimpleNamespace(page_number=2, evidence=f"安装 {part_number}")
                    ],
                    quantity_explanation="批量二次复核成功",
                    quantity_decisions=[],
                )
                for part_number in sorted(batch)
            ]

    monkeypatch.setattr("modules.workflows.service.WORKFLOW_REFINE_BATCH_SIZE", 2)
    sop_service = PartiallyFailingSopService()
    service = WorkflowService(
        WorkflowRepository(tmp_path / "workflows.sqlite3"),
        sop_service=sop_service,  # type: ignore[arg-type]
    )
    materials = {
        part_number: {
            "name": f"物料 {part_number}",
            "quantity": 1.0,
            "quantity_known": True,
            "occurrence_count": 1,
            "occurrence_steps": [],
            "locations": [f"Robot / Assembly：第 {index} 页"],
            "quantity_explanations": [f"Robot / Assembly：第一阶段数量为 1"],
            "quantity_decisions": [],
            "source_quantities": {"sop-a": 1.0},
            "source_occurrence_counts": {"sop-a": 1},
            "source_labels": {"sop-a": "Robot / Assembly"},
        }
        for index, part_number in enumerate(
            ["100-00001", "100-00002", "100-00003", "100-00004", "100-00005"],
            start=1,
        )
    }

    updated = service._refine_sop_quantity_mismatches(
        [{"drive_file_id": "sop-a", "project": "Robot", "process": "Assembly"}],
        materials,
        set(materials),
    )

    assert sop_service.calls == [
        {"100-00001", "100-00002"},
        {"100-00003", "100-00004"},
        {"100-00005"},
    ]
    assert updated == 3
    assert materials["100-00001"]["quantity"] == 1
    assert materials["100-00003"]["quantity"] == 9
    assert materials["100-00005"]["quantity_explanations"] == [
        "Robot / Assembly：批量二次复核成功"
    ]


class CleanupMatchSopService:
    def get_master_sheet(self, refresh: bool = False):
        assert refresh is True
        return SimpleNamespace(
            cached=False,
            entries=[
                SimpleNamespace(
                    row_number=2,
                    project="Robot",
                    process="Assembly",
                    issue_date="2026-01-01",
                    link_url="https://drive.google.com/file/d/sop-cleanup/view",
                    drive_file_id="sop-cleanup",
                )
            ],
        )

    def analyze_pdf(self, file_id: str, refresh: bool = False, excluded_part_numbers=None):
        assert refresh is True
        return SimpleNamespace(
            full_text_references=[
                SimpleNamespace(
                    part_number="415-000656",
                    name="清洗后匹配物料",
                    occurrences=1,
                    quantity=1,
                    pages=[8],
                    quantity_explanation="正文语义判断为装入 1 个",
                    quantity_decisions=[],
                )
            ]
        )


class CleanupMatchDuroService:
    def list_products(self, refresh: bool = False):
        assert refresh is True
        return SimpleNamespace(
            cached=False,
            products=[
                SimpleNamespace(
                    id="duro-product",
                    name="Product",
                    cpn="999-00001",
                    revision="A1",
                )
            ],
        )

    def get_product_bom(self, product_id: str, refresh: bool = False):
        assert refresh is True
        return SimpleNamespace(
            root=DuroBomNode(
                id="root",
                node_type="product",
                name="Product",
                cpn="999-00001",
                children=[
                    DuroBomNode(
                        id="assembly",
                        name="Scan Menu",
                        cpn="930-00004",
                        quantity=1,
                        has_children=True,
                    ),
                ],
            )
        )

    def get_component_children(self, component_id: str, refresh: bool = False):
        assert refresh is True
        assert component_id == "assembly"
        return SimpleNamespace(
            children=[
                DuroBomNode(
                    id="cleaned-part",
                    name="清洗后匹配物料",
                    cpn="415-00656",
                    quantity=1,
                )
            ]
        )


class RefreshedSourceSopService(CleanupMatchSopService):
    def get_master_sheet(self, refresh: bool = False):
        assert refresh is True
        return SimpleNamespace(
            cached=False,
            entries=[
                SimpleNamespace(
                    row_number=2,
                    project="Robot",
                    process="Assembly",
                    issue_date="2026-07-30",
                    link_url="https://drive.google.com/file/d/sop-current/view",
                    drive_file_id="sop-current",
                )
            ],
        )

    def analyze_pdf(self, file_id: str, refresh: bool = False, excluded_part_numbers=None):
        assert file_id == "sop-current"
        return super().analyze_pdf(file_id, refresh)


class RefreshedProductDuroService(CleanupMatchDuroService):
    def list_products(self, refresh: bool = False):
        assert refresh is True
        return SimpleNamespace(
            cached=False,
            products=[
                SimpleNamespace(
                    id="duro-current",
                    name="Product",
                    cpn="999-00001",
                    revision="A1",
                )
            ],
        )

    def get_product_bom(self, product_id: str, refresh: bool = False):
        assert product_id == "duro-current"
        return super().get_product_bom(product_id, refresh)


def test_manual_duro_run_generates_bom_difference_report(tmp_path: Path) -> None:
    service = WorkflowService(
        WorkflowRepository(tmp_path / "workflows.sqlite3"),
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
                "duro_submenu_ids": ["assembly"],
                "duro_submenus": [{"id": "assembly", "label": "930-00004"}],
                "ignored_sop_product_keywords": ["P50"],
                "ignored_sop_product_material_names": {"P50": ["Clip"]},
                "ignored_part_numbers": [" 100-00004 ", "100-00004", "100-00002"],
                "ignored_sop_product_keyword_reasons": {"P50": "该产品不参与当前核对"},
                "ignored_part_number_reasons": {
                    "100-00004": "测试用辅料",
                    "100-00002": "该料号数量不参与核对",
                },
                "ignore_quantity_mismatch_warning": True,
                "check_parent_bom": True,
                "check_supplies": True,
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
    assert current.report.sop_material_count == 2
    assert current.report.matched_count == 2
    assert current.report.duro_material_count == 3
    assert current.report.missing_in_duro_count == 0
    assert current.report.extra_in_duro_count == 1
    assert current.report.quantity_mismatch_count == 0
    assert current.report.quantity_unknown_count == 0
    assert current.report.warning_difference_count == 1
    assert len(current.report.differences) == 1
    assert all(item.part_number != "100-00004" for item in current.report.differences)
    assert current.report.total_ignored_count == 3
    assert {item.status for item in current.report.ignored_items} == {
        "missing_in_duro",
        "extra_in_duro",
        "quantity_mismatch",
    }
    assert {item.ignore_reason for item in current.report.ignored_items} == {
        "该产品不参与当前核对",
        "测试用辅料",
        "该料号数量不参与核对",
    }
    assert all(item.part_number != "100-00002" for item in current.report.differences)
    assert all(item.part_number != "100-00005" for item in current.report.differences)
    assert all(item.part_number != "930-00004" for item in current.report.differences)
    assert all(item.part_number != "999-00001" for item in current.report.differences)
    assert current.report.duro_submenus == [
        {"id": "assembly", "label": "930-00004", "name": "Scan Menu"}
    ]
    assert all(
        item.duro_submenu_ids == ["assembly"]
        for item in current.report.differences
        if item.status != "missing_in_duro"
    )


def test_default_duro_run_ignores_parent_bom_materials_and_audits_them(tmp_path: Path) -> None:
    service = WorkflowService(
        WorkflowRepository(tmp_path / "workflows.sqlite3"),
        sop_service=FakeSopService(),  # type: ignore[arg-type]
        duro_service=FakeDuroService(),  # type: ignore[arg-type]
        supplies_service=FakeSuppliesService(),  # type: ignore[arg-type]
    )
    workflow = service.create_workflow(
        WorkflowCreate(
            name="默认叶子 BOM 核对",
            kind="duro_bom_check",
            configuration={
                "sop_sources": [
                    {"drive_file_id": "sop-a", "project": "Robot", "process": "Assembly A"}
                ],
                "duro_product_id": "duro-product",
                "duro_submenu_ids": ["assembly"],
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
    assert workflow.configuration["check_parent_bom"] is False
    assert current.report.duro_material_count == 3
    assert {item.part_number for item in current.report.differences} == {
        "100-00001",
        "100-00002",
    }
    supply_items = [
        item for item in current.report.ignored_items if item.ignore_type == "supply"
    ]
    assert len(supply_items) == 1
    assert supply_items[0].part_number == "100-00004"
    assert supply_items[0].status == "extra_in_duro"
    assert supply_items[0].ignore_reason == "命中辅料"
    parent_items = [
        item for item in current.report.ignored_items if item.ignore_type == "parent_bom"
    ]
    assert len(parent_items) == 1
    assert parent_items[0].part_number == "200-00001"
    assert parent_items[0].status == "parent_bom_ignored"
    assert "未勾选“核对父菜单 BOM”" in parent_items[0].ignore_reason


def test_default_part_number_cleanup_is_compared_and_audited(tmp_path: Path) -> None:
    service = WorkflowService(WorkflowRepository(tmp_path / "workflows.sqlite3"))
    materials = {
        "415-000656": {
            "name": "清洗测试物料",
            "quantity": 2.0,
            "quantity_known": True,
            "locations": ["SOP：第 1 页"],
        },
        "920-000131": {
            "name": "第二个清洗测试物料",
            "quantity": 1.0,
            "quantity_known": True,
            "locations": ["SOP：第 2 页"],
        },
    }

    ignored = service._normalize_material_part_numbers(materials, "sop")

    assert set(materials) == {"415-00656", "920-00131"}
    assert {item.part_number for item in ignored} == {"415-000656", "920-000131"}
    assert {item.normalized_part_number for item in ignored} == {"415-00656", "920-00131"}
    assert all(item.ignore_type == "part_number_cleanup" for item in ignored)


def test_cleanup_match_without_difference_is_kept_in_run_ignored_items(tmp_path: Path) -> None:
    service = WorkflowService(
        WorkflowRepository(tmp_path / "workflows.sqlite3"),
        sop_service=CleanupMatchSopService(),  # type: ignore[arg-type]
        duro_service=CleanupMatchDuroService(),  # type: ignore[arg-type]
    )
    workflow = service.create_workflow(
        WorkflowCreate(
            name="清洗后无差异核对",
            kind="duro_bom_check",
            configuration={
                "sop_sources": [
                    {"drive_file_id": "sop-cleanup", "project": "Robot", "process": "Assembly"},
                ],
                "duro_product_id": "duro-product",
                "duro_submenu_ids": ["assembly"],
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
    assert current.report.matched_count == 1
    assert current.report.differences == []
    assert current.report.total_ignored_count == 1
    cleanup = current.report.ignored_items[0]
    assert cleanup.ignore_type == "part_number_cleanup"
    assert cleanup.part_number == "415-000656"
    assert cleanup.normalized_part_number == "415-00656"
    assert cleanup.ignore_reason == "默认料号清洗：415-000656 → 415-00656"


def test_run_refreshes_source_tables_and_uses_current_sop_link_and_duro_product(tmp_path: Path) -> None:
    service = WorkflowService(
        WorkflowRepository(tmp_path / "workflows.sqlite3"),
        sop_service=RefreshedSourceSopService(),  # type: ignore[arg-type]
        duro_service=RefreshedProductDuroService(),  # type: ignore[arg-type]
    )
    workflow = service.create_workflow(
        WorkflowCreate(
            name="实时数据源核对",
            kind="duro_bom_check",
            configuration={
                "sop_sources": [
                    {
                        "drive_file_id": "sop-stale",
                        "project": "Robot",
                        "process": "Assembly",
                        "issue_date": "2026-01-01",
                        "row_number": 2,
                    },
                ],
                "duro_product_id": "duro-stale",
                "duro_product_name": "Product",
                "duro_product_cpn": "999-00001",
                "duro_product_revision": "A1",
                "duro_submenu_ids": ["assembly"],
            },
        )
    )

    run = service.trigger_workflow(workflow.id, "manual")
    deadline = time.monotonic() + 2
    current = run
    while current.status in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(0.01)
        current = service.list_runs(workflow_id=workflow.id, limit=1)[0]

    stored = service.get_workflow(workflow.id)
    assert current.status == "succeeded"
    assert stored.configuration["sop_drive_file_ids"] == ["sop-current"]
    assert stored.configuration["sop_sources"][0]["link_url"].endswith("/sop-current/view")
    assert stored.configuration["duro_product_id"] == "duro-current"
    assert any("更新 1 个源 PDF 链接" in message for message in current.logs)
    assert any("目标产品 ID 已更新" in message for message in current.logs)


def test_workflow_persists_progress_before_next_source_refresh_finishes(tmp_path: Path) -> None:
    refresh_started = Event()
    release_refresh = Event()
    service = WorkflowService(
        WorkflowRepository(tmp_path / "workflows.sqlite3"),
        sop_service=FakeSopService(),  # type: ignore[arg-type]
        duro_service=BlockingProductDuroService(  # type: ignore[arg-type]
            refresh_started,
            release_refresh,
        ),
    )
    workflow = service.create_workflow(
        WorkflowCreate(
            name="实时执行日志",
            kind="duro_bom_check",
            configuration={
                "sop_sources": [
                    {"drive_file_id": "sop-a", "project": "Robot", "process": "Assembly A"},
                ],
                "duro_product_id": "duro-product",
                "duro_submenu_ids": ["assembly"],
            },
        )
    )

    run = service.trigger_workflow(workflow.id, "manual")
    try:
        assert refresh_started.wait(timeout=2)
        current = service.get_run(run.id)
        assert any("SOP 总表实时刷新完成" in message for message in current.logs)
        assert not any("Duro 产品表实时刷新完成" in message for message in current.logs)
    finally:
        release_refresh.set()

    deadline = time.monotonic() + 2
    current = service.get_run(run.id)
    while current.status in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(0.01)
        current = service.get_run(run.id)
    assert current.status == "succeeded"


def test_manual_duro_run_rejects_sop_without_full_text_references(tmp_path: Path) -> None:
    service = WorkflowService(
        WorkflowRepository(tmp_path / "workflows.sqlite3"),
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
                "duro_submenu_ids": ["assembly"],
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


class AutoSelectionDuroService(FakeDuroService):
    def __init__(self) -> None:
        self.component_calls: list[str] = []
        self.submenus = [
            DuroBomNode(id='assembly', name='Mechanical assembly', cpn='930-00004', quantity=1, has_children=True),
            DuroBomNode(id='packaging', name='Shipping', description='Product PACKAGING', cpn='930-00005', quantity=1, has_children=True),
            DuroBomNode(id='software', name='Robot Software', cpn='930-00006', quantity=1, has_children=True),
            DuroBomNode(id='touchpoints', name='Version menu', description='firmware touchpoints', cpn='930-00007', quantity=1, has_children=True),
        ]
        self.children = {
            'assembly': [
                DuroBomNode(id='bolt', name='Bolt', cpn='100-00001', quantity=5),
                DuroBomNode(id='nested', name='Nested Assembly', cpn='200-00001', quantity=2, has_children=True),
                DuroBomNode(id='nested-software', name='Nested Version Menu', description='SOFTWARE', cpn='200-00002', quantity=1, has_children=True),
            ],
            'nested': [DuroBomNode(id='washer', name='Washer', cpn='100-00002', quantity=3)],
            'nested-software': [DuroBomNode(id='nested-script', name='Script', cpn='710-00001', quantity=1)],
            'packaging': [DuroBomNode(id='box', name='Box', cpn='900-00001', quantity=1)],
            'software': [DuroBomNode(id='same-bolt', name='Bolt', cpn='100-00001', quantity=100)],
            'touchpoints': [DuroBomNode(id='script', name='Script', cpn='710-00002', quantity=1)],
        }

    def get_product_bom(self, product_id: str, refresh: bool = False):
        assert refresh is True
        return SimpleNamespace(root=DuroBomNode(id='root', name='Product', children=self.submenus))

    def get_component_children(self, component_id: str, refresh: bool = False):
        assert refresh is True
        self.component_calls.append(component_id)
        return SimpleNamespace(children=self.children[component_id])


@pytest.mark.parametrize(('name', 'description'), [
    ('Robot PACKAGING', ''), ('Unrelated name', 'Robot packaging'),
    ('Robot SOFTWARE', ''), ('Unrelated name', 'Software firmware'),
    ('TOUCHPOINTS', ''), ('Unrelated name', 'Firmware Touchpoints'),
    ('ＰＡＣＫＡＧＩＮＧ', ''),
])
def test_auto_submenu_exclusions_match_any_keyword_in_name_or_description(name, description) -> None:
    assert WorkflowService._duro_node_matches_auto_exclusions(
        DuroBomNode(id='node', name=name, description=description), ['PACKAGING', 'SOFTWARE', 'TOUCHPOINTS'],
    )


def test_auto_submenu_configuration_persists_custom_and_empty_keywords(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    workflow = service.create_workflow(WorkflowCreate(name='Auto', kind='duro_bom_check', configuration={
        'duro_submenu_ids': ['manual-choice'], 'duro_auto_select_submenus': True,
        'duro_auto_excluded_keywords': [' packaging ', 'PACKAGING', 'custom assembly', '', None],
    }))
    stored = service.get_workflow(workflow.id)
    assert stored.configuration['duro_auto_select_submenus'] is True
    assert stored.configuration['duro_auto_excluded_keywords'] == ['PACKAGING', 'CUSTOM ASSEMBLY']
    assert stored.configuration['duro_submenu_ids'] == ['manual-choice']
    configuration = dict(stored.configuration, duro_auto_excluded_keywords=[], duro_auto_select_submenus=False)
    service.update_workflow(workflow.id, WorkflowUpdate(configuration=configuration))
    stored = service.get_workflow(workflow.id)
    assert stored.configuration['duro_auto_select_submenus'] is False
    assert stored.configuration['duro_auto_excluded_keywords'] == []
    assert stored.configuration['duro_submenu_ids'] == ['manual-choice']


@pytest.mark.parametrize('include_parent_bom', [False, True])
def test_auto_submenus_prune_excluded_parents_and_whole_subtrees(tmp_path: Path, include_parent_bom: bool) -> None:
    duro = AutoSelectionDuroService()
    service = WorkflowService(WorkflowRepository(tmp_path / 'workflows.sqlite3'), duro_service=duro)
    materials, submenus, ignored = service._collect_duro_materials(
        'duro-product', {'stale-manual-id'}, include_parent_bom=include_parent_bom,
        auto_excluded_keywords=['PACKAGING', 'SOFTWARE', 'TOUCHPOINTS'],
    )
    assert [item['id'] for item in submenus] == ['assembly']
    assert set(materials) == ({'100-00001', '100-00002', '200-00001'} if include_parent_bom else {'100-00001', '100-00002'})
    assert materials['100-00001']['quantity'] == 5  # Shared part in an excluded branch contributes nothing.
    assert materials['100-00002']['quantity'] == 6
    assert set(duro.component_calls) == {'assembly', 'nested'}
    assert {item.part_number for item in ignored} == (set() if include_parent_bom else {'200-00001'})


@pytest.mark.parametrize('keywords', [[], ['CUSTOM'], ['nested assembly']])
def test_auto_submenu_custom_keywords_and_empty_list(tmp_path: Path, keywords: list[str]) -> None:
    duro = AutoSelectionDuroService()
    service = WorkflowService(WorkflowRepository(tmp_path / 'workflows.sqlite3'), duro_service=duro)
    materials, submenus, _ = service._collect_duro_materials('duro-product', set(), auto_excluded_keywords=keywords)
    assert len(submenus) == 4
    assert '900-00001' in materials
    assert '710-00001' in materials
    assert '710-00002' in materials
    assert materials['100-00001']['quantity'] == 105
    assert ('100-00002' in materials) is (keywords != ['nested assembly'])


def test_manual_submenus_remain_unfiltered_by_auto_rules(tmp_path: Path) -> None:
    duro = AutoSelectionDuroService()
    service = WorkflowService(WorkflowRepository(tmp_path / 'workflows.sqlite3'), duro_service=duro)
    materials, submenus, _ = service._collect_duro_materials('duro-product', {'assembly', 'packaging'})
    assert {item['id'] for item in submenus} == {'assembly', 'packaging'}
    assert '900-00001' in materials
    assert '710-00001' in materials
    assert 'software' not in duro.component_calls


def test_auto_submenu_all_excluded_does_not_fall_back_to_manual_selection(tmp_path: Path) -> None:
    duro = AutoSelectionDuroService()
    service = WorkflowService(WorkflowRepository(tmp_path / 'workflows.sqlite3'), duro_service=duro)
    with pytest.raises(RuntimeError, match='自动选择未找到可核对的子项目'):
        service._collect_duro_materials('duro-product', {'assembly'}, auto_excluded_keywords=['assembly', 'shipping', 'software', 'version'])
    assert not duro.component_calls


@pytest.mark.parametrize('manual_ids', [[], ['deleted-submenu']])
def test_auto_workflow_run_uses_fresh_submenus_without_requiring_manual_selection(tmp_path: Path, manual_ids) -> None:
    duro = AutoSelectionDuroService()
    service = WorkflowService(
        WorkflowRepository(tmp_path / 'workflows.sqlite3'),
        sop_service=FakeSopService(), duro_service=duro,
    )
    workflow = service.create_workflow(WorkflowCreate(name='Auto', kind='duro_bom_check', configuration={
        'sop_sources': [{'drive_file_id': 'sop-a', 'project': 'Robot', 'process': 'Assembly A'}],
        'duro_product_id': 'duro-product', 'duro_submenu_ids': manual_ids, 'duro_auto_select_submenus': True,
    }))
    run = WorkflowRun(workflow_id=workflow.id, workflow_name=workflow.name, trigger_type='manual', status='queued')
    service._execute_run(workflow, run)
    assert run.status == 'succeeded', run.message
    assert run.report is not None
    assert [item['id'] for item in run.report.duro_submenus] == ['assembly']
    assert service.get_workflow(workflow.id).configuration['duro_submenu_ids'] == manual_ids
    assert any('自动选择子项目' in log for log in run.logs)


@pytest.mark.parametrize("auto", [False, True])
@pytest.mark.parametrize("zero", [0, "0", "0.0"])
def test_zero_quantity_subtrees_are_skipped_at_every_level(tmp_path: Path, auto: bool, zero) -> None:
    duro = AutoSelectionDuroService()
    duro.submenus = [duro.submenus[0], DuroBomNode(
        id="zero-root", name="Zero root", cpn="991-00001", quantity=zero, has_children=True,
    )]
    # No child data is provided for zero nodes: expansion would fail this test.
    duro.children["assembly"] = [
        DuroBomNode(id="zero-child", name="Zero child", cpn="991-00002", quantity=zero, has_children=True),
        DuroBomNode(id="zero-leaf", name="Zero leaf", cpn="100-00003", quantity=zero),
        DuroBomNode(id="active-parent", name="Active parent", cpn="991-00003", quantity=2, has_children=True),
        DuroBomNode(id="shared-active", name="Shared active", cpn="100-00001", quantity=3),
    ]
    duro.children["active-parent"] = [
        DuroBomNode(id="deep-zero", name="Deep zero", cpn="991-00004", quantity=zero, has_children=True),
        DuroBomNode(id="shared-zero", name="Shared zero", cpn="100-00001", quantity=zero),
        DuroBomNode(id="active-leaf", name="Active leaf", cpn="100-00002", quantity=4),
    ]
    service = WorkflowService(WorkflowRepository(tmp_path / "workflows.sqlite3"), duro_service=duro)
    materials, submenus, ignored = service._collect_duro_materials(
        "duro-product", {"assembly", "zero-root"}, auto_excluded_keywords=[] if auto else None,
    )
    assert [item["id"] for item in submenus] == ["assembly"]
    assert set(duro.component_calls) == {"assembly", "active-parent"}
    assert set(materials) == {"100-00001", "100-00002"}
    assert materials["100-00001"]["quantity"] == 3
    assert materials["100-00002"]["quantity"] == 8
    assert {item.part_number for item in ignored} == {"991-00003"}


@pytest.mark.parametrize(("parent_part", "quantity", "prefixes", "expected"), [
    ("991-00001", 0, ["991-"], True),
    ("991-00001", "0", ["991-"], True),
    ("991-00001", "0.0", ["991-"], True),
    ("991-00001", 1, ["991-"], False),
    ("991-00001", None, ["991-"], False),
    ("991-00001", "", ["991-"], False),
    ("991-00001", "unknown", ["991-"], False),
    ("992-00001", 0, ["991-"], False),
    ("1991-00001", 0, ["991-"], False),
    ("992-00001", 0, ["992-"], True),
    ("991-00001", 0, [], False),
    ("991-00001", 0, None, False),
])
def test_zero_quantity_rule_is_scoped_to_configured_parent_prefixes(parent_part, quantity, prefixes, expected) -> None:
    parent = DuroBomNode(id="parent", cpn=parent_part, has_children=True)
    child = DuroBomNode(id="child", cpn="100-00001", quantity=quantity)
    assert WorkflowService._duro_is_zero_quantity_child(parent, child, prefixes) is expected


def test_zero_quantity_parent_prefix_settings_persist_and_can_be_disabled(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    workflow = service.create_workflow(WorkflowCreate(name="Prefix rule", kind="duro_bom_check", configuration={
        "duro_auto_select_submenus": True,
        "duro_auto_zero_quantity_parent_prefixes": [" 991- ", "991-", "992-", "", None],
    }))
    stored = service.get_workflow(workflow.id)
    assert stored.configuration["duro_auto_zero_quantity_parent_prefixes"] == ["991-", "992-"]
    configuration = dict(stored.configuration, duro_auto_zero_quantity_parent_prefixes=[])
    service.update_workflow(workflow.id, WorkflowUpdate(configuration=configuration))
    assert service.get_workflow(workflow.id).configuration["duro_auto_zero_quantity_parent_prefixes"] == []


@pytest.mark.parametrize("include_parent_bom", [False, True])
def test_prefix_rule_keeps_nonzero_991_parents_and_checks_each_deeper_level(tmp_path: Path, include_parent_bom: bool) -> None:
    duro = AutoSelectionDuroService()
    duro.submenus = [DuroBomNode(id="root-991", name="Root assembly", cpn="991-00001", quantity=2, has_children=True)]
    duro.children = {
        "root-991": [
            DuroBomNode(id="zero-root-child", cpn="991-00002", quantity=0, has_children=True),
            DuroBomNode(id="next-991", cpn="991-00003", quantity=2, has_children=True),
            DuroBomNode(id="non-prefix-parent", cpn="930-00001", quantity=3, has_children=True),
            DuroBomNode(id="root-leaf", cpn="100-00001", quantity=5),
        ],
        "next-991": [
            DuroBomNode(id="zero-next-child", cpn="100-00005", quantity="0"),
            DuroBomNode(id="next-leaf", cpn="100-00002", quantity=4),
            DuroBomNode(id="third-991", cpn="991-00004", quantity=3, has_children=True),
        ],
        "third-991": [
            DuroBomNode(id="zero-third-child", cpn="991-00005", quantity="0.0", has_children=True),
            DuroBomNode(id="third-leaf", cpn="100-00003", quantity=5),
        ],
        "non-prefix-parent": [DuroBomNode(id="deep-991", cpn="991-00006", quantity=2, has_children=True)],
        "deep-991": [
            DuroBomNode(id="zero-deep-child", cpn="100-00006", quantity=0),
            DuroBomNode(id="deep-leaf", cpn="100-00004", quantity=7),
        ],
    }
    service = WorkflowService(WorkflowRepository(tmp_path / "workflows.sqlite3"), duro_service=duro)
    materials, submenus, ignored = service._collect_duro_materials(
        "duro-product", set(), include_parent_bom=include_parent_bom,
        auto_excluded_keywords=[], zero_quantity_parent_prefixes=["991-"],
    )
    assert [item["id"] for item in submenus] == ["root-991"]
    assert set(duro.component_calls) == {"root-991", "next-991", "third-991", "non-prefix-parent", "deep-991"}
    assert {part: materials[part]["quantity"] for part in ["100-00001", "100-00002", "100-00003", "100-00004"]} == {
        "100-00001": 10, "100-00002": 16, "100-00003": 60, "100-00004": 84,
    }
    parent_parts = {"991-00003", "991-00004", "991-00006", "930-00001"}
    assert set(materials) == ({"100-00001", "100-00002", "100-00003", "100-00004"} | (parent_parts if include_parent_bom else set()))
    assert {item.part_number for item in ignored} == (set() if include_parent_bom else parent_parts)
