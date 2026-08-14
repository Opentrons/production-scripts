#!/usr/bin/env python3
"""Migrate production SQLite data into MongoDB without overwriting existing docs.

Safe defaults:
- Never drops MongoDB collections
- Never deletes existing Mongo documents
- Inserts only when _id (or auth username_key) is absent
- Optional --purge-sqlite removes migrated production sqlite files after success

Usage (on the server, with backend env loaded):

  cd /opt/production-platform
  uv run --package production-backend python apps/backend/scripts/migrate_sqlite_to_mongodb.py
  uv run --package production-backend python apps/backend/scripts/migrate_sqlite_to_mongodb.py --purge-sqlite
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

# Ensure `src` is importable when invoked as a script.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = BACKEND_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from core import config  # noqa: E402
from core.database import mongodb  # noqa: E402
from core.logging import get_logger  # noqa: E402
from modules.auth.mongo_store import MongoAuthStore  # noqa: E402

logger = get_logger(__name__)

def _cfg(name: str, default: str) -> str:
    return str(getattr(config, name, default))


PLATFORM_COLLECTIONS = (
    _cfg("ROBOT_SCAN_GATEWAY_COLLECTION", "robot_scan_gateways"),
    _cfg("ROBOT_SCAN_CACHE_COLLECTION", "robot_scan_cache"),
    _cfg("UPLOAD_FINISH_SETTINGS_COLLECTION", "upload_finish_settings"),
    _cfg("ROBOT_SSH_COMMAND_COLLECTION", "robot_ssh_commands"),
    _cfg("ROBOT_VERSION_RECORD_COLLECTION", "robot_version_records"),
    _cfg("SYSTEM_HEALTH_COLLECTION", "system_health"),
    _cfg("DATA_UPLOAD_STATUS_COLLECTION", "data_upload_status"),
    _cfg("DATA_UPLOAD_RECORD_COLLECTION", "data_upload_records"),
    _cfg("PROTOCOL_MONITOR_ROOM_COLLECTION", "protocol_monitor_rooms"),
    _cfg("AGENT_KNOWLEDGE_COLLECTION", "agent_knowledge"),
    _cfg("AGENT_SCHEDULE_COLLECTION", "agent_schedules"),
    _cfg("AGENT_SCHEDULE_RUN_COLLECTION", "agent_schedule_runs"),
    _cfg("FILE_RESOURCE_PROJECTS_COLLECTION", "file_resource_projects"),
    _cfg("FILE_RESOURCE_VERSIONS_COLLECTION", "file_resource_versions"),
    _cfg("ROBOT_LOG_DOWNLOAD_COLLECTION", "robot_log_download_records"),
    _cfg("PRODUCT_MANAGEMENT_COLLECTION", "product_management"),
    _cfg("UNIT_TRACKER_COLLECTION", "unit_tracker_rows"),
)

PURGE_CANDIDATES = (
    config.AUTH_DB_PATH,
    config.DB_BUSINESS_DIR / "platform.sqlite3",
    config.DB_BUSINESS_DIR / "workflows.sqlite3",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--auth-db",
        type=Path,
        default=config.AUTH_DB_PATH,
        help="Path to auth.sqlite3 (default: production auth path)",
    )
    parser.add_argument(
        "--platform-db",
        type=Path,
        default=config.DB_BUSINESS_DIR / "platform.sqlite3",
        help="Path to business platform.sqlite3",
    )
    parser.add_argument(
        "--workflows-db",
        type=Path,
        default=config.DB_BUSINESS_DIR / "workflows.sqlite3",
        help="Path to business workflows.sqlite3",
    )
    parser.add_argument(
        "--purge-sqlite",
        action="store_true",
        help="After a successful migrate, delete migrated production sqlite files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be migrated without writing to MongoDB",
    )
    return parser.parse_args()


def _connect_mongo():
    if mongodb.client is None and not mongodb.connect():
        raise SystemExit("MongoDB is unavailable; aborting migration")
    return mongodb.client[config.MESSAGE_COLLECTION]


def _load_platform_docs(path: Path) -> dict[str, list[dict[str, Any]]]:
    if not path.exists():
        return {}
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "documents" not in tables:
            return {}
        columns = {row[1] for row in connection.execute("PRAGMA table_info(documents)")}
        id_column = "doc_key" if "doc_key" in columns else "document_id"
        rows = connection.execute(
            f"SELECT collection, {id_column} AS document_id, payload FROM documents"
        ).fetchall()
    finally:
        connection.close()

    by_collection: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        collection = str(row["collection"] or "")
        payload_raw = row["payload"]
        try:
            payload = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw
        except Exception:
            logger.warning("Skipping corrupt document in %s/%s", collection, row["document_id"])
            continue
        if not isinstance(payload, dict):
            continue
        payload = dict(payload)
        payload.setdefault("_id", row["document_id"])
        by_collection.setdefault(collection, []).append(payload)
    return by_collection


def _insert_if_absent(collection, document: dict[str, Any], *, dry_run: bool) -> str:
    doc_id = document.get("_id")
    if doc_id is None:
        return "skipped_missing_id"
    existing = collection.find_one({"_id": doc_id}, projection={"_id": 1})
    if existing is not None:
        return "skipped_exists"
    if dry_run:
        return "would_insert"
    collection.insert_one(document)
    return "inserted"


def migrate_platform(database, path: Path, *, dry_run: bool) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    documents_by_collection = _load_platform_docs(path)
    for name, documents in documents_by_collection.items():
        if name not in PLATFORM_COLLECTIONS and name not in {
            "workflows",
            "workflow_runs",
            "workflow_ignored_part_rules",
            "auth_users",
            "auth_sessions",
        }:
            # Still migrate unknown business collections safely.
            pass
        counts = {"inserted": 0, "skipped_exists": 0, "would_insert": 0, "skipped_missing_id": 0}
        mongo_collection = database[name]
        for document in documents:
            result = _insert_if_absent(mongo_collection, document, dry_run=dry_run)
            counts[result] = counts.get(result, 0) + 1
        summary[name] = counts
        logger.info("platform.%s -> %s", name, counts)
    return summary


def migrate_auth(database, path: Path, *, dry_run: bool) -> dict[str, dict[str, int]]:
    summary = {
        "auth_users": {"inserted": 0, "skipped_exists": 0, "would_insert": 0},
        "auth_sessions": {"inserted": 0, "skipped_exists": 0, "would_insert": 0},
    }
    if not path.exists():
        logger.info("Auth sqlite missing at %s; skipping", path)
        return summary

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        users = connection.execute("SELECT * FROM auth_users").fetchall()
        sessions = connection.execute("SELECT * FROM auth_sessions").fetchall()
    except sqlite3.Error as exc:
        logger.warning("Failed reading auth sqlite %s: %s", path, exc)
        return summary
    finally:
        connection.close()

    users_collection = database[MongoAuthStore.USERS]
    sessions_collection = database[MongoAuthStore.SESSIONS]
    if not dry_run:
        users_collection.create_index("username_key", unique=True)
        sessions_collection.create_index("user_id")
        sessions_collection.create_index("expires_at")

    for row in users:
        username = str(row["username"] or "")
        document = {
            "_id": str(row["id"]),
            "username": username,
            "username_key": username.strip().casefold(),
            "display_name": str(row["display_name"] or ""),
            "role": str(row["role"] or ""),
            "password_hash": str(row["password_hash"] or ""),
            "disabled": bool(row["disabled"]),
            "token_version": int(row["token_version"] or 1),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "last_login_at": row["last_login_at"],
        }
        by_id = users_collection.find_one({"_id": document["_id"]}, projection={"_id": 1})
        by_name = users_collection.find_one(
            {"username_key": document["username_key"]}, projection={"_id": 1}
        )
        if by_id or by_name:
            summary["auth_users"]["skipped_exists"] += 1
            continue
        if dry_run:
            summary["auth_users"]["would_insert"] += 1
            continue
        users_collection.insert_one(document)
        summary["auth_users"]["inserted"] += 1

    for row in sessions:
        document = {
            "_id": str(row["id"]),
            "user_id": str(row["user_id"]),
            "refresh_token_hash": str(row["refresh_token_hash"] or ""),
            "expires_at": row["expires_at"],
            "created_at": row["created_at"],
            "last_used_at": row["last_used_at"],
            "revoked_at": row["revoked_at"],
            "user_agent": str(row["user_agent"] or ""),
            "ip_address": str(row["ip_address"] or ""),
        }
        result = _insert_if_absent(sessions_collection, document, dry_run=dry_run)
        key = "would_insert" if result == "would_insert" else (
            "inserted" if result == "inserted" else "skipped_exists"
        )
        summary["auth_sessions"][key] += 1

    logger.info("auth -> %s", summary)
    return summary


def migrate_workflows(database, path: Path, *, dry_run: bool) -> dict[str, dict[str, int]]:
    summary = {
        "workflows": {"inserted": 0, "skipped_exists": 0, "would_insert": 0},
        "workflow_runs": {"inserted": 0, "skipped_exists": 0, "would_insert": 0},
        "workflow_ignored_part_rules": {"inserted": 0, "skipped_exists": 0, "would_insert": 0},
    }
    if not path.exists():
        logger.info("Workflows sqlite missing at %s; skipping", path)
        return summary

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        workflows = connection.execute("SELECT id, updated_at, payload FROM workflows").fetchall()
        runs = connection.execute(
            "SELECT id, workflow_id, created_at, payload FROM workflow_runs"
        ).fetchall()
        rules = connection.execute(
            "SELECT workflow_id, part_number, reason, ignored_at FROM workflow_ignored_part_rules"
        ).fetchall()
    except sqlite3.Error as exc:
        logger.warning("Failed reading workflows sqlite %s: %s", path, exc)
        return summary
    finally:
        connection.close()

    for row in workflows:
        try:
            payload = json.loads(row["payload"])
        except Exception:
            continue
        document = {
            "_id": str(row["id"]),
            "updated_at": row["updated_at"],
            "payload": payload,
        }
        result = _insert_if_absent(database["workflows"], document, dry_run=dry_run)
        key = "would_insert" if result == "would_insert" else (
            "inserted" if result == "inserted" else "skipped_exists"
        )
        summary["workflows"][key] += 1

    for row in runs:
        try:
            payload = json.loads(row["payload"])
        except Exception:
            continue
        document = {
            "_id": str(row["id"]),
            "workflow_id": str(row["workflow_id"]),
            "created_at": row["created_at"],
            "payload": payload,
        }
        result = _insert_if_absent(database["workflow_runs"], document, dry_run=dry_run)
        key = "would_insert" if result == "would_insert" else (
            "inserted" if result == "inserted" else "skipped_exists"
        )
        summary["workflow_runs"][key] += 1

    for row in rules:
        document_id = f"{row['workflow_id']}:{row['part_number']}"
        document = {
            "_id": document_id,
            "workflow_id": str(row["workflow_id"]),
            "part_number": str(row["part_number"]),
            "reason": str(row["reason"] or ""),
            "ignored_at": row["ignored_at"],
        }
        result = _insert_if_absent(
            database["workflow_ignored_part_rules"], document, dry_run=dry_run
        )
        key = "would_insert" if result == "would_insert" else (
            "inserted" if result == "inserted" else "skipped_exists"
        )
        summary["workflow_ignored_part_rules"][key] += 1

    logger.info("workflows -> %s", summary)
    return summary


def purge_sqlite_files(*, dry_run: bool) -> list[str]:
    removed: list[str] = []
    for path in PURGE_CANDIDATES:
        if not path.exists():
            continue
        if dry_run:
            removed.append(f"would_remove:{path}")
            continue
        path.unlink()
        # Also remove WAL/SHM sidecars when present.
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(path) + suffix)
            if sidecar.exists():
                sidecar.unlink()
        removed.append(str(path))
        logger.info("Removed sqlite file %s", path)
    return removed


def main() -> int:
    args = parse_args()
    if config.use_sqlite_persistence():
        raise SystemExit(
            "Refuse to migrate while simulating mode is enabled. "
            "Set db-storage/mode.json simulating=false first."
        )

    database = _connect_mongo()
    report = {
        "auth": migrate_auth(database, args.auth_db, dry_run=args.dry_run),
        "platform": migrate_platform(database, args.platform_db, dry_run=args.dry_run),
        "workflows": migrate_workflows(database, args.workflows_db, dry_run=args.dry_run),
    }
    if args.purge_sqlite:
        report["purged"] = purge_sqlite_files(dry_run=args.dry_run)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
