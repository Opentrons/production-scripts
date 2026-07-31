from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from typing import Any, Iterator

from workflows.models import Workflow, WorkflowIgnoredPartRule, WorkflowRun


class WorkflowRepository:
    """SQLite-backed workflow storage with optional one-time JSON migration."""

    def __init__(self, store_path: Path, legacy_json_path: Path | None = None) -> None:
        self.store_path = store_path
        self.legacy_json_path = legacy_json_path
        self._lock = RLock()
        self._initialize_database()

    def list_workflows(self) -> list[Workflow]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT workflows.payload, COUNT(workflow_runs.id)
                FROM workflows
                LEFT JOIN workflow_runs ON workflow_runs.workflow_id = workflows.id
                GROUP BY workflows.id
                ORDER BY workflows.updated_at DESC
                """
            ).fetchall()
        workflows = []
        for payload, run_count in rows:
            workflow = Workflow.model_validate_json(payload)
            workflow.run_count = int(run_count)
            workflows.append(workflow)
        return workflows

    def get_workflow(self, workflow_id: str) -> Workflow | None:
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT payload FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
        return Workflow.model_validate_json(row[0]) if row else None

    def save_workflow(self, workflow: Workflow) -> Workflow:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workflows (id, updated_at, payload) VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET updated_at = excluded.updated_at, payload = excluded.payload
                """,
                (workflow.id, workflow.updated_at.isoformat(), workflow.model_dump_json()),
            )
        return workflow

    def delete_workflow(self, workflow_id: str) -> bool:
        with self._lock, self._connect() as connection:
            cursor = connection.execute("DELETE FROM workflows WHERE id = ?", (workflow_id,))
        return cursor.rowcount > 0

    def list_ignored_part_rules(self, workflow_id: str) -> list[WorkflowIgnoredPartRule]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT workflow_id, part_number, reason, ignored_at
                FROM workflow_ignored_part_rules
                WHERE workflow_id = ?
                ORDER BY ignored_at DESC, part_number ASC
                """,
                (workflow_id,),
            ).fetchall()
        return [
            WorkflowIgnoredPartRule(
                workflow_id=row[0],
                part_number=row[1],
                reason=row[2],
                ignored_at=row[3],
            )
            for row in rows
        ]

    def save_ignored_part_rule(self, rule: WorkflowIgnoredPartRule) -> WorkflowIgnoredPartRule:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workflow_ignored_part_rules (
                    workflow_id, part_number, reason, ignored_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(workflow_id, part_number) DO UPDATE SET
                    reason = excluded.reason,
                    ignored_at = excluded.ignored_at
                """,
                (
                    rule.workflow_id,
                    rule.part_number,
                    rule.reason,
                    rule.ignored_at.isoformat(),
                ),
            )
        return rule

    def delete_ignored_part_rule(self, workflow_id: str, part_number: str) -> bool:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM workflow_ignored_part_rules
                WHERE workflow_id = ? AND part_number = ?
                """,
                (workflow_id, part_number),
            )
        return cursor.rowcount > 0

    def list_runs(self, workflow_id: str | None = None, limit: int = 30) -> list[WorkflowRun]:
        query = "SELECT payload FROM workflow_runs"
        parameters: list[Any] = []
        if workflow_id:
            query += " WHERE workflow_id = ?"
            parameters.append(workflow_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        parameters.append(max(0, limit))
        with self._lock, self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [WorkflowRun.model_validate_json(row[0]) for row in rows]

    def list_runs_in_range(
        self,
        workflow_id: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> list[WorkflowRun]:
        query = "SELECT payload FROM workflow_runs"
        clauses: list[str] = []
        parameters: list[Any] = []
        if workflow_id:
            clauses.append("workflow_id = ?")
            parameters.append(workflow_id)
        if created_from:
            clauses.append("created_at >= ?")
            parameters.append(created_from)
        if created_to:
            clauses.append("created_at <= ?")
            parameters.append(created_to)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC"
        with self._lock, self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [WorkflowRun.model_validate_json(row[0]) for row in rows]

    def get_run(self, run_id: str) -> WorkflowRun | None:
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT payload FROM workflow_runs WHERE id = ?", (run_id,)).fetchone()
        return WorkflowRun.model_validate_json(row[0]) if row else None

    def delete_runs(self, run_ids: list[str]) -> int:
        normalized_ids = list(dict.fromkeys(run_id.strip() for run_id in run_ids if run_id.strip()))
        if not normalized_ids:
            return 0
        placeholders = ",".join("?" for _ in normalized_ids)
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                f"DELETE FROM workflow_runs WHERE id IN ({placeholders})",
                normalized_ids,
            )
        return cursor.rowcount

    def save_run(self, run: WorkflowRun) -> WorkflowRun:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workflow_runs (id, workflow_id, created_at, payload) VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    workflow_id = excluded.workflow_id,
                    created_at = excluded.created_at,
                    payload = excluded.payload
                """,
                (run.id, run.workflow_id, run.created_at.isoformat(), run.model_dump_json()),
            )
            connection.execute(
                """
                DELETE FROM workflow_runs WHERE id IN (
                    SELECT id FROM workflow_runs ORDER BY created_at DESC LIMIT -1 OFFSET 500
                )
                """
            )
        return run

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.store_path, timeout=10)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 10000")
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize_database(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS workflows (
                    id TEXT PRIMARY KEY,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS workflow_runs (
                    id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_workflow_runs_workflow_created
                    ON workflow_runs(workflow_id, created_at DESC);
                CREATE TABLE IF NOT EXISTS workflow_ignored_part_rules (
                    workflow_id TEXT NOT NULL,
                    part_number TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    ignored_at TEXT NOT NULL,
                    PRIMARY KEY (workflow_id, part_number),
                    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_workflow_ignored_part_rules_workflow_time
                    ON workflow_ignored_part_rules(workflow_id, ignored_at DESC);
                CREATE TABLE IF NOT EXISTS workflow_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            migrated = connection.execute(
                "SELECT 1 FROM workflow_metadata WHERE key = 'legacy_json_migrated'"
            ).fetchone()
            if not migrated:
                record_count = connection.execute(
                    "SELECT (SELECT COUNT(*) FROM workflows) + (SELECT COUNT(*) FROM workflow_runs)"
                ).fetchone()[0]
                if record_count == 0:
                    self._migrate_legacy_json(connection)
                connection.execute(
                    "INSERT INTO workflow_metadata (key, value) VALUES ('legacy_json_migrated', '1')"
                )

    def _migrate_legacy_json(self, connection: sqlite3.Connection) -> None:
        if self.legacy_json_path is None or not self.legacy_json_path.exists():
            return
        try:
            document = json.loads(self.legacy_json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        for item in document.get("workflows", []):
            try:
                workflow = Workflow.model_validate(item)
            except (TypeError, ValueError):
                continue
            connection.execute(
                "INSERT OR IGNORE INTO workflows (id, updated_at, payload) VALUES (?, ?, ?)",
                (workflow.id, workflow.updated_at.isoformat(), workflow.model_dump_json()),
            )

        for item in document.get("runs", []):
            try:
                run = WorkflowRun.model_validate(item)
            except (TypeError, ValueError):
                continue
            if connection.execute("SELECT 1 FROM workflows WHERE id = ?", (run.workflow_id,)).fetchone():
                connection.execute(
                    "INSERT OR IGNORE INTO workflow_runs (id, workflow_id, created_at, payload) VALUES (?, ?, ?, ?)",
                    (run.id, run.workflow_id, run.created_at.isoformat(), run.model_dump_json()),
                )
