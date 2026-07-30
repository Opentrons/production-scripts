from __future__ import annotations

import threading
import unicodedata
import re
from datetime import timedelta
from typing import Any

from duro.models import DuroBomNode
from duro.service import DuroService
from sop.service import SopService

from workflows.models import (
    Workflow,
    WorkflowBomDifference,
    WorkflowBomIgnoredItem,
    WorkflowBomReport,
    WorkflowCreate,
    WorkflowRun,
    WorkflowRunDetailResponse,
    WorkflowRunDeleteResponse,
    WorkflowRunPage,
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
            "ignored_sop_product_keyword_reasons": {},
            "ignored_part_number_reasons": {},
            "ignore_quantity_mismatch_warning": False,
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

    def list_run_summaries(self, workflow_id: str | None = None, limit: int = 30) -> list[WorkflowRun]:
        runs = self.list_runs(workflow_id=workflow_id, limit=limit)
        summaries: list[WorkflowRun] = []
        for run in runs:
            if run.report is None:
                summaries.append(run)
                continue
            total = len(run.report.differences)
            summaries.append(
                run.model_copy(
                    update={
                        "report": run.report.model_copy(
                            update={
                                "differences": [],
                                "total_difference_count": total,
                                "ignored_items": [],
                                "total_ignored_count": len(run.report.ignored_items),
                            }
                        )
                    }
                )
            )
        return summaries

    def list_run_page(
        self,
        workflow_id: str | None,
        page: int,
        page_size: int,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> WorkflowRunPage:
        self.initialize()
        runs = self.repository.list_runs_in_range(workflow_id, created_from, created_to)
        total = len(runs)
        success_count = sum(run.status == "succeeded" for run in runs)
        failed_count = sum(run.status == "failed" for run in runs)
        warning_count = sum(
            run.status == "succeeded"
            and run.report is not None
            and (
                run.report.warning_difference_count
                if run.report.warning_difference_count is not None
                else len(run.report.differences)
            ) > 0
            for run in runs
        )
        start = (page - 1) * page_size
        page_runs = runs[start:start + page_size]
        summaries: list[WorkflowRun] = []
        for run in page_runs:
            if run.report is None:
                summaries.append(run)
                continue
            summaries.append(
                run.model_copy(
                    update={
                        "report": run.report.model_copy(
                            update={
                                "differences": [],
                                "total_difference_count": len(run.report.differences),
                                "ignored_items": [],
                                "total_ignored_count": len(run.report.ignored_items),
                            }
                        )
                    }
                )
            )
        return WorkflowRunPage(
            items=summaries,
            total=total,
            page=page,
            page_size=page_size,
            success_count=success_count,
            failed_count=failed_count,
            warning_count=warning_count,
        )

    def get_run_detail(
        self,
        run_id: str,
        difference_offset: int = 0,
        difference_limit: int = 50,
    ) -> WorkflowRunDetailResponse:
        self.initialize()
        run = self.repository.get_run(run_id)
        if run is None:
            raise WorkflowNotFoundError(f"运行记录不存在：{run_id}")
        total = len(run.report.differences) if run.report else 0
        if run.report is not None:
            page = run.report.differences[difference_offset:difference_offset + difference_limit]
            run = run.model_copy(
                update={
                    "report": run.report.model_copy(
                        update={"differences": page, "total_difference_count": total}
                    )
                }
            )
        return WorkflowRunDetailResponse(
            run=run,
            difference_offset=difference_offset,
            difference_limit=difference_limit,
            difference_total=total,
            has_more=difference_offset + difference_limit < total,
        )

    def delete_runs(self, run_ids: list[str]) -> WorkflowRunDeleteResponse:
        self.initialize()
        return WorkflowRunDeleteResponse(deleted_count=self.repository.delete_runs(run_ids))

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
                run.logs.append("运行前强制刷新 SOP 总表和 Duro 产品表。")
                self.repository.save_run(run)
                sop_sources, duro_source = self._refresh_run_data_sources(
                    workflow,
                    sop_sources,
                    duro_source,
                    run,
                )
                run.logs.append(f"读取 {len(sop_sources)} 份 SOP。")
                self.repository.save_run(run)
                sop_materials = self._collect_sop_references(sop_sources)
                sop_cleanup_items = self._normalize_material_part_numbers(sop_materials, "sop")
                run.logs.append(f"SOP 全文引用汇总完成：{len(sop_materials)} 个料号。")
                self.repository.save_run(run)

                run.logs.append(
                    f"读取 Duro 产品：{workflow.configuration.get('duro_product_name') or duro_source}。"
                )
                self.repository.save_run(run)
                duro_materials, duro_submenus = self._collect_duro_materials(duro_source, duro_submenu_ids)
                duro_cleanup_items = self._normalize_material_part_numbers(duro_materials, "duro")
                run.logs.append(
                    f"Duro BOM 展开完成：扫描 {len(duro_submenus)} 个子菜单，"
                    f"识别 {len(duro_materials)} 个料号。"
                )
                self.repository.save_run(run)

                report = self._build_bom_report(sop_sources, sop_materials, duro_materials, duro_submenus)
                report = self._apply_ignored_differences(workflow, report)
                warning_difference_count = (
                    report.missing_in_duro_count
                    + report.extra_in_duro_count
                    + report.quantity_unknown_count
                    + (
                        0
                        if workflow.configuration.get("ignore_quantity_mismatch_warning")
                        else report.quantity_mismatch_count
                    )
                )
                report.warning_difference_count = warning_difference_count
                cleanup_items = [*sop_cleanup_items, *duro_cleanup_items]
                if cleanup_items:
                    report.ignored_items.extend(cleanup_items)
                    report.total_ignored_count = len(report.ignored_items)
                    run.logs.append(f"默认料号清洗完成：规范化 {len(cleanup_items)} 个料号。")
                if report.ignored_items:
                    run.logs.append(f"已按配置忽略 {len(report.ignored_items)} 项 BOM 差异。")
                run.report = report
                run.status = "succeeded"
                run.message = f"核对完成：{warning_difference_count} 项警告"
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
        raw_keyword_reasons = configuration.get("ignored_sop_product_keyword_reasons")
        keyword_reasons = raw_keyword_reasons if isinstance(raw_keyword_reasons, dict) else {}
        configuration["ignored_sop_product_keyword_reasons"] = {
            keyword: str(keyword_reasons.get(keyword) or "历史配置未填写原因").strip()
            for keyword in configuration["ignored_sop_product_keywords"]
        }
        raw_ignored = configuration.get("ignored_part_numbers")
        ignored = raw_ignored if isinstance(raw_ignored, list) else []
        configuration["ignored_part_numbers"] = list(
            dict.fromkeys(
                normalized
                for value in ignored
                if (normalized := str(value).strip().upper())
            )
        )
        raw_part_reasons = configuration.get("ignored_part_number_reasons")
        part_reasons = raw_part_reasons if isinstance(raw_part_reasons, dict) else {}
        configuration["ignored_part_number_reasons"] = {
            part_number: str(part_reasons.get(part_number) or "历史配置未填写原因").strip()
            for part_number in configuration["ignored_part_numbers"]
        }
        configuration["ignore_quantity_mismatch_warning"] = bool(
            configuration.get("ignore_quantity_mismatch_warning", False)
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

    def _refresh_run_data_sources(
        self,
        workflow: Workflow,
        configured_sop_sources: list[dict[str, Any]],
        configured_duro_product_id: str,
        run: WorkflowRun,
    ) -> tuple[list[dict[str, Any]], str]:
        assert self.sop_service is not None
        assert self.duro_service is not None

        master_sheet = self.sop_service.get_master_sheet(refresh=True)
        if bool(getattr(master_sheet, "cached", False)):
            raise RuntimeError("SOP 总表强制刷新失败：服务返回了缓存数据")
        fresh_sop_sources = [
            self._sop_catalog_source(
                self._match_sop_catalog_entry(source, list(master_sheet.entries))
            )
            for source in configured_sop_sources
        ]
        changed_sop_links = sum(
            str(old.get("drive_file_id") or "").strip() != fresh["drive_file_id"]
            for old, fresh in zip(configured_sop_sources, fresh_sop_sources)
        )
        run.logs.append(
            f"SOP 总表实时刷新完成：定位 {len(fresh_sop_sources)} 份 SOP，"
            f"更新 {changed_sop_links} 个源 PDF 链接。"
        )

        product_table = self.duro_service.list_products(refresh=True)
        if bool(getattr(product_table, "cached", False)):
            raise RuntimeError("Duro 产品表强制刷新失败：服务返回了缓存数据")
        product = self._match_duro_product(
            workflow,
            list(product_table.products),
            configured_duro_product_id,
        )
        fresh_duro_product_id = self._duro_product_text(product, "id")
        if not fresh_duro_product_id:
            raise RuntimeError("Duro 产品表中的目标产品缺少产品 ID")
        product_changed = fresh_duro_product_id != configured_duro_product_id
        run.logs.append(
            f"Duro 产品表实时刷新完成：读取 {len(product_table.products)} 个产品，"
            f"目标产品 ID {'已更新' if product_changed else '未变化'}。"
        )

        configuration = dict(workflow.configuration)
        configuration["sop_sources"] = fresh_sop_sources
        configuration["sop_drive_file_ids"] = [
            source["drive_file_id"] for source in fresh_sop_sources
        ]
        first_source = fresh_sop_sources[0]
        configuration["sop_drive_file_id"] = first_source["drive_file_id"]
        configuration["sop_project"] = first_source["project"]
        configuration["sop_process"] = first_source["process"]
        configuration["sop_issue_date"] = first_source["issue_date"]
        configuration["sop_link_url"] = first_source["link_url"]
        configuration["sop_row_number"] = first_source["row_number"]
        configuration["duro_product_id"] = fresh_duro_product_id
        configuration["duro_product_name"] = self._duro_product_text(product, "name")
        configuration["duro_product_cpn"] = self._duro_product_text(product, "cpn")
        configuration["duro_product_revision"] = self._duro_product_text(product, "revision")
        workflow.configuration = configuration
        workflow.updated_at = utc_now()
        self.repository.save_workflow(workflow)
        self.repository.save_run(run)
        return fresh_sop_sources, fresh_duro_product_id

    def _match_sop_catalog_entry(
        self,
        source: dict[str, Any],
        entries: list[Any],
    ) -> Any:
        linked_entries = [entry for entry in entries if self._sop_entry_text(entry, "drive_file_id")]
        project = self._normalized_identity(source.get("project"))
        process = self._normalized_identity(source.get("process"))
        issue_date = self._normalized_identity(source.get("issue_date"))
        row_number = str(source.get("row_number") or "").strip()
        file_id = str(source.get("drive_file_id") or "").strip()

        def same_identity(entry: Any) -> bool:
            return (
                (not project or self._normalized_identity(self._sop_entry_value(entry, "project")) == project)
                and (not process or self._normalized_identity(self._sop_entry_value(entry, "process")) == process)
            )

        if row_number:
            row_matches = [
                entry
                for entry in linked_entries
                if str(self._sop_entry_value(entry, "row_number") or "").strip() == row_number
                and same_identity(entry)
            ]
            if len(row_matches) == 1:
                return row_matches[0]

        identity_matches = [entry for entry in linked_entries if same_identity(entry)]
        if (project or process) and issue_date:
            dated_matches = [
                entry
                for entry in identity_matches
                if self._normalized_identity(self._sop_entry_value(entry, "issue_date")) == issue_date
            ]
            if len(dated_matches) == 1:
                return dated_matches[0]
        if (project or process) and len(identity_matches) == 1:
            return identity_matches[0]

        file_matches = [
            entry
            for entry in linked_entries
            if self._sop_entry_text(entry, "drive_file_id") == file_id
        ]
        if len(file_matches) == 1:
            return file_matches[0]

        label = " / ".join(value for value in (str(source.get("project") or "").strip(), str(source.get("process") or "").strip()) if value)
        if len(identity_matches) > 1:
            raise RuntimeError(f"刷新 SOP 总表后匹配到多条记录，无法确定当前链接：{label or file_id}")
        raise RuntimeError(f"刷新 SOP 总表后未找到对应的当前 PDF 链接：{label or file_id}")

    def _match_duro_product(
        self,
        workflow: Workflow,
        products: list[Any],
        configured_product_id: str,
    ) -> Any:
        id_matches = [
            product
            for product in products
            if self._duro_product_text(product, "id") == configured_product_id
        ]
        if len(id_matches) == 1:
            return id_matches[0]

        configured_cpn = self._normalized_identity(workflow.configuration.get("duro_product_cpn"))
        configured_name = self._normalized_identity(workflow.configuration.get("duro_product_name"))
        configured_revision = self._normalized_identity(workflow.configuration.get("duro_product_revision"))

        for field, expected in (("cpn", configured_cpn), ("name", configured_name)):
            if not expected:
                continue
            matches = [
                product
                for product in products
                if self._normalized_identity(self._duro_product_text(product, field)) == expected
            ]
            if configured_revision and len(matches) > 1:
                matches = [
                    product
                    for product in matches
                    if self._normalized_identity(self._duro_product_text(product, "revision"))
                    == configured_revision
                ]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                raise RuntimeError(f"刷新 Duro 产品表后匹配到多个目标产品：{expected}")

        identity = (
            str(workflow.configuration.get("duro_product_cpn") or "").strip()
            or str(workflow.configuration.get("duro_product_name") or "").strip()
            or configured_product_id
        )
        raise RuntimeError(f"刷新 Duro 产品表后未找到目标产品：{identity}")

    @staticmethod
    def _sop_entry_value(entry: Any, field: str) -> Any:
        if isinstance(entry, dict):
            return entry.get(field)
        return getattr(entry, field, None)

    @classmethod
    def _sop_entry_text(cls, entry: Any, field: str) -> str:
        return str(cls._sop_entry_value(entry, field) or "").strip()

    @classmethod
    def _sop_catalog_source(cls, entry: Any) -> dict[str, Any]:
        return {
            "drive_file_id": cls._sop_entry_text(entry, "drive_file_id"),
            "project": cls._sop_entry_text(entry, "project"),
            "process": cls._sop_entry_text(entry, "process"),
            "issue_date": cls._sop_entry_text(entry, "issue_date"),
            "link_url": cls._sop_entry_text(entry, "link_url"),
            "row_number": cls._sop_entry_value(entry, "row_number"),
        }

    @staticmethod
    def _duro_product_text(product: Any, field: str) -> str:
        if isinstance(product, dict):
            value = product.get(field)
            if field == "id" and value is None:
                value = product.get("_id")
        else:
            value = getattr(product, field, None)
        return str(value or "").strip()

    @staticmethod
    def _normalized_identity(value: Any) -> str:
        return " ".join(str(value or "").strip().casefold().split())

    def _configured_ignored_part_numbers(self, workflow: Workflow) -> set[str]:
        raw_values = workflow.configuration.get("ignored_part_numbers")
        values = raw_values if isinstance(raw_values, list) else []
        return {
            self._clean_part_number(normalized)
            for value in values
            if (normalized := str(value).strip().upper())
        }

    def _configured_ignored_sop_product_keywords(self, workflow: Workflow) -> list[str]:
        raw_values = workflow.configuration.get("ignored_sop_product_keywords")
        values = raw_values if isinstance(raw_values, list) else []
        configured: list[str] = []
        seen: set[str] = set()
        for value in values:
            keyword = str(value).strip()
            normalized = self._normalize_sop_product_text(keyword)
            if normalized and normalized not in seen:
                seen.add(normalized)
                configured.append(keyword)
        return configured

    @classmethod
    def _material_name_matches_keywords(cls, name: Any, keywords: list[str]) -> bool:
        return cls._matching_sop_keyword(name, keywords) is not None

    @classmethod
    def _matching_sop_keyword(cls, name: Any, keywords: list[str]) -> str | None:
        normalized_name = cls._normalize_sop_product_text(name)
        for keyword in keywords:
            normalized_keyword = cls._normalize_sop_product_text(keyword)
            if normalized_keyword and normalized_keyword in normalized_name:
                return keyword
            fragments = [
                cls._normalize_sop_product_text(fragment)
                for fragment in re.split(r"[\s,，;；/|]+", str(keyword).strip())
                if cls._normalize_sop_product_text(fragment)
            ]
            position = 0
            for fragment in fragments:
                matched_at = normalized_name.find(fragment, position)
                if matched_at < 0:
                    break
                position = matched_at + len(fragment)
            else:
                if len(fragments) > 1:
                    return keyword
        return None

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
        text = re.sub(r"\bvolumes?\b", "容量", text)
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
            # A workflow run is an explicit verification request: always
            # re-analyze the SOP and replace the persistent analysis cache.
            analysis = self.sop_service.analyze_pdf(file_id, refresh=True)
            if bool(getattr(analysis, "cached", False)):
                raise RuntimeError(f"SOP“{label}”强制刷新失败：服务返回了缓存分析")
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
                        "quantity_explanations": [],
                        "quantity_decisions": [],
                    },
                )
                current["quantity"] += float(getattr(material, "quantity", 0) or material.occurrences)
                if len(material.name) > len(str(current["name"])):
                    current["name"] = material.name
                location = f"{label}：第 {', '.join(str(page) for page in material.pages)} 页"
                if location not in current["locations"]:
                    current["locations"].append(location)
                quantity_explanation = str(getattr(material, "quantity_explanation", "") or "")
                if not quantity_explanation:
                    material_quantity = float(getattr(material, "quantity", 0) or material.occurrences)
                    quantity_explanation = (
                        "大模型未返回该料号的完整语义累加明细，"
                        f"当前采用 SOP 正文规则统计数量 {self._rounded(material_quantity):g}"
                    )
                explanation = f"{label}：{quantity_explanation}"
                if explanation not in current["quantity_explanations"]:
                    current["quantity_explanations"].append(explanation)
                current["quantity_decisions"].extend(
                    {"source": label, **decision.model_dump()}
                    for decision in getattr(material, "quantity_decisions", [])
                )
        return materials

    def _collect_duro_materials(
        self,
        product_id: str,
        selected_submenu_ids: set[str],
    ) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
        assert self.duro_service is not None
        # A workflow run must compare against the current Duro BOM, not the
        # last page-view snapshot. The service refresh also updates SQLite.
        response = self.duro_service.get_product_bom(product_id, refresh=True)
        if bool(getattr(response, "cached", False)):
            raise RuntimeError("Duro 产品 BOM 强制刷新失败：服务返回了缓存数据")
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
            child_response = self.duro_service.get_component_children(node.id, refresh=True)
            if bool(getattr(child_response, "cached", False)):
                raise RuntimeError(f"Duro 子组件 {node.id} 强制刷新失败：服务返回了缓存数据")
            children = child_response.children
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
            child_response = self.duro_service.get_component_children(submenu.id, refresh=True)
            if bool(getattr(child_response, "cached", False)):
                raise RuntimeError(f"Duro 子菜单 {submenu.id} 强制刷新失败：服务返回了缓存数据")
            children = child_response.children
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
                        sop_quantity_explanations=list(sop["quantity_explanations"]),
                        sop_quantity_decisions=list(sop["quantity_decisions"]),
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
                        sop_quantity_explanations=list(sop["quantity_explanations"]),
                        sop_quantity_decisions=list(sop["quantity_decisions"]),
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
                        sop_quantity_explanations=list(sop["quantity_explanations"]),
                        sop_quantity_decisions=list(sop["quantity_decisions"]),
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

    def _apply_ignored_differences(
        self,
        workflow: Workflow,
        report: WorkflowBomReport,
    ) -> WorkflowBomReport:
        keyword_reasons = workflow.configuration.get("ignored_sop_product_keyword_reasons")
        keyword_reasons = keyword_reasons if isinstance(keyword_reasons, dict) else {}
        part_reasons = workflow.configuration.get("ignored_part_number_reasons")
        part_reasons = part_reasons if isinstance(part_reasons, dict) else {}
        keywords = self._configured_ignored_sop_product_keywords(workflow)
        ignored_parts = self._configured_ignored_part_numbers(workflow)
        raw_ignored_parts = workflow.configuration.get("ignored_part_numbers")
        raw_ignored_parts = raw_ignored_parts if isinstance(raw_ignored_parts, list) else []
        ignored_part_rules = {
            self._clean_part_number(str(value)): str(value).strip().upper()
            for value in raw_ignored_parts
            if str(value).strip()
        }
        kept: list[WorkflowBomDifference] = []
        ignored: list[WorkflowBomIgnoredItem] = []
        for difference in report.differences:
            ignore_type: str | None = None
            ignore_value = ""
            reason = ""
            if difference.part_number in ignored_parts:
                ignore_type = "part_number"
                ignore_value = ignored_part_rules.get(difference.part_number, difference.part_number)
                reason = str(
                    part_reasons.get(ignore_value)
                    or part_reasons.get(difference.part_number)
                    or "历史配置未填写原因"
                )
            else:
                matched_keyword = self._matching_sop_keyword(difference.name, keywords)
                if matched_keyword and difference.status != "extra_in_duro":
                    ignore_type = "sop_product_keyword"
                    ignore_value = matched_keyword
                    reason = str(keyword_reasons.get(matched_keyword) or "历史配置未填写原因")
            if ignore_type:
                ignored.append(
                    WorkflowBomIgnoredItem(
                        **difference.model_dump(),
                        ignore_type=ignore_type,
                        ignore_value=ignore_value,
                        ignore_reason=reason,
                    )
                )
            else:
                kept.append(difference)
        return report.model_copy(
            update={
                "differences": kept,
                "sop_material_count": report.sop_material_count - sum(
                    item.status != "extra_in_duro" for item in ignored
                ),
                "duro_material_count": report.duro_material_count - sum(
                    item.ignore_type == "part_number" and item.status != "missing_in_duro"
                    for item in ignored
                ),
                "missing_in_duro_count": sum(item.status == "missing_in_duro" for item in kept),
                "extra_in_duro_count": sum(item.status == "extra_in_duro" for item in kept),
                "quantity_mismatch_count": sum(item.status == "quantity_mismatch" for item in kept),
                "quantity_unknown_count": sum(item.status == "quantity_unknown" for item in kept),
                "ignored_items": ignored,
                "total_ignored_count": len(ignored),
            }
        )

    @staticmethod
    def _clean_part_number(part_number: str) -> str:
        match = re.fullmatch(r"(\d{3})-0(\d{5})", part_number.strip().upper())
        return f"{match.group(1)}-{match.group(2)}" if match else part_number.strip().upper()

    def _normalize_material_part_numbers(
        self,
        materials: dict[str, dict[str, Any]],
        source: str,
    ) -> list[WorkflowBomIgnoredItem]:
        cleanup_items: list[WorkflowBomIgnoredItem] = []
        for original in list(materials):
            normalized = self._clean_part_number(original)
            if normalized == original:
                continue
            material = materials.pop(original)
            existing = materials.get(normalized)
            if existing is None:
                materials[normalized] = material
            else:
                existing["quantity"] = float(existing.get("quantity", 0)) + float(material.get("quantity", 0))
                if len(str(material.get("name") or "")) > len(str(existing.get("name") or "")):
                    existing["name"] = material.get("name") or ""
                for field in (
                    ("locations", "quantity_explanations", "quantity_decisions")
                    if source == "sop"
                    else ("paths", "submenu_ids", "submenu_labels")
                ):
                    for value in material.get(field, []):
                        if value not in existing.setdefault(field, []):
                            existing[field].append(value)
                if source == "sop":
                    existing["quantity_known"] = bool(existing.get("quantity_known", True)) and bool(
                        material.get("quantity_known", True)
                    )

            cleanup_items.append(
                WorkflowBomIgnoredItem(
                    status="missing_in_duro" if source == "sop" else "extra_in_duro",
                    part_number=original,
                    name=str(material.get("name") or ""),
                    sop_quantity=self._rounded(material.get("quantity", 0)) if source == "sop" else None,
                    duro_quantity=self._rounded(material.get("quantity", 0)) if source == "duro" else None,
                    sop_locations=list(material.get("locations", [])),
                    sop_quantity_explanations=list(material.get("quantity_explanations", [])),
                    sop_quantity_decisions=list(material.get("quantity_decisions", [])),
                    duro_paths=list(material.get("paths", [])),
                    duro_submenu_ids=list(material.get("submenu_ids", [])),
                    duro_submenu_labels=list(material.get("submenu_labels", [])),
                    ignore_type="part_number_cleanup",
                    ignore_value=original,
                    ignore_reason=f"默认料号清洗：{original} → {normalized}",
                    normalized_part_number=normalized,
                )
            )
        return cleanup_items

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
