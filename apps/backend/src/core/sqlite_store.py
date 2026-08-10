from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from pymongo.errors import DuplicateKeyError


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _matches(document: dict[str, Any], query: dict[str, Any] | None) -> bool:
    if not query:
        return True
    for key, expected in query.items():
        actual = document.get(key)
        if key == "_id":
            actual = str(actual) if actual is not None else actual
            expected = str(expected) if expected is not None else expected
        if actual != expected:
            return False
    return True


class SqliteCollection:
    """Minimal Mongo-like collection backed by a SQLite documents table."""

    def __init__(self, store: "SqliteDocumentStore", name: str) -> None:
        self._store = store
        self.name = name

    def create_index(self, *args: Any, **kwargs: Any) -> None:
        return None

    def find(self, query: dict[str, Any] | None = None, projection: dict[str, Any] | None = None):
        documents = [
            self._apply_projection(document, projection)
            for document in self._store._load_collection(self.name)
            if _matches(document, query)
        ]
        return _Cursor(documents)

    def find_one(self, query: dict[str, Any] | None = None, projection: dict[str, Any] | None = None):
        for document in self.find(query, projection):
            return document
        return None

    def insert_one(self, document: dict[str, Any]):
        payload = dict(document)
        payload.setdefault("_id", str(uuid4()))
        documents = self._store._load_collection(self.name)
        if any(str(item.get("_id")) == str(payload["_id"]) for item in documents):
            raise DuplicateKeyError("duplicate _id")
        name_key = payload.get("name_key")
        if name_key and any(item.get("name_key") == name_key for item in documents):
            raise DuplicateKeyError("duplicate name_key")
        documents.append(payload)
        self._store._save_collection(self.name, documents)
        return SimpleNamespace(inserted_id=payload["_id"])

    def find_one_and_update(
        self,
        query: dict[str, Any],
        update: dict[str, Any],
        *,
        return_document: Any = None,
        upsert: bool = False,
    ):
        documents = self._store._load_collection(self.name)
        matched_index = -1
        matched = None
        for index, document in enumerate(documents):
            if _matches(document, query):
                matched = dict(document)
                matched_index = index
                break

        set_fields = dict(update.get("$set") or {})
        set_on_insert = dict(update.get("$setOnInsert") or {})
        if matched is None:
            if not upsert:
                return None
            created = dict(query)
            created.update(set_on_insert)
            created.update(set_fields)
            created.setdefault("_id", str(uuid4()))
            name_key = created.get("name_key")
            if name_key and any(item.get("name_key") == name_key for item in documents):
                raise DuplicateKeyError("duplicate name_key")
            documents.append(created)
            self._store._save_collection(self.name, documents)
            return created

        name_key = set_fields.get("name_key", matched.get("name_key"))
        if name_key and any(
            index != matched_index and item.get("name_key") == name_key
            for index, item in enumerate(documents)
        ):
            raise DuplicateKeyError("duplicate name_key")
        matched.update(set_fields)
        documents[matched_index] = matched
        self._store._save_collection(self.name, documents)
        return matched

    def update_one(
        self,
        query: dict[str, Any],
        update: dict[str, Any],
        upsert: bool = False,
    ):
        documents = self._store._load_collection(self.name)
        matched = None
        matched_index = -1
        for index, document in enumerate(documents):
            if _matches(document, query):
                matched = dict(document)
                matched_index = index
                break

        set_fields = dict(update.get("$set") or {})
        set_on_insert = dict(update.get("$setOnInsert") or {})
        if matched is None:
            if not upsert:
                return SimpleNamespace(matched_count=0, modified_count=0, upserted_id=None)
            created = dict(query)
            created.update(set_on_insert)
            created.update(set_fields)
            created.setdefault("_id", str(uuid4()))
            documents.append(created)
            self._store._save_collection(self.name, documents)
            return SimpleNamespace(matched_count=0, modified_count=0, upserted_id=created["_id"])

        previous = dict(matched)
        matched.update(set_fields)
        documents[matched_index] = matched
        self._store._save_collection(self.name, documents)
        return SimpleNamespace(
            matched_count=1,
            modified_count=0 if previous == matched else 1,
            upserted_id=None,
        )

    def delete_one(self, query: dict[str, Any]):
        documents = self._store._load_collection(self.name)
        for index, document in enumerate(documents):
            if _matches(document, query):
                documents.pop(index)
                self._store._save_collection(self.name, documents)
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)

    def update_many(self, query: dict[str, Any], update: dict[str, Any]):
        documents = self._store._load_collection(self.name)
        set_fields = dict(update.get("$set") or {})
        modified = 0
        for index, document in enumerate(documents):
            if not _matches(document, query):
                continue
            previous = dict(document)
            document.update(set_fields)
            documents[index] = document
            if previous != document:
                modified += 1
        if modified:
            self._store._save_collection(self.name, documents)
        return SimpleNamespace(matched_count=modified, modified_count=modified)

    def count_documents(self, query: dict[str, Any] | None = None) -> int:
        return sum(1 for _ in self.find(query))

    def distinct(self, key: str, query: dict[str, Any] | None = None) -> list[Any]:
        values = []
        seen = set()
        for document in self.find(query):
            if "." in key:
                current: Any = document
                for part in key.split("."):
                    if not isinstance(current, dict):
                        current = None
                        break
                    current = current.get(part)
                value = current
            else:
                value = document.get(key)
            marker = repr(value)
            if value in (None, "") or marker in seen:
                continue
            seen.add(marker)
            values.append(value)
        return values

    def _apply_projection(
        self,
        document: dict[str, Any],
        projection: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not projection:
            return dict(document)

        include_id = projection.get("_id", 1)
        inclusion_fields = {
            key: value
            for key, value in projection.items()
            if key != "_id" and value
        }
        if inclusion_fields:
            result = {key: document[key] for key in inclusion_fields if key in document}
        else:
            excluded = {
                key
                for key, value in projection.items()
                if key != "_id" and not value
            }
            result = {key: value for key, value in document.items() if key not in excluded}

        if include_id:
            if "_id" in document:
                result["_id"] = document["_id"]
        else:
            result.pop("_id", None)
        return result


class _Cursor:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self._documents = documents

    def sort(self, key: Any, direction: int = 1):
        if isinstance(key, list):
            for field, field_direction in reversed(key):
                reverse = int(field_direction) < 0
                self._documents.sort(key=lambda item, f=field: item.get(f) or "", reverse=reverse)
            return self
        reverse = direction < 0
        self._documents.sort(key=lambda item: item.get(key) or "", reverse=reverse)
        return self

    def skip(self, count: int):
        self._documents = self._documents[max(0, int(count)) :]
        return self

    def limit(self, count: int):
        self._documents = self._documents[: max(0, int(count))]
        return self

    def __iter__(self):
        return iter(self._documents)


class SqliteDocumentStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def __getitem__(self, name: str) -> SqliteCollection:
        return SqliteCollection(self, name)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    collection TEXT NOT NULL,
                    doc_key TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (collection, doc_key)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_documents_collection ON documents(collection)"
            )

    def _load_collection(self, collection: str) -> list[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM documents WHERE collection = ? ORDER BY updated_at ASC",
                (collection,),
            ).fetchall()
        documents: list[dict[str, Any]] = []
        for row in rows:
            try:
                payload = json.loads(row["payload"])
            except Exception:
                continue
            if isinstance(payload, dict):
                documents.append(payload)
        return documents

    def _save_collection(self, collection: str, documents: list[dict[str, Any]]) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM documents WHERE collection = ?", (collection,))
            now = _utc_now()
            for document in documents:
                doc_key = str(
                    document.get("_id")
                    or document.get("cache_key")
                    or document.get("gateway")
                    or uuid4()
                )
                if "_id" not in document:
                    document["_id"] = doc_key
                connection.execute(
                    """
                    INSERT INTO documents (collection, doc_key, payload, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (collection, doc_key, json.dumps(document, ensure_ascii=False), now),
                )


_STORE_CACHE: dict[str, SqliteDocumentStore] = {}
_STORE_LOCK = RLock()


def get_platform_store() -> SqliteDocumentStore:
    import core.config as setting

    path = setting.resolve_sqlite_path("platform.sqlite3")
    cache_key = str(path.resolve())
    with _STORE_LOCK:
        store = _STORE_CACHE.get(cache_key)
        if store is None:
            store = SqliteDocumentStore(path)
            _STORE_CACHE[cache_key] = store
        return store
