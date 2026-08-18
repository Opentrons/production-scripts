"""MongoDB-backed workflow storage (production / non-simulating)."""

from __future__ import annotations

from threading import RLock
from typing import Any

from core.persistence import get_document_collection
from modules.workflows.models import Workflow, WorkflowIgnoredPartRule, WorkflowRun


class MongoWorkflowRepository:
    """Document-store workflow storage with the same surface as WorkflowRepository."""

    WORKFLOWS = "workflows"
    RUNS = "workflow_runs"
    IGNORED = "workflow_ignored_part_rules"

    def __init__(self) -> None:
        self._lock = RLock()

    def _workflows(self):
        return get_document_collection(self.WORKFLOWS)

    def _runs(self):
        return get_document_collection(self.RUNS)

    def _ignored(self):
        return get_document_collection(self.IGNORED)

    def initialize(self) -> None:
        """Create indexes after the application has established MongoDB."""
        with self._lock:
            self._runs().create_index([("workflow_id", 1), ("created_at", -1)])
            self._ignored().create_index([("workflow_id", 1), ("ignored_at", -1)])

    def list_workflows(self) -> list[Workflow]:
        with self._lock:
            documents = list(self._workflows().find({}))
            run_counts: dict[str, int] = {}
            for run in self._runs().find({}):
                workflow_id = str(run.get("workflow_id") or "")
                if workflow_id:
                    run_counts[workflow_id] = run_counts.get(workflow_id, 0) + 1
        workflows: list[Workflow] = []
        for document in documents:
            payload = document.get("payload")
            if isinstance(payload, dict):
                workflow = Workflow.model_validate(payload)
            else:
                workflow = Workflow.model_validate_json(str(payload))
            workflow.run_count = int(run_counts.get(workflow.id, 0))
            workflows.append(workflow)
        workflows.sort(key=lambda item: item.updated_at, reverse=True)
        return workflows

    def get_workflow(self, workflow_id: str) -> Workflow | None:
        with self._lock:
            document = self._workflows().find_one({"_id": workflow_id})
        if not document:
            return None
        payload = document.get("payload")
        if isinstance(payload, dict):
            return Workflow.model_validate(payload)
        return Workflow.model_validate_json(str(payload))

    def save_workflow(self, workflow: Workflow) -> Workflow:
        document = {
            "_id": workflow.id,
            "updated_at": workflow.updated_at.isoformat(),
            "payload": workflow.model_dump(mode="json"),
        }
        with self._lock:
            self._workflows().replace_one({"_id": workflow.id}, document, upsert=True)
        return workflow

    def delete_workflow(self, workflow_id: str) -> bool:
        with self._lock:
            result = self._workflows().delete_one({"_id": workflow_id})
            self._runs().delete_many({"workflow_id": workflow_id})
            self._ignored().delete_many({"workflow_id": workflow_id})
        return getattr(result, "deleted_count", 0) > 0

    def list_ignored_part_rules(self, workflow_id: str) -> list[WorkflowIgnoredPartRule]:
        with self._lock:
            documents = list(self._ignored().find({"workflow_id": workflow_id}))
        rules = [
            WorkflowIgnoredPartRule.model_validate(
                {
                    "workflow_id": document.get("workflow_id"),
                    "part_number": document.get("part_number"),
                    "reason": document.get("reason"),
                    "ignored_at": document.get("ignored_at"),
                }
            )
            for document in documents
        ]
        rules.sort(key=lambda item: (item.ignored_at, item.part_number), reverse=True)
        return rules

    def save_ignored_part_rule(self, rule: WorkflowIgnoredPartRule) -> WorkflowIgnoredPartRule:
        document_id = f"{rule.workflow_id}:{rule.part_number}"
        document = {
            "_id": document_id,
            "workflow_id": rule.workflow_id,
            "part_number": rule.part_number,
            "reason": rule.reason,
            "ignored_at": rule.ignored_at.isoformat(),
        }
        with self._lock:
            self._ignored().replace_one({"_id": document_id}, document, upsert=True)
        return rule

    def delete_ignored_part_rule(self, workflow_id: str, part_number: str) -> bool:
        document_id = f"{workflow_id}:{part_number}"
        with self._lock:
            result = self._ignored().delete_one({"_id": document_id})
        return getattr(result, "deleted_count", 0) > 0

    def list_runs(self, workflow_id: str | None = None, limit: int = 30) -> list[WorkflowRun]:
        query: dict[str, Any] = {}
        if workflow_id:
            query["workflow_id"] = workflow_id
        with self._lock:
            cursor = self._runs().find(query).sort("created_at", -1).limit(max(0, limit))
            documents = list(cursor)
        return [self._run_from_document(document) for document in documents]

    def list_runs_in_range(
        self,
        workflow_id: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> list[WorkflowRun]:
        query: dict[str, Any] = {}
        if workflow_id:
            query["workflow_id"] = workflow_id
        created_filter: dict[str, Any] = {}
        if created_from:
            created_filter["$gte"] = created_from
        if created_to:
            created_filter["$lte"] = created_to
        if created_filter:
            query["created_at"] = created_filter
        with self._lock:
            documents = list(self._runs().find(query).sort("created_at", -1))
        return [self._run_from_document(document) for document in documents]

    def get_run(self, run_id: str) -> WorkflowRun | None:
        with self._lock:
            document = self._runs().find_one({"_id": run_id})
        return self._run_from_document(document) if document else None

    def delete_runs(self, run_ids: list[str]) -> int:
        normalized_ids = list(dict.fromkeys(run_id.strip() for run_id in run_ids if run_id.strip()))
        if not normalized_ids:
            return 0
        with self._lock:
            result = self._runs().delete_many({"_id": {"$in": normalized_ids}})
        return int(getattr(result, "deleted_count", 0))

    def save_run(self, run: WorkflowRun) -> WorkflowRun:
        document = {
            "_id": run.id,
            "workflow_id": run.workflow_id,
            "created_at": run.created_at.isoformat(),
            "payload": run.model_dump(mode="json"),
        }
        with self._lock:
            self._runs().replace_one({"_id": run.id}, document, upsert=True)
            # Keep the newest 500 runs overall (same cap as sqlite).
            all_runs = list(self._runs().find({}).sort("created_at", -1))
            stale_ids = [str(item.get("_id")) for item in all_runs[500:]]
            if stale_ids:
                self._runs().delete_many({"_id": {"$in": stale_ids}})
        return run

    @staticmethod
    def _run_from_document(document: dict[str, Any] | None) -> WorkflowRun | None:
        if not document:
            return None
        payload = document.get("payload")
        if isinstance(payload, dict):
            return WorkflowRun.model_validate(payload)
        return WorkflowRun.model_validate_json(str(payload))
