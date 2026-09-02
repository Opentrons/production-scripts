"""Unified document persistence with simulation and dev SQLite fallback."""

from __future__ import annotations

from typing import Any, Literal

import core.config as setting
from core.database import mongodb
from core.logging import get_logger

logger = get_logger(__name__)

StorageBackend = Literal["mongodb", "sqlite"]


def storage_backend() -> StorageBackend:
    return "sqlite" if setting.use_sqlite_persistence() else "mongodb"


def storage_label() -> StorageBackend:
    return storage_backend()


def require_mongodb() -> Any:
    """Return a live MongoDB client or raise."""
    if mongodb.client is None and not mongodb.connect():
        target = "PRODUCTION_PLATFORM_MONGO_URI" if setting.MONGO_URI else f"{setting.MONGO_HOST}:27017"
        raise RuntimeError(
            "MongoDB is unavailable for business persistence "
            f"({target}); configure a reachable MongoDB instance."
        )
    return mongodb.client


def get_message_database():
    """Return ProductionsMessage database (Mongo) or raise when unavailable."""
    client = require_mongodb()
    return client[setting.MESSAGE_COLLECTION]


def get_document_collection(name: str):
    """Return a Mongo-like collection for business documents.

    - normal operation -> MongoDB ProductionsMessage.<name>
    - simulating or dev connection fallback -> local platform.sqlite3 collection
    """
    if setting.use_sqlite_persistence():
        from core.sqlite_store import get_platform_store

        return get_platform_store()[name]

    database = get_message_database()
    return database[name]
