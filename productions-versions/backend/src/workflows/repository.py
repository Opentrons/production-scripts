from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from typing import Any

from workflows.models import Workflow, WorkflowRun


class WorkflowRepository:
    def __init__(self, store_path: Path) -> None:
        self.store_path = store_path
        self._lock = RLock()

    def list_workflows(self) -> list[Workflow]:
        with self._lock:
            document = self._read_document()
            return [Workflow.model_validate(item) for item in document["workflows"]]

    def get_workflow(self, workflow_id: str) -> Workflow | None:
        return next((item for item in self.list_workflows() if item.id == workflow_id), None)

    def save_workflow(self, workflow: Workflow) -> Workflow:
        with self._lock:
            document = self._read_document()
            workflows = document["workflows"]
            for index, item in enumerate(workflows):
                if item.get("id") == workflow.id:
                    workflows[index] = workflow.model_dump(mode="json")
                    break
            else:
                workflows.append(workflow.model_dump(mode="json"))
            self._write_document(document)
        return workflow

    def delete_workflow(self, workflow_id: str) -> bool:
        with self._lock:
            document = self._read_document()
            original_count = len(document["workflows"])
            document["workflows"] = [item for item in document["workflows"] if item.get("id") != workflow_id]
            if len(document["workflows"]) == original_count:
                return False
            document["runs"] = [item for item in document["runs"] if item.get("workflow_id") != workflow_id]
            self._write_document(document)
            return True

    def list_runs(self, workflow_id: str | None = None, limit: int = 30) -> list[WorkflowRun]:
        with self._lock:
            document = self._read_document()
            runs = [WorkflowRun.model_validate(item) for item in document["runs"]]
        if workflow_id:
            runs = [item for item in runs if item.workflow_id == workflow_id]
        runs.sort(key=lambda item: item.created_at, reverse=True)
        return runs[:limit]

    def save_run(self, run: WorkflowRun) -> WorkflowRun:
        with self._lock:
            document = self._read_document()
            runs = document["runs"]
            for index, item in enumerate(runs):
                if item.get("id") == run.id:
                    runs[index] = run.model_dump(mode="json")
                    break
            else:
                runs.append(run.model_dump(mode="json"))
            document["runs"] = runs[-500:]
            self._write_document(document)
        return run

    def _read_document(self) -> dict[str, list[dict[str, Any]]]:
        if not self.store_path.exists():
            return {"workflows": [], "runs": []}
        try:
            payload = json.loads(self.store_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"workflows": [], "runs": []}
        return {
            "workflows": list(payload.get("workflows", [])),
            "runs": list(payload.get("runs", [])),
        }

    def _write_document(self, document: dict[str, list[dict[str, Any]]]) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.store_path.with_suffix(".tmp")
        temporary_path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(self.store_path)
