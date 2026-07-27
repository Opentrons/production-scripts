from __future__ import annotations

import threading
import unicodedata
from datetime import timedelta
from typing import Any

from duro.models import DuroBomNode
from duro.service import DuroService
from sop.service import SopService

from workflows.models import (
    Workflow,
    WorkflowBomDifference,
    WorkflowBomReport,
    WorkflowCreate,
    WorkflowRun,
    WorkflowStep,
    WorkflowTriggerType,
    WorkflowUpdate,
    utc_now,
)
from workflows.repository import WorkflowRepository


class WorkflowNotFoundError(KeyError):
    pass


def build_duro_bom_steps() -> list[WorkflowStep]:
    return [
        WorkflowStep(
            name="核对 Duro BOM",
            kind="bom_compare",
            description="汇总所选 SOP 的全文料号引用，并与 Duro BOM 核对料号和出现次数。",
        ),
        WorkflowStep(
            name="核对报告",
            kind="report",
            description="输出缺失料号、冗余料号、数量差异和无法比较项。",
        ),
    ]


def build_duro_bom_workflow() -> Workflow:
    return Workflow(
        name="Duro BOM 核对",
        description="从 Duro 拉取目标产品 BOM，执行结构和版本差异核对，并输出报告。",
        kind="duro_bom_check",
        status="draft",
        configuration={
            "sop_drive_file_ids": [],
            "sop_sources": [],
            "sop_drive_file_id": "",
            "sop_project": "",
            "sop_process": "",
            "sop_issue_date": "",
            "sop_link_url": "",
            "sop_row_number": None,
            "duro_product_id": "",
            "duro_product_name": "",
            "duro_product_cpn": "",
            "duro_product_revision": "",
            "target_revision": "",
            "duro_submenu_ids": [],
            "duro_submenus": [],
            "ignored_sop_product_keywords": [],
            "ignored_part_numbers": [],
        },
        steps=build_duro_bom_steps(),
    )


