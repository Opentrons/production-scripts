from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import threading
from typing import Any

from modules.system import health


class FakeHealthCollection:
    def __init__(self, record: dict[str, Any] | None = None) -> None:
        self.record = record
        self.update_calls: list[tuple[dict[str, Any], dict[str, Any], bool]] = []

    def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        if self.record and self.record.get("_id") == query.get("_id"):
            return dict(self.record)
        return None

    def update_one(
        self,
        query: dict[str, Any],
        update: dict[str, Any],
        upsert: bool = False,
    ) -> None:
        self.update_calls.append((query, update, upsert))
        self.record = dict(update["$set"])


def _cached_record() -> dict[str, Any]:
    return {
        "_id": "latest",
        "status": True,
        "elapsed_ms": 12.5,
        "checked_at": "2026-08-14T00:00:00+00:00",
        "services": {
            "system_service": {"status": "running", "message": "ok"},
            "slack": {"status": "healthy", "message": "ok"},
            "google_drive": {"status": "healthy", "message": "ok"},
        },
    }


def test_get_health_status_only_reads_cached_database(monkeypatch) -> None:
    collection = FakeHealthCollection(_cached_record())
    monkeypatch.setattr(health, "_health_collection", lambda: collection)
    monkeypatch.setattr(
        health,
        "check_systemctl_service",
        lambda _name: (_ for _ in ()).throw(AssertionError("live probe called")),
    )

    result = health.get_health_status()

    assert result["status"] is True
    assert result["checked_at"] == "2026-08-14T00:00:00+00:00"
    assert collection.update_calls == []


def test_missing_cached_health_returns_unknown_without_live_probe(monkeypatch) -> None:
    collection = FakeHealthCollection()
    monkeypatch.setattr(health, "_health_collection", lambda: collection)

    result = health.get_health_status()

    assert result["status"] is False
    assert result["checked_at"] is None
    assert all(item["status"] == "unknown" for item in result["services"].values())


def test_refresh_health_probes_once_and_persists_result(monkeypatch) -> None:
    collection = FakeHealthCollection()
    monkeypatch.setattr(health, "_health_collection", lambda: collection)
    monkeypatch.setattr(
        health,
        "check_systemctl_service",
        lambda _name: {"status": "running", "message": "ok"},
    )
    monkeypatch.setattr(
        health,
        "check_slack_health",
        lambda: (True, {"status": "healthy", "message": "ok"}),
    )
    monkeypatch.setattr(
        health,
        "check_google_drive_health",
        lambda: (True, {"status": "healthy", "message": "ok"}),
    )

    result = health.refresh_health_status()

    assert result["status"] is True
    assert result["checked_at"]
    assert len(collection.update_calls) == 1
    assert collection.record == {"_id": "latest", **result}


def test_concurrent_refresh_waits_for_same_probe_result(monkeypatch) -> None:
    collection = FakeHealthCollection(_cached_record())
    monkeypatch.setattr(health, "_health_collection", lambda: collection)
    completion = threading.Event()
    monkeypatch.setattr(health, "_refresh_complete", completion)
    monkeypatch.setattr(
        health,
        "_probe_health_status",
        lambda: (_ for _ in ()).throw(AssertionError("duplicate probe called")),
    )

    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(health.refresh_health_status)
        assert not pending.done()
        collection.record = _cached_record()
        collection.record["checked_at"] = "2026-08-14T00:10:00+00:00"
        completion.set()
        result = pending.result(timeout=2)

    assert result["checked_at"] == "2026-08-14T00:10:00+00:00"
