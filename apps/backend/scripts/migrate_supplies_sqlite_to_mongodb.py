#!/usr/bin/env python3
"""Copy supplementary materials from SQLite into the production MongoDB collection.

The migration is idempotent by material document ID. It never drops the target
collection and never deletes documents that are not present in the source SQLite
table.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Any

from pymongo import MongoClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = BACKEND_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from core.config import MESSAGE_COLLECTION, MONGO_HOST, MONGO_URI, resolve_sqlite_path  # noqa: E402
from modules.supplies.mongo_repository import MongoSupplementaryMaterialRepository  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sqlite-path",
        type=Path,
        default=resolve_sqlite_path("supplementary_materials.sqlite3"),
        help="Source SQLite path",
    )
    parser.add_argument(
        "--mongo-uri",
        default=MONGO_URI or f"mongodb://{MONGO_HOST}:27017",
        help="Target MongoDB URI",
    )
    parser.add_argument("--database", default=MESSAGE_COLLECTION)
    parser.add_argument("--collection", default=MongoSupplementaryMaterialRepository.COLLECTION)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read and validate the source without writing MongoDB",
    )
    return parser.parse_args()


def read_source(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"SQLite file does not exist: {path}")
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, material_number, english_name, chinese_name, eid, created_at, updated_at
            FROM supplementary_materials
            ORDER BY material_number COLLATE NOCASE ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def migrate(args: argparse.Namespace) -> dict[str, int | str]:
    documents = read_source(args.sqlite_path)
    ids = [str(document.get("id") or "").strip() for document in documents]
    material_numbers = [str(document.get("material_number") or "").strip() for document in documents]
    if not documents or any(not value for value in ids + material_numbers):
        raise ValueError("Source SQLite contains no complete supplementary-material records")
    if len(ids) != len(set(ids)) or len(material_numbers) != len(set(material_numbers)):
        raise ValueError("Source SQLite contains duplicate IDs or material numbers")
    if args.dry_run:
        return {"source_count": len(documents), "target_count": -1, "written_count": 0}

    client = MongoClient(
        args.mongo_uri,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        socketTimeoutMS=10000,
    )
    try:
        client.admin.command("ping")
        collection = client[args.database][args.collection]
        collection.create_index("material_number", unique=True)
        collection.create_index("updated_at")
        written_count = 0
        for document in documents:
            mongo_document = dict(document)
            mongo_document["_id"] = mongo_document.pop("id")
            collection.replace_one(
                {"_id": mongo_document["_id"]},
                mongo_document,
                upsert=True,
            )
            written_count += 1

        meta = client[args.database][MongoSupplementaryMaterialRepository.META_COLLECTION]
        meta.update_one(
            {"_id": "seed_version"},
            {
                "$set": {
                    "value": MongoSupplementaryMaterialRepository.SEED_VERSION,
                    "source": "sqlite-migration",
                }
            },
            upsert=True,
        )
        return {
            "source_count": len(documents),
            "target_count": collection.count_documents({}),
            "written_count": written_count,
        }
    finally:
        client.close()


def main() -> int:
    args = parse_args()
    result = migrate(args)
    print({"sqlite": str(args.sqlite_path), "mongo": args.mongo_uri, **result})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
