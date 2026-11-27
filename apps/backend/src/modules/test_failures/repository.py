from __future__ import annotations

import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from .parser import digest, shanghai_test_date
from .products import normalize_product, product_from_serial
from .reference import reference_stage_volume


INDEX_VERSION = 3
WRITEBACK_VERSION = 3


class NotFoundError(LookupError):
    pass


class ConflictError(ValueError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def public_confirmation(record: dict) -> dict:
    result = {key: record[key] for key in ("id", "text", "created_by", "created_by_name", "created_at")}
    if name := record.get("confirmed_by_name"):
        result["confirmed_by_name"] = name
    return result


def evidence_version(report: dict) -> str:
    """Refresh evidence/attachments without reopening an unchanged QC confirmation."""
    fields = {key: report.get(key) for key in (
        "revision", "attachment_paths", "attachment_signatures", "attachment_hashes", "parse_status", "source_format",
    )}
    if report.get("test_report_fallback"):
        fields["test_report_fallback"] = report["test_report_fallback"]
    return digest(fields)


def report_summary(report: dict) -> dict:
    keys = ("id", "revision", "sn", "product", "report_run_id", "mode", "test_time", "kind", "stage",
            "report_role", "reference_tip_volume_ul", "run_group_id", "report_folder", "source_name",
            "summary", "failure_count", "parse_status", "source_format")
    summary = {"evidence_version": evidence_version(report), **{key: report.get(key) for key in keys}}
    if report["source_format"] == "test_report" or report.get("test_report_fallback"):
        summary["report_url"] = report.get("report_url") or (report.get("test_report_fallback") or {}).get("url")
    return summary


def _report_source(report: dict) -> str:
    source = report.get("source_group")
    if source:
        return str(source)
    paths = report.get("attachment_paths", {})
    path = paths.get("json") or paths.get("log")
    if path:
        return str(Path(path).with_suffix(""))
    return "legacy:" + str(report.get("id") or report.get("source_name") or "unknown")


def _folder_scope(source: str) -> tuple[str, str]:
    """Real directories are independent; loose legacy files use their stem."""
    parent = Path(source).parent.as_posix()
    return ("folder", parent) if parent != "." else ("source", source)


def _report_identity(report: dict, source_key: str) -> str:
    run_id, mode, report_run_id = (report.get(key) for key in ("run_id", "mode", "report_run_id"))
    # Both report identity and row membership are bounded by the archive folder.
    # Matching run fields in another folder never imply shared evidence.
    main_identity = digest([run_id, mode, report_run_id or source_key]) if run_id else "source:" + source_key
    volume = reference_stage_volume(report.get("stage"))
    identity = digest([main_identity, "right_reference", volume]) if volume is not None else main_identity
    return digest([_folder_scope(source_key), identity])


def _report_metadata(report: dict, root_key: str) -> dict:
    volume = reference_stage_volume(report.get("stage"))
    report["report_role"] = "right_reference" if volume is not None else "main"
    report["reference_tip_volume_ul"] = volume
    source = _report_source(report)
    scope = _folder_scope(source)
    report["report_folder"] = report["source_name"] if report.get("source_format") == "test_report" else scope[1]
    run_id = report.get("run_id")
    group = [run_id, report.get("mode"), report.get("report_run_id") or source] if run_id else ["source", source]
    report["run_group_id"] = digest([root_key, scope, group])
    return report


def _read_report(payload: str, root_key: str) -> dict:
    report = _report_metadata(json.loads(payload), root_key)
    # Display upgrades must also apply to cached reports without rewriting their
    # evidence, identity, or historical confirmation coverage.
    report["product"] = normalize_product(report.get("product")) or product_from_serial(report.get("sn", ""))
    return report


def _search_values(value: object) -> Iterator[str]:
    """Flatten evidence values without indexing storage metadata or field names."""
    if isinstance(value, dict):
        for item in value.values():
            yield from _search_values(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _search_values(item)
    elif value is not None:
        yield str(value)


def _failure_search_text(report: dict) -> str:
    values = [report.get("summary"), report.get("failures"), report.get("runtime_error"), report.get("last_failure")]
    for name, state in report.get("tests", {}).items():
        if state.get("status") in {"failed", "execution_error", "exception", "not_run_due_to_previous_failure"}:
            values.extend((name, state.get("error"), state.get("blocking_stage"), state.get("last_handled_exception")))
    return " ".join(_search_values(values)).casefold()


class Repository:
    def __init__(self, database_path: Path, root_key: str, *, first_visible_test_date: str = ""):
        self.path = Path(database_path)
        self.root_key = root_key
        self.first_visible_test_date = first_visible_test_date

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=15)) as connection, connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA busy_timeout=15000")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS failure_reports (
                    id TEXT PRIMARY KEY, root_key TEXT NOT NULL, identity_key TEXT NOT NULL,
                    payload TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS failure_identity ON failure_reports(root_key, identity_key);
                CREATE TABLE IF NOT EXISTS failure_report_revisions (
                    report_id TEXT NOT NULL, revision TEXT NOT NULL, payload TEXT NOT NULL,
                    recorded_at TEXT NOT NULL, PRIMARY KEY(report_id, revision)
                );
                CREATE TABLE IF NOT EXISTS failure_sources (
                    root_key TEXT NOT NULL, source_key TEXT NOT NULL, report_id TEXT NOT NULL,
                    signature TEXT NOT NULL, PRIMARY KEY(root_key, source_key)
                );
                CREATE TABLE IF NOT EXISTS failure_report_aliases (
                    root_key TEXT NOT NULL, alias_id TEXT NOT NULL, report_id TEXT NOT NULL,
                    PRIMARY KEY(root_key, alias_id)
                );
                CREATE TABLE IF NOT EXISTS repair_confirmations (
                    id TEXT PRIMARY KEY, root_key TEXT NOT NULL, device_id TEXT NOT NULL,
                    text TEXT NOT NULL, created_by TEXT NOT NULL, created_by_name TEXT NOT NULL,
                    created_at TEXT NOT NULL, coverage TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS repair_device ON repair_confirmations(root_key, device_id, created_at);
                CREATE TABLE IF NOT EXISTS repair_confirmation_reviewers (
                    confirmation_id TEXT PRIMARY KEY, confirmed_by_name TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS failure_index_versions (
                    root_key TEXT PRIMARY KEY, version INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS failure_writebacks (
                    root_key TEXT NOT NULL, database_name TEXT NOT NULL, report_id TEXT NOT NULL,
                    report_updated_at TEXT NOT NULL, attempts INTEGER NOT NULL, retry_at REAL,
                    PRIMARY KEY(root_key, database_name, report_id)
                );
            """)
            yield connection

    def prepare_scan(self) -> None:
        """Separate legacy folders/checkpoints on scan, preserving audit IDs.

        An old index may have collapsed several source packages into one report.
        Its ID remains with the package represented by the current payload. The
        other sources are reparsed into their own IDs; historical revisions and
        confirmation coverage are deliberately neither rewritten nor copied.
        """
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            version = connection.execute("SELECT version FROM failure_index_versions WHERE root_key=?", (self.root_key,)).fetchone()
            if version and version["version"] >= INDEX_VERSION:
                return
            for row in connection.execute("SELECT id,payload FROM failure_reports WHERE root_key=?", (self.root_key,)).fetchall():
                payload = json.loads(row["payload"])
                source = _report_source({**payload, "id": row["id"]})
                payload["source_group"] = source
                # Old multi-source merges can already contain foreign optional
                # attachments. Keep only this payload's own package, even when a
                # missing source cannot be recovered during this scan.
                paths = {kind: path for kind, path in payload.get("attachment_paths", {}).items()
                         if kind == "encoder" and path == source + ".encoder.csv"
                         or kind in {"json", "log"} and Path(path).suffix.lower() == "." + kind and str(Path(path).with_suffix("")) == source}
                payload["attachment_paths"] = paths
                for field in ("attachment_signatures", "attachment_hashes"):
                    payload[field] = {kind: value for kind, value in payload.get(field, {}).items() if kind in paths}
                _report_metadata(payload, self.root_key)
                connection.execute("UPDATE failure_reports SET identity_key=?,payload=? WHERE root_key=? AND id=?",
                                   (_report_identity(payload, source), json.dumps(payload, ensure_ascii=False, allow_nan=False), self.root_key, row["id"]))
            # Invalidating signatures also reparses sources whose bytes have not
            # changed. It happens once per root, not on read-only list requests.
            connection.execute("UPDATE failure_sources SET signature='legacy:' || signature WHERE root_key=?", (self.root_key,))
            connection.execute("INSERT INTO failure_index_versions VALUES (?,?) ON CONFLICT(root_key) DO UPDATE SET version=excluded.version",
                               (self.root_key, INDEX_VERSION))

    def source(self, source_key: str) -> dict | None:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM failure_sources WHERE root_key=? AND source_key=?", (self.root_key, source_key)).fetchone()
            return dict(row) if row else None

    def upsert(self, source_key: str, signature: str, payload: dict, attachments: dict, *, present_kinds: set[str] | None = None) -> str:
        identity_key = _report_identity(payload, source_key)
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            source = connection.execute("SELECT report_id FROM failure_sources WHERE root_key=? AND source_key=?", (self.root_key, source_key)).fetchone()
            canonical = connection.execute("SELECT id,payload FROM failure_reports WHERE root_key=? AND identity_key=?", (self.root_key, identity_key)).fetchone()
            if source:
                old = connection.execute("SELECT payload FROM failure_reports WHERE root_key=? AND id=?", (self.root_key, source["report_id"])).fetchone()
                old_payload = json.loads(old["payload"]) if old else {}
                # A source may be overwritten by a later test. Missing identity
                # fields may be enriched by JSON, but known IDs cannot change.
                if _folder_scope(_report_source(old_payload)) != _folder_scope(source_key) or reference_stage_volume(old_payload.get("stage")) != reference_stage_volume(payload.get("stage")) or any(old_payload.get(key) and payload.get(key) and old_payload[key] != payload[key]
                       for key in ("run_id", "report_run_id")) or (
                    old_payload.get("mode") not in (None, "", "unknown") and payload.get("mode") not in (None, "", "unknown") and old_payload["mode"] != payload["mode"]
                ):
                    source = None
            report_id = source["report_id"] if source else canonical["id"] if canonical else uuid4().hex
            if source and canonical and source["report_id"] != canonical["id"]:
                # A copied log can precede its JSON identity. Merge the aliases and
                # carry historical confirmation coverage to the surviving report.
                removed_id = source["report_id"]
                report_id = canonical["id"]
                for confirmation in connection.execute("SELECT id,coverage FROM repair_confirmations WHERE root_key=?", (self.root_key,)).fetchall():
                    coverage = json.loads(confirmation["coverage"])
                    if removed_id in coverage:
                        coverage.setdefault(report_id, coverage.pop(removed_id))
                        connection.execute("UPDATE repair_confirmations SET coverage=? WHERE id=?", (json.dumps(coverage), confirmation["id"]))
                connection.execute("UPDATE failure_sources SET report_id=? WHERE root_key=? AND report_id=?", (report_id, self.root_key, removed_id))
                connection.execute("UPDATE failure_report_aliases SET report_id=? WHERE root_key=? AND report_id=?", (report_id, self.root_key, removed_id))
                connection.execute("INSERT OR REPLACE INTO failure_report_aliases VALUES (?,?,?)", (self.root_key, removed_id, report_id))
                connection.execute("DELETE FROM failure_reports WHERE id=? AND root_key=?", (removed_id, self.root_key))
            previous = connection.execute("SELECT payload FROM failure_reports WHERE id=? AND root_key=?", (report_id, self.root_key)).fetchone()
            if previous:
                previous_payload = json.loads(previous["payload"])
                same_source = previous_payload.get("source_group") == source_key
                incoming_signatures = payload.get("attachment_signatures", {})
                incoming_hashes = payload.get("attachment_hashes", {})
                if not same_source and (payload.get("kind") == "incomplete" or previous_payload.get("source_format") == "json" and payload.get("source_format") == "log"):
                    # A partial duplicate cannot replace the selected structured
                    # package or contribute attachments with a different stem.
                    connection.execute("INSERT INTO failure_sources VALUES (?,?,?,?) ON CONFLICT(root_key,source_key) DO UPDATE SET report_id=excluded.report_id,signature=excluded.signature",
                                       (self.root_key, source_key, report_id, signature))
                    return report_id
                if payload.get("kind") == "incomplete" and previous_payload.get("kind") != "incomplete":
                    payload = {**previous_payload, "parse_status": "incomplete",
                               "warnings": list(dict.fromkeys(previous_payload.get("warnings", []) + payload.get("warnings", []) + ["更新报告暂不完整，保留上次失败证据"])),
                               "attachment_signatures": incoming_signatures, "attachment_hashes": incoming_hashes}
                    identity_key = _report_identity(payload, source_key)
                if previous_payload.get("source_format") == "json" and payload.get("source_format") == "log":
                    # A missing JSON must not downgrade already indexed structured evidence.
                    payload = {**previous_payload, "attachment_signatures": incoming_signatures, "attachment_hashes": incoming_hashes}
                    identity_key = _report_identity(payload, source_key)
                retained_paths = dict(previous_payload.get("attachment_paths", {})) if same_source else {}
                retained_signatures = dict(previous_payload.get("attachment_signatures", {})) if same_source else {}
                retained_hashes = dict(previous_payload.get("attachment_hashes", {})) if same_source else {}
                if same_source and present_kinds is not None:
                    # The current directory listing is authoritative for optional
                    # attachments. Keep old JSON metadata until valid JSON is
                    # available so a missing/corrupt upload cannot erase evidence.
                    for kind in ("log", "encoder"):
                        if kind not in present_kinds:
                            retained_paths.pop(kind, None)
                            retained_signatures.pop(kind, None)
                            retained_hashes.pop(kind, None)
                attachments = {**retained_paths, **attachments}
                payload["attachment_signatures"] = {**retained_signatures, **incoming_signatures}
                payload["attachment_hashes"] = {**retained_hashes, **incoming_hashes}
            stored = _report_metadata({**payload, "id": report_id, "attachment_paths": attachments, "source_group": source_key}, self.root_key)
            connection.execute("INSERT OR IGNORE INTO failure_report_revisions VALUES (?,?,?,?)",
                               (report_id, stored["revision"], json.dumps(stored, ensure_ascii=False, allow_nan=False), now()))
            connection.execute("INSERT INTO failure_reports VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET identity_key=excluded.identity_key,payload=excluded.payload,updated_at=excluded.updated_at",
                               (report_id, self.root_key, identity_key, json.dumps(stored, ensure_ascii=False, allow_nan=False), now()))
            connection.execute("INSERT INTO failure_sources VALUES (?,?,?,?) ON CONFLICT(root_key,source_key) DO UPDATE SET report_id=excluded.report_id,signature=excluded.signature",
                               (self.root_key, source_key, report_id, signature))
            return report_id

    def get_report(self, report_id: str) -> dict:
        with self.connection() as connection:
            alias = connection.execute("SELECT report_id FROM failure_report_aliases WHERE root_key=? AND alias_id=?", (self.root_key, report_id)).fetchone()
            if alias:
                report_id = alias["report_id"]
            row = connection.execute("SELECT payload FROM failure_reports WHERE root_key=? AND id=?", (self.root_key, report_id)).fetchone()
        if row is None:
            raise NotFoundError("未找到测试失败报告")
        return _read_report(row["payload"], self.root_key)

    def archived_reports(self) -> list[dict]:
        with self.connection() as connection:
            rows = connection.execute("""
                SELECT payload FROM failure_reports WHERE root_key = ?
                  AND json_extract(payload, '$.source_format') IN ('json', 'log')
            """, (self.root_key,)).fetchall()
        return [_read_report(row["payload"], self.root_key) for row in rows]

    def replace_mongo_reports(self, reports: list[dict], fallbacks: dict[str, dict]) -> None:
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for row in connection.execute("""
                SELECT id, payload FROM failure_reports WHERE root_key=?
                    AND json_extract(payload, '$.source_format') IN ('json', 'log')
            """, (self.root_key,)).fetchall():
                report = json.loads(row["payload"])
                fallback = fallbacks.get(row["id"])
                if fallback == report.get("test_report_fallback"):
                    continue
                if fallback:
                    report["test_report_fallback"] = fallback
                else:
                    report.pop("test_report_fallback", None)
                connection.execute("UPDATE failure_reports SET payload=? WHERE root_key=? AND id=?",
                                   (json.dumps(report, ensure_ascii=False), self.root_key, row["id"]))
            existing = {
                row["id"]: json.loads(row["payload"]) for row in connection.execute("""
                    SELECT id, payload FROM failure_reports WHERE root_key = ?
                      AND json_extract(payload, '$.source_format') = 'test_report'
                """, (self.root_key,))
            }
            for incoming in reports:
                report = _report_metadata({**incoming, "id": digest([self.root_key, incoming["id"]])}, self.root_key)
                report_id, revision = report["id"], report["revision"]
                old = existing.pop(report_id, None)
                pair = (report["mongo_confirmation"], report["mongo_confirmer"])
                same_pair = old and pair == (old.get("mongo_confirmation"), old.get("mongo_confirmer"))
                report["mongo_confirmation_revision"] = old.get("mongo_confirmation_revision") if same_pair else revision
                if old == report:
                    continue
                payload = json.dumps(report, ensure_ascii=False)
                updated_at = now()
                connection.execute("INSERT OR IGNORE INTO failure_report_revisions VALUES (?,?,?,?)",
                                   (report_id, revision, payload, updated_at))
                if old and old.get("revision") == revision and not old.get("inactive"):
                    connection.execute("UPDATE failure_reports SET payload=? WHERE root_key=? AND id=?",
                                       (payload, self.root_key, report_id))
                else:
                    connection.execute("""
                        INSERT INTO failure_reports VALUES (?,?,?,?,?)
                        ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at
                    """, (report_id, self.root_key, report_id, payload, updated_at))
            for report_id, report in existing.items():
                if not report.get("inactive"):
                    report["inactive"] = True
                    connection.execute("UPDATE failure_reports SET payload=?, updated_at=? WHERE root_key=? AND id=?",
                                       (json.dumps(report, ensure_ascii=False), now(), self.root_key, report_id))

    def pending_writebacks(self, database_name: str, timestamp: float, limit: int) -> list[tuple[dict, str, int]]:
        with self.connection() as connection:
            rows = connection.execute("""
                SELECT r.payload, r.updated_at, COALESCE(w.attempts, 0) AS attempts
                FROM failure_reports r
                LEFT JOIN failure_writebacks w ON w.root_key = r.root_key AND w.report_id = r.id
                    AND w.database_name = ? AND w.report_updated_at = r.updated_at
                WHERE r.root_key = ? AND (w.report_id IS NULL OR w.retry_at <= ?)
                    AND json_extract(r.payload, '$.parse_status') = 'ready'
                    AND json_extract(r.payload, '$.source_format') IN ('json', 'test_report')
                    AND COALESCE(json_extract(r.payload, '$.inactive'), 0) = 0
                ORDER BY COALESCE(w.retry_at, 0), r.updated_at DESC, r.id
                LIMIT ?
            """, (f"{database_name}:v{WRITEBACK_VERSION}", self.root_key, timestamp, limit)).fetchall()
        return [(_read_report(row["payload"], self.root_key), row["updated_at"], row["attempts"]) for row in rows]

    def record_writeback(
        self, database_name: str, report_id: str, updated_at: str, attempts: int, retry_at: float | None,
    ) -> None:
        with self.connection() as connection:
            connection.execute("""
                INSERT INTO failure_writebacks(root_key, database_name, report_id, report_updated_at, attempts, retry_at)
                SELECT root_key, ?, id, updated_at, ?, ? FROM failure_reports
                WHERE root_key = ? AND id = ? AND updated_at = ?
                ON CONFLICT(root_key, database_name, report_id) DO UPDATE SET
                    report_updated_at = excluded.report_updated_at, attempts = excluded.attempts, retry_at = excluded.retry_at
                WHERE failure_writebacks.report_updated_at <> excluded.report_updated_at
                    OR (failure_writebacks.retry_at IS NOT NULL AND (
                        excluded.retry_at IS NULL OR excluded.attempts > failure_writebacks.attempts
                    ))
            """, (f"{database_name}:v{WRITEBACK_VERSION}", attempts, retry_at, self.root_key, report_id, updated_at))

    def latest_report_confirmation(self, report_id: str, revision: str) -> dict | None:
        with self.connection() as connection:
            row = connection.execute("""
                SELECT c.id, c.text, c.created_by, c.created_by_name, c.created_at, reviewer.confirmed_by_name
                FROM repair_confirmations c
                LEFT JOIN repair_confirmation_reviewers reviewer ON reviewer.confirmation_id = c.id
                WHERE c.root_key = ? AND EXISTS (
                    SELECT 1 FROM json_each(c.coverage) AS covered
                    WHERE covered.key = ? AND covered.value = ?
                )
                ORDER BY c.created_at DESC, c.rowid DESC LIMIT 1
            """, (self.root_key, report_id, revision)).fetchone()
        return public_confirmation(dict(row)) if row else None

    def has_report_confirmation(self, report_id: str) -> bool:
        with self.connection() as connection:
            return connection.execute("""
                SELECT 1 FROM repair_confirmations c
                WHERE c.root_key = ? AND EXISTS (
                    SELECT 1 FROM json_each(c.coverage) AS covered WHERE covered.key = ?
                ) LIMIT 1
            """, (self.root_key, report_id)).fetchone() is not None

    def writeback_reports(self, sn: str, mode: str, run_id: str | None) -> list[dict]:
        with self.connection() as connection:
            rows = connection.execute("""
                SELECT payload FROM failure_reports WHERE root_key = ?
                    AND json_extract(payload, '$.sn') = ?
                    AND json_extract(payload, '$.mode') = ?
                    AND json_extract(payload, '$.parse_status') = 'ready'
                    AND json_extract(payload, '$.source_format') = 'json'
                    AND (? IS NULL OR TRIM(json_extract(payload, '$.report_run_id')) = ?)
            """, (self.root_key, sn, mode, run_id, run_id)).fetchall()
        return [_read_report(row["payload"], self.root_key) for row in rows]

    def _devices(self, connection: sqlite3.Connection, q: str = "") -> list[dict]:
        query = q.strip().casefold()
        reports = [_read_report(row[0], self.root_key) for row in connection.execute("""
            SELECT payload FROM failure_reports WHERE root_key=?
              AND COALESCE(json_extract(payload, '$.inactive'), 0) = 0
        """, (self.root_key,))]
        confirmations = []
        for row in connection.execute("""
            SELECT c.*, reviewer.confirmed_by_name FROM repair_confirmations c
            LEFT JOIN repair_confirmation_reviewers reviewer ON reviewer.confirmation_id = c.id
            WHERE c.root_key=? ORDER BY c.created_at DESC, c.rowid DESC
        """, (self.root_key,)):
            record = dict(row)
            record["coverage"] = json.loads(record["coverage"])
            confirmations.append(record)
        groups: dict[str, list[dict]] = {}
        for report in reports:
            has_log = report.get("source_format") == "log" or bool(report.get("attachment_paths", {}).get("log"))
            if (self.first_visible_test_date and not has_log
                    and shanghai_test_date(report.get("test_time")) < self.first_visible_test_date):
                continue
            device_id = digest([self.root_key, _folder_scope(_report_source(report))])[:32]
            groups.setdefault(device_id, []).append(report)
        devices = []
        for device_id, group in groups.items():
            run_times: dict[str, str] = {}
            for item in group:
                run = item["run_group_id"]
                run_times[run] = max(run_times.get(run, ""), item.get("test_time") or "")
            group.sort(key=lambda item: (run_times[item["run_group_id"]], item["run_group_id"], item["report_role"] == "main",
                                         -(item["reference_tip_volume_ul"] or 0), item["id"]), reverse=True)
            ids = {item["id"] for item in group}
            # Legacy confirmations were recorded against an SN-level row. Only
            # their actual evidence coverage can associate them with a folder.
            history = [item for item in confirmations if ids.intersection(item["coverage"])]
            for item in group:
                if (not history and item.get("mongo_confirmation") and item.get("mongo_confirmer")
                        and item.get("mongo_confirmation_revision") == item["revision"]):
                    history.append({
                        "id": "mongo-" + item["id"], "text": item["mongo_confirmation"],
                        "created_by": "", "created_by_name": item["mongo_confirmer"], "created_at": "",
                        "coverage": {item["id"]: item["revision"]},
                    })
            coverage = {(report_id, revision) for item in history for report_id, revision in item["coverage"].items()}
            latest = history[0] if history else None
            version = digest({"reports": sorted((item["id"], item["revision"]) for item in group), "confirmation": latest["id"] if latest else None})
            summaries = list(dict.fromkeys(text for item in group for text in item["summary"]))
            report_summaries = []
            for item in group:
                covered_by = [entry["id"] for entry in history if entry["coverage"].get(item["id"]) == item["revision"]]
                report_summaries.append({**report_summary(item), "confirmation_status": "confirmed" if covered_by else "pending", "covered_by": covered_by})
            device = {
                "id": device_id, "sn": group[0]["sn"], "product": group[0]["product"], "report_folder": group[0]["report_folder"], "last_test_at": group[0]["test_time"],
                "report_count": len(group), "unconfirmed_count": sum((item["id"], item["revision"]) not in coverage for item in group),
                "failure_types": sorted({item["kind"] for item in group}),
                "summary": summaries[:10], "summary_total": len(summaries), "summary_omitted": max(0, len(summaries) - 10),
                "version": version, "confirmation": public_confirmation(latest) if latest else None,
                "recent_confirmations": [public_confirmation(record) for record in history[:2]],
                "reports": report_summaries, "_history": history,
            }
            # Folder/SN searches apply to every package. Evidence searches retain
            # their exact matches so kind/date filters and the analysis card agree.
            identity_text = " ".join((device["sn"], device["product"], device["report_folder"])).casefold()
            device["_query_report_ids"] = [item["id"] for item in group
                                           if not query or query in identity_text or query in _failure_search_text(item)]
            devices.append(device)
        devices.sort(key=lambda item: (item.get("last_test_at") or "", item["id"]), reverse=True)
        return devices

    def devices(self, *, q: str = "") -> list[dict]:
        with self.connection() as connection:
            connection.execute("BEGIN")
            return self._devices(connection, q=q)

    def confirmations(self, device_id: str) -> dict:
        device = next((item for item in self.devices() if item["id"] == device_id), None)
        if device is None:
            raise NotFoundError("未找到失败设备")
        items = []
        with self.connection() as connection:
            connection.execute("BEGIN")
            for record in device["_history"]:
                coverage = []
                for report_id, revision in record["coverage"].items():
                    current_row = connection.execute("SELECT payload FROM failure_reports WHERE root_key=? AND id=?", (self.root_key, report_id)).fetchone()
                    current = _read_report(current_row[0], self.root_key) if current_row else None
                    archived = connection.execute("SELECT payload FROM failure_report_revisions WHERE report_id=? AND revision=?", (report_id, revision)).fetchone()
                    recorded = _read_report(archived[0], self.root_key) if archived else None
                    metadata = recorded or current or {}
                    coverage.append({"report_id": report_id, "revision": revision,
                                     **{key: metadata.get(key) for key in ("report_folder", "source_name", "report_role", "test_time")},
                                     "current": bool(current and current["revision"] == revision),
                                     "metadata_recorded": recorded is not None})
                items.append({**public_confirmation(record), "coverage": coverage})
        return {"items": items}

    def confirm(
        self, device_id: str, text: str, version: str, created_by: str, created_by_name: str,
        confirmed_by_name: str | None = None,
    ) -> dict:
        text = text.strip()
        if not text or len(text) > 4000:
            raise ValueError("测试返修确认须为 1 至 4000 字符")
        if not created_by:
            raise ValueError("请登录后保存测试返修确认")
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            device = next((item for item in self._devices(connection) if item["id"] == device_id), None)
            if device is None:
                raise NotFoundError("未找到失败设备")
            if version != device["version"]:
                raise ConflictError("报告或返修确认已更新，请刷新并核对后保存；当前输入内容请保留")
            record = {"id": uuid4().hex, "text": text, "created_by": created_by,
                      "created_by_name": created_by_name or created_by, "created_at": now()}
            coverage = {item["id"]: item["revision"] for item in device["reports"]}
            connection.execute("INSERT INTO repair_confirmations VALUES (?,?,?,?,?,?,?,?)",
                               (record["id"], self.root_key, device_id, text, created_by, record["created_by_name"], record["created_at"], json.dumps(coverage)))
            if confirmed_by_name:
                connection.execute(
                    "INSERT INTO repair_confirmation_reviewers VALUES (?,?)", (record["id"], confirmed_by_name),
                )
                record["confirmed_by_name"] = confirmed_by_name
            connection.executemany(
                "UPDATE failure_reports SET updated_at=? WHERE root_key=? AND id=?",
                [(record["created_at"], self.root_key, report_id) for report_id in coverage],
            )
            updated = next(item for item in self._devices(connection) if item["id"] == device_id)
            updated.pop("_history", None)
            updated["matched_report_ids"] = updated.pop("_query_report_ids", [])
            return {"confirmation": record, "device": updated}
