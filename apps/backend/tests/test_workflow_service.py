from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace

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


def test_material_name_keyword_matching_normalizes_micro_symbol_case_and_spaces(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    assert service._material_name_matches_keywords("Flex Robot Pro", ["robot"])
    assert service._material_name_matches_keywords("FLEX ROBOT PRO", ["flex robot"])
    assert service._material_name_matches_keywords("200ul Plunger", ["200μl"])
    assert service._material_name_matches_keywords("200 µL O-ring", ["200ul"])
    assert service._material_name_matches_keywords("200 μl logo", ["200 uL"])
    assert service._material_name_matches_keywords("200容量 弹簧441-00067", ["200 容量 441-00067"])
    assert service._material_name_matches_keywords("200 容量密封圈 441-00067", ["200 容量 441-00067"])
    assert service._material_name_matches_keywords(
        "96装入压块,1000容量的弹簧441-00037,200容量弹簧441-00067",
        ["200 Volume"],
    )
    assert not service._material_name_matches_keywords("441-00067 弹簧 200容量", ["200 容量 441-00067"])
    assert not service._material_name_matches_keywords("Flex Robot Pro", ["heater"])


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

    def analyze_pdf(self, file_id: str, refresh: bool = False):
        assert refresh is True
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

    def analyze_pdf(self, file_id: str, refresh: bool = False):
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

    def analyze_pdf(self, file_id: str, refresh: bool = False):
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

    def analyze_pdf(self, file_id: str, refresh: bool = False):
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
                "ignored_sop_product_keywords": ["clip"],
                "ignored_part_numbers": [" 100-00004 ", "100-00004", "100-00002"],
                "ignored_sop_product_keyword_reasons": {"clip": "该产品不参与当前核对"},
                "ignored_part_number_reasons": {
                    "100-00004": "测试用辅料",
                    "100-00002": "该料号数量不参与核对",
                },
                "ignore_quantity_mismatch_warning": True,
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