class WorkflowService:
    def __init__(
        self,
        repository: WorkflowRepository,
        sop_service: SopService | None = None,
        duro_service: DuroService | None = None,
    ) -> None:
        self.repository = repository
        self.sop_service = sop_service
        self.duro_service = duro_service
        self._initialized = False
        self._initialize_lock = threading.Lock()

    def initialize(self) -> None:
        with self._initialize_lock:
            if self._initialized:
                return
            workflows = self.repository.list_workflows()
            if not workflows:
                self.repository.save_workflow(build_duro_bom_workflow())
            else:
                for workflow in workflows:
                    original = workflow.model_dump()
                    normalized = self._normalize_duro_workflow(workflow)
                    if normalized.model_dump() != original:
                        self.repository.save_workflow(normalized)
            for run in self.repository.list_runs(limit=500):
                if run.status in {"queued", "running"}:
                    run.status = "failed"
                    run.message = "后端服务重启，原执行线程已中断"
                    run.logs.append(run.message)
                    run.finished_at = utc_now()
                    self.repository.save_run(run)
                    continue
                if run.report is not None and run.report.sop_material_count == 0:
                    run.status = "failed"
                    run.message = "SOP 核对源为空，历史差异报告已作废"
                    run.logs.append(run.message)
                    run.report = None
                    self.repository.save_run(run)
            self._initialized = True

    def list_workflows(self) -> list[Workflow]:
        self.initialize()
        workflows = self.repository.list_workflows()
        workflows.sort(key=lambda item: item.updated_at, reverse=True)
        return workflows

    def get_workflow(self, workflow_id: str) -> Workflow:
        self.initialize()
        workflow = self.repository.get_workflow(workflow_id)
        if workflow is None:
            raise WorkflowNotFoundError(f"工作流不存在: {workflow_id}")
        return workflow

    def create_workflow(self, payload: WorkflowCreate) -> Workflow:
        self.initialize()
        now = utc_now()
        workflow = Workflow.model_validate(
            {
                **payload.model_dump(),
                "created_at": now,
                "updated_at": now,
            }
        )
        workflow = self._normalize_duro_workflow(workflow)
        workflow.next_run_at = self._next_run_at(workflow, now)
        return self.repository.save_workflow(workflow)

    def update_workflow(self, workflow_id: str, payload: WorkflowUpdate) -> Workflow:
        current = self.get_workflow(workflow_id)
        now = utc_now()
        workflow = Workflow.model_validate(
            {
                **current.model_dump(),
                **payload.model_dump(exclude_unset=True),
                "updated_at": now,
            }
        )
        workflow = self._normalize_duro_workflow(workflow)
        workflow.next_run_at = self._next_run_at(workflow, now)
        return self.repository.save_workflow(workflow)

    def delete_workflow(self, workflow_id: str) -> None:
        self.get_workflow(workflow_id)
        self.repository.delete_workflow(workflow_id)

    def list_runs(self, workflow_id: str | None = None, limit: int = 30) -> list[WorkflowRun]:
        self.initialize()
        return self.repository.list_runs(workflow_id=workflow_id, limit=limit)

    def trigger_workflow(self, workflow_id: str, trigger_type: WorkflowTriggerType) -> WorkflowRun:
        workflow = self.get_workflow(workflow_id)
        now = utc_now()
        run = WorkflowRun(
            workflow_id=workflow.id,
            workflow_name=workflow.name,
            trigger_type=trigger_type,
            logs=[f"已接收{self._trigger_label(trigger_type)}触发请求。"],
        )
        self.repository.save_run(run)
        workflow.last_run_at = now
        workflow.updated_at = now
        workflow.next_run_at = self._next_run_at(workflow, now)
        self.repository.save_workflow(workflow)
        threading.Thread(
            target=self._execute_run,
            args=(workflow, run),
            name=f"workflow-{run.id}",
            daemon=True,
        ).start()
        return run

    def list_due_workflows(self) -> list[Workflow]:
        now = utc_now()
        return [
            workflow
            for workflow in self.list_workflows()
            if workflow.status == "active"
            and workflow.schedule.enabled
            and workflow.next_run_at is not None
            and workflow.next_run_at <= now
        ]

    def _execute_run(self, workflow: Workflow, run: WorkflowRun) -> None:
        run.status = "running"
        run.started_at = utc_now()
        run.logs.append(f"开始执行工作流：{workflow.name}")
        self.repository.save_run(run)

        try:
            if workflow.kind == "duro_bom_check":
                sop_sources = self._configured_sop_sources(workflow)
                ignored_sop_keywords = self._configured_ignored_sop_product_keywords(workflow)
                duro_source = str(workflow.configuration.get("duro_product_id") or "").strip()
                duro_submenu_ids = self._configured_duro_submenu_ids(workflow)
                run.logs.append("检查 SOP 与 Duro 数据源配置。")
                if not sop_sources or not duro_source or not duro_submenu_ids:
                    missing = []
                    if not sop_sources:
                        missing.append("SOP")
                    if not duro_source:
                        missing.append("Duro 产品")
                    if duro_source and not duro_submenu_ids:
                        missing.append("Duro 扫描子菜单")
                    run.status = "skipped"
                    run.message = f"请先配置数据源：{'、'.join(missing)}"
                    run.logs.append(run.message)
                    return
                if self.sop_service is None or self.duro_service is None:
                    raise RuntimeError("工作流 BOM 核对服务未初始化")
                run.logs.append(f"读取 {len(sop_sources)} 份 SOP。")
                self.repository.save_run(run)
                sop_materials = self._collect_sop_references(sop_sources)
                run.logs.append(f"SOP 全文引用汇总完成：{len(sop_materials)} 个料号。")
                self.repository.save_run(run)

                run.logs.append(
                    f"读取 Duro 产品：{workflow.configuration.get('duro_product_name') or duro_source}。"
                )
                self.repository.save_run(run)
                duro_materials, duro_submenus = self._collect_duro_materials(duro_source, duro_submenu_ids)
                run.logs.append(
                    f"Duro BOM 展开完成：扫描 {len(duro_submenus)} 个子菜单，"
                    f"识别 {len(duro_materials)} 个料号。"
                )
                self.repository.save_run(run)

                if ignored_sop_keywords:
                    removed_sop = self._remove_materials_by_name(sop_materials, ignored_sop_keywords)
                    run.logs.append(
                        f"按产品名称关键字过滤 SOP 物料：移除 {removed_sop} 项。"
                    )
                    self.repository.save_run(run)

                ignored_part_numbers = self._configured_ignored_part_numbers(workflow)
                if ignored_part_numbers:
                    removed_sop = sum(part_number in sop_materials for part_number in ignored_part_numbers)
                    removed_duro = sum(part_number in duro_materials for part_number in ignored_part_numbers)
                    for part_number in ignored_part_numbers:
                        sop_materials.pop(part_number, None)
                        duro_materials.pop(part_number, None)
                    run.logs.append(
                        f"已过滤 {len(ignored_part_numbers)} 个指定料号："
                        f"SOP 移除 {removed_sop} 项，Duro 移除 {removed_duro} 项。"
                    )
                    self.repository.save_run(run)

                report = self._build_bom_report(sop_sources, sop_materials, duro_materials, duro_submenus)
                run.report = report
                run.status = "succeeded"
                run.message = (
                    f"核对完成：{len(report.differences)} 项差异"
                    if report.differences
                    else "核对完成：BOM 一致"
                )
                run.logs.append(run.message)
            else:
                run.status = "skipped"
                run.message = "自定义工作流执行器待实现"
                run.logs.append(run.message)
        except Exception as exc:
            run.status = "failed"
            run.message = str(exc) or exc.__class__.__name__
            run.logs.append(f"运行失败：{run.message}")
        finally:
            run.finished_at = utc_now()
            self.repository.save_run(run)

    def _normalize_duro_workflow(self, workflow: Workflow) -> Workflow:
        if workflow.kind != "duro_bom_check":
            return workflow
        configuration = dict(workflow.configuration)
        raw_ids = configuration.get("sop_drive_file_ids")
        file_ids = [str(value).strip() for value in raw_ids] if isinstance(raw_ids, list) else []
        file_ids = [value for value in file_ids if value]
        legacy_file_id = str(configuration.get("sop_drive_file_id") or "").strip()
        if not file_ids and legacy_file_id:
            file_ids = [legacy_file_id]
        configuration["sop_drive_file_ids"] = list(dict.fromkeys(file_ids))

        raw_sources = configuration.get("sop_sources")
        sources = [dict(item) for item in raw_sources if isinstance(item, dict)] if isinstance(raw_sources, list) else []
        if not sources and legacy_file_id:
            sources = [
                {
                    "drive_file_id": legacy_file_id,
                    "project": configuration.get("sop_project") or "",
                    "process": configuration.get("sop_process") or "",
                    "issue_date": configuration.get("sop_issue_date") or "",
                    "link_url": configuration.get("sop_link_url") or "",
                    "row_number": configuration.get("sop_row_number"),
                }
            ]
        configuration["sop_sources"] = sources
        raw_submenu_ids = configuration.get("duro_submenu_ids")
        submenu_ids = raw_submenu_ids if isinstance(raw_submenu_ids, list) else []
        configuration["duro_submenu_ids"] = list(
            dict.fromkeys(
                normalized
                for value in submenu_ids
                if (normalized := str(value).strip())
            )
        )
        raw_submenus = configuration.get("duro_submenus")
        submenus = [dict(item) for item in raw_submenus if isinstance(item, dict)] if isinstance(raw_submenus, list) else []
        configuration["duro_submenus"] = [
            {
                "id": str(item.get("id") or "").strip(),
                "label": str(item.get("label") or "").strip(),
            }
            for item in submenus
            if str(item.get("id") or "").strip()
        ]
        raw_sop_keywords = configuration.get("ignored_sop_product_keywords")
        sop_keywords = raw_sop_keywords if isinstance(raw_sop_keywords, list) else []
        seen_sop_keywords: set[str] = set()
        configuration["ignored_sop_product_keywords"] = [
            keyword
            for value in sop_keywords
            if (keyword := str(value).strip())
            and not (normalized := keyword.casefold()) in seen_sop_keywords
            and not seen_sop_keywords.add(normalized)
        ]
        raw_ignored = configuration.get("ignored_part_numbers")
        ignored = raw_ignored if isinstance(raw_ignored, list) else []
        configuration["ignored_part_numbers"] = list(
            dict.fromkeys(
                normalized
                for value in ignored
                if (normalized := str(value).strip().upper())
            )
        )
        workflow.configuration = configuration

        desired_steps = build_duro_bom_steps()
        expected = [(step.kind, step.name, step.description) for step in desired_steps]
        current = [(step.kind, step.name, step.description) for step in workflow.steps]
        if current != expected:
            workflow.steps = desired_steps
        return workflow

    def _configured_sop_sources(self, workflow: Workflow) -> list[dict[str, Any]]:
        raw_sources = workflow.configuration.get("sop_sources")
        sources = [dict(item) for item in raw_sources if isinstance(item, dict)] if isinstance(raw_sources, list) else []
        normalized = []
        seen: set[str] = set()
        for source in sources:
            file_id = str(source.get("drive_file_id") or "").strip()
            if not file_id or file_id in seen:
                continue
            seen.add(file_id)
            source["drive_file_id"] = file_id
            normalized.append(source)
        if normalized:
            return normalized

        raw_ids = workflow.configuration.get("sop_drive_file_ids")
        file_ids = raw_ids if isinstance(raw_ids, list) else []
        legacy_file_id = str(workflow.configuration.get("sop_drive_file_id") or "").strip()
        if not file_ids and legacy_file_id:
            file_ids = [legacy_file_id]
        return [
            {"drive_file_id": str(file_id).strip(), "project": "", "process": ""}
            for file_id in file_ids
            if str(file_id).strip()
        ]

    def _configured_ignored_part_numbers(self, workflow: Workflow) -> set[str]:
        raw_values = workflow.configuration.get("ignored_part_numbers")
        values = raw_values if isinstance(raw_values, list) else []
        return {
            normalized
            for value in values
            if (normalized := str(value).strip().upper())
        }

    def _configured_ignored_sop_product_keywords(self, workflow: Workflow) -> list[str]:
        raw_values = workflow.configuration.get("ignored_sop_product_keywords")
        values = raw_values if isinstance(raw_values, list) else []
        return list(
            dict.fromkeys(
                normalized
                for value in values
                if (normalized := self._normalize_sop_product_text(value))
            )
        )

    @classmethod
    def _material_name_matches_keywords(cls, name: Any, keywords: list[str]) -> bool:
        normalized_name = cls._normalize_sop_product_text(name)
        return any(cls._normalize_sop_product_text(keyword) in normalized_name for keyword in keywords)

    @classmethod
    def _remove_materials_by_name(cls, materials: dict[str, dict[str, Any]], keywords: list[str]) -> int:
        matched_part_numbers = [
            part_number
            for part_number, material in materials.items()
            if cls._material_name_matches_keywords(material.get("name"), keywords)
        ]
        for part_number in matched_part_numbers:
            materials.pop(part_number, None)
        return len(matched_part_numbers)

    @staticmethod
    def _normalize_sop_product_text(value: Any) -> str:
        text = unicodedata.normalize("NFKC", str(value or "")).casefold().replace("μ", "u")
        return "".join(text.split())

    def _configured_duro_submenu_ids(self, workflow: Workflow) -> set[str]:
        raw_values = workflow.configuration.get("duro_submenu_ids")
        values = raw_values if isinstance(raw_values, list) else []
        return {
            normalized
            for value in values
            if (normalized := str(value).strip())
        }

    def _collect_sop_references(self, sources: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        assert self.sop_service is not None
        materials: dict[str, dict[str, Any]] = {}
        for source in sources:
            file_id = str(source["drive_file_id"])
            label = " / ".join(
                value
                for value in (str(source.get("project") or "").strip(), str(source.get("process") or "").strip())
                if value
            ) or file_id
            analysis = self.sop_service.analyze_pdf(file_id)
            if not analysis.full_text_references:
                raise RuntimeError(f"SOP“{label}”未识别到全文料号引用，无法执行 BOM 核对")
            for material in analysis.full_text_references:
                current = materials.setdefault(
                    material.part_number,
                    {
                        "name": material.name,
                        "quantity": 0.0,
                        "quantity_known": True,
                        "locations": [],
                    },
                )
                current["quantity"] += float(getattr(material, "quantity", 0) or material.occurrences)
                if len(material.name) > len(str(current["name"])):
                    current["name"] = material.name
                location = f"{label}：第 {', '.join(str(page) for page in material.pages)} 页"
                if location not in current["locations"]:
                    current["locations"].append(location)
        return materials

    def _collect_duro_materials(
        self,
        product_id: str,
        selected_submenu_ids: set[str],
    ) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
        assert self.duro_service is not None
        response = self.duro_service.get_product_bom(product_id)
        materials: dict[str, dict[str, Any]] = {}
        visited_nodes = 0

        selected_submenus: list[dict[str, str]] = []

        def visit(
            node: DuroBomNode,
            multiplier: float,
            path: list[str],
            ancestors: set[str],
            submenu_id: str,
            submenu_label: str,
        ) -> None:
            nonlocal visited_nodes
            visited_nodes += 1
            if visited_nodes > 5000:
                raise RuntimeError("Duro BOM 节点超过 5000，已停止展开")
            quantity = self._number(node.quantity, default=1.0)
            effective_quantity = multiplier * quantity
            if effective_quantity <= 0:
                return
            identity = node.cpn or node.name or node.id
            current_path = [*path, identity]
            if node.cpn:
                current = materials.setdefault(
                    node.cpn,
                    {
                        "name": node.name,
                        "quantity": 0.0,
                        "paths": [],
                        "submenu_ids": [],
                        "submenu_labels": [],
                    },
                )
                current["quantity"] += effective_quantity
                if len(node.name) > len(str(current["name"])):
                    current["name"] = node.name
                path_text = " > ".join(current_path)
                if path_text not in current["paths"] and len(current["paths"]) < 20:
                    current["paths"].append(path_text)
                if submenu_id not in current["submenu_ids"]:
                    current["submenu_ids"].append(submenu_id)
                if submenu_label not in current["submenu_labels"]:
                    current["submenu_labels"].append(submenu_label)
            if not node.has_children or node.id in ancestors:
                return
            children = self.duro_service.get_component_children(node.id).children
            next_ancestors = {*ancestors, node.id}
            for child in children:
                visit(child, effective_quantity, current_path, next_ancestors, submenu_id, submenu_label)

        root_label = response.root.cpn or response.root.name or product_id
        for submenu in response.root.children:
            if submenu.id not in selected_submenu_ids:
                continue
            submenu_label = submenu.cpn or submenu.name or submenu.id
            selected_submenus.append({"id": submenu.id, "label": submenu_label, "name": submenu.name})
            submenu_quantity = self._number(submenu.quantity, default=1.0)
            children = self.duro_service.get_component_children(submenu.id).children
            for child in children:
                visit(
                    child,
                    submenu_quantity,
                    [root_label, submenu_label],
                    {submenu.id},
                    submenu.id,
                    submenu_label,
                )
        missing_ids = selected_submenu_ids - {item["id"] for item in selected_submenus}
        if missing_ids:
            raise RuntimeError(f"Duro 子菜单不存在或已失效：{', '.join(sorted(missing_ids))}")
        return materials, selected_submenus

    def _build_bom_report(
        self,
        sources: list[dict[str, Any]],
        sop_materials: dict[str, dict[str, Any]],
        duro_materials: dict[str, dict[str, Any]],
        duro_submenus: list[dict[str, str]],
    ) -> WorkflowBomReport:
        differences: list[WorkflowBomDifference] = []
        matched_count = 0
        for part_number in sorted(set(sop_materials) | set(duro_materials)):
            sop = sop_materials.get(part_number)
            duro = duro_materials.get(part_number)
            if sop is None:
                differences.append(
                    WorkflowBomDifference(
                        status="extra_in_duro",
                        part_number=part_number,
                        name=str(duro["name"]),
                        duro_quantity=self._rounded(duro["quantity"]),
                        duro_paths=list(duro["paths"]),
                        duro_submenu_ids=list(duro["submenu_ids"]),
                        duro_submenu_labels=list(duro["submenu_labels"]),
                    )
                )
                continue
            if duro is None:
                differences.append(
                    WorkflowBomDifference(
                        status="missing_in_duro",
                        part_number=part_number,
                        name=str(sop["name"]),
                        sop_quantity=self._rounded(sop["quantity"]) if sop["quantity_known"] else None,
                        sop_locations=list(sop["locations"]),
                    )
                )
                continue
            sop_quantity = self._rounded(sop["quantity"]) if sop["quantity_known"] else None
            duro_quantity = self._rounded(duro["quantity"])
            if sop_quantity is None:
                differences.append(
                    WorkflowBomDifference(
                        status="quantity_unknown",
                        part_number=part_number,
                        name=str(sop["name"] or duro["name"]),
                        sop_quantity=None,
                        duro_quantity=duro_quantity,
                        sop_locations=list(sop["locations"]),
                        duro_paths=list(duro["paths"]),
                        duro_submenu_ids=list(duro["submenu_ids"]),
                        duro_submenu_labels=list(duro["submenu_labels"]),
                    )
                )
            elif abs(sop_quantity - duro_quantity) > 1e-6:
                differences.append(
                    WorkflowBomDifference(
                        status="quantity_mismatch",
                        part_number=part_number,
                        name=str(sop["name"] or duro["name"]),
                        sop_quantity=sop_quantity,
                        duro_quantity=duro_quantity,
                        quantity_delta=self._rounded(duro_quantity - sop_quantity),
                        sop_locations=list(sop["locations"]),
                        duro_paths=list(duro["paths"]),
                        duro_submenu_ids=list(duro["submenu_ids"]),
                        duro_submenu_labels=list(duro["submenu_labels"]),
                    )
                )
            else:
                matched_count += 1

        return WorkflowBomReport(
            sop_source_count=len(sources),
            sop_material_count=len(sop_materials),
            duro_material_count=len(duro_materials),
            matched_count=matched_count,
            missing_in_duro_count=sum(item.status == "missing_in_duro" for item in differences),
            extra_in_duro_count=sum(item.status == "extra_in_duro" for item in differences),
            quantity_mismatch_count=sum(item.status == "quantity_mismatch" for item in differences),
            quantity_unknown_count=sum(item.status == "quantity_unknown" for item in differences),
            duro_submenus=duro_submenus,
            differences=differences,
        )

    @staticmethod
    def _number(value: Any, default: float = 0.0) -> float:
        try:
            return float(value) if value not in (None, "") else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _rounded(value: Any) -> float:
        return round(float(value), 6)

    def _next_run_at(self, workflow: Workflow, base_time):
        if workflow.status != "active" or not workflow.schedule.enabled:
            return None
        return base_time + timedelta(minutes=workflow.schedule.interval_minutes)

    def _trigger_label(self, trigger_type: WorkflowTriggerType) -> str:
        return "定时" if trigger_type == "scheduled" else "手动"
