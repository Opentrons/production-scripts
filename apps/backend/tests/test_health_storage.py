from __future__ import annotations

from modules.system import health


def test_health_cache_uses_sqlite_in_development(monkeypatch) -> None:
    sqlite_collection = object()
    monkeypatch.setattr(health.setting, "IS_DEV_ENV", True)
    monkeypatch.setattr(
        health,
        "get_platform_store",
        lambda: {health.setting.SYSTEM_HEALTH_COLLECTION: sqlite_collection},
    )

    assert health._health_collection() is sqlite_collection


def test_health_cache_uses_mongodb_on_server(monkeypatch) -> None:
    mongo_collection = object()
    monkeypatch.setattr(health.setting, "IS_DEV_ENV", False)
    monkeypatch.setattr(health, "get_document_collection", lambda name: mongo_collection)

    assert health._health_collection() is mongo_collection
