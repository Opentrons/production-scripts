from __future__ import annotations

import asyncio
from copy import deepcopy

import pytest

from api.services import robots


class FakeCollection:
    def __init__(self) -> None:
        self.docs: dict[str, dict] = {}

    def create_index(self, *args, **kwargs):
        return None

    def find_one(self, query: dict, projection: dict | None = None):
        doc = self.docs.get(query["cache_key"])
        return deepcopy(doc) if doc else None

    def update_one(self, query: dict, update: dict, upsert: bool = False):
        cache_key = query["cache_key"]
        is_insert = cache_key not in self.docs
        doc = self.docs.setdefault(cache_key, {})
        if is_insert:
            doc.update(deepcopy(update.get("$setOnInsert", {})))
        doc.update(deepcopy(update.get("$set", {})))
        return None


def _scan_result(ip: str = "192.168.6.10") -> dict:
    robot = {
        "ip": ip,
        "port": 31950,
        "online": True,
        "service_status": "normal",
    }
    return {
        "total": 1,
        "online_count": 1,
        "offline_count": 0,
        "abnormal_count": 0,
        "scan_network": ip,
        "server_ip": "192.168.6.55",
        "gateway": "192.168.6.1",
        "scan_gateways": ["192.168.6.1"],
        "online_robots": [robot],
        "offline_robots": [],
        "abnormal_robots": [],
    }


def test_robot_scan_cache_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    collection = FakeCollection()
    monkeypatch.setattr(robots, "get_robot_scan_cache_collection", lambda: collection)

    saved = robots.save_robot_scan_cache(
        _scan_result(),
        port=31950,
        network=None,
        scan_started_at="2026-07-15T00:00:00+00:00",
        scan_duration_ms=1200,
    )
    loaded = robots.load_robot_scan_cache(31950)

    assert saved["online_count"] == 1
    assert loaded["online_robots"][0]["ip"] == "192.168.6.10"
    assert loaded["scan_duration_ms"] == 1200
    assert loaded["cached_at"]
    assert loaded["last_error"] is None


def test_failed_refresh_preserves_last_successful_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    collection = FakeCollection()
    monkeypatch.setattr(robots, "get_robot_scan_cache_collection", lambda: collection)
    robots.save_robot_scan_cache(
        _scan_result(),
        port=31950,
        network=None,
        scan_started_at="2026-07-15T00:00:00+00:00",
        scan_duration_ms=1200,
    )

    robots.record_robot_scan_failure(
        "scan timeout",
        port=31950,
        network=None,
        scan_started_at="2026-07-15T00:03:00+00:00",
        scan_duration_ms=120000,
    )
    loaded = robots.load_robot_scan_cache(31950)

    assert loaded["online_count"] == 1
    assert loaded["online_robots"][0]["ip"] == "192.168.6.10"
    assert loaded["last_error"] == "scan timeout"


def test_offline_robot_skips_slow_http_health_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(robots, "_is_port_open", lambda ip, port: False)

    def unexpected_request(*args, **kwargs):
        raise AssertionError("HTTP health request should not run for a closed port")

    monkeypatch.setattr(robots.requests, "get", unexpected_request)

    result = robots.check_robot_health_sync("192.168.6.200")

    assert result["online"] is False
    assert result["error"] == "connection timeout"


def test_triggered_refresh_updates_cache_without_blocking_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collection = FakeCollection()
    monkeypatch.setattr(robots, "get_robot_scan_cache_collection", lambda: collection)

    async def fake_scan_robots(port: int, network: str | None = None):
        await asyncio.sleep(0.01)
        return _scan_result()

    monkeypatch.setattr(robots, "scan_robots", fake_scan_robots)

    async def run_refresh() -> None:
        started = robots.trigger_robot_scan_refresh(port=31950)
        assert started is True
        assert robots.is_robot_scan_refreshing(31950) is True
        while robots.is_robot_scan_refreshing(31950):
            await asyncio.sleep(0.01)

    asyncio.run(run_refresh())

    loaded = robots.load_robot_scan_cache(31950)
    assert loaded["online_count"] == 1
