from __future__ import annotations

import threading

from modules.workflows.service import WorkflowService


class WorkflowScheduler:
    def __init__(self, service: WorkflowService, poll_seconds: float = 5) -> None:
        self.service = service
        self.poll_seconds = max(1, poll_seconds)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="workflow-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self.poll_seconds + 1)
        self._thread = None

    def _run(self) -> None:
        while not self._stop_event.wait(self.poll_seconds):
            for workflow in self.service.list_due_workflows():
                self.service.trigger_workflow(workflow.id, "scheduled")
