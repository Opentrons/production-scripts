from __future__ import annotations

import threading
from datetime import timedelta

from workflows.models import (
    Workflow,
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


def build_duro_bom_workflow() -> Workflow:
    return Workflow(
        name="Duro BOM 核对",
        description="从 Duro 拉取目标产品 BOM，执行结构和版本差异核对，并输出报告。",
        kind="duro_bom_check",
        status="draft",
        configuration={
            "duro_base_url": "",
            "duro_product_id": "",
            "target_revision": "",
        },
        steps=[
            WorkflowStep(
                name="读取 Duro BOM",
                kind="duro_bom_fetch",
                description="按产品 ID 和目标版本读取 Duro BOM。",
            ),
            WorkflowStep(
                name="核对 BOM",
                kind="bom_compare",
                description="检查料号、数量、版本和层级差异。",
            ),
            WorkflowStep(
                name="生成核对报告",
                kind="report",
                description="汇总缺失项、冗余项和版本不一致。",
            ),
        ],
    )


class WorkflowService:
    def __init__(self, repository: WorkflowRepository) -> None:
        self.repository = repository
        self._initialized = False
        self._initialize_lock = threading.Lock()

    def initialize(self) -> None:
        with self._initialize_lock:
            if self._initialized:
                return
            if not self.repository.list_workflows():
                self.repository.save_workflow(build_duro_bom_workflow())
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
                run.logs.extend(
                    [
                        "准备读取 Duro BOM 配置。",
                        "Duro API 连接器尚未接入，本次运行不执行真实 BOM 核对。",
                    ]
                )
                run.status = "skipped"
                run.message = "Duro API 连接器待配置"
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

    def _next_run_at(self, workflow: Workflow, base_time):
        if workflow.status != "active" or not workflow.schedule.enabled:
            return None
        return base_time + timedelta(minutes=workflow.schedule.interval_minutes)

    def _trigger_label(self, trigger_type: WorkflowTriggerType) -> str:
        return "定时" if trigger_type == "scheduled" else "手动"
