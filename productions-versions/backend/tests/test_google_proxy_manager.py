from google_driver.proxy_manager import GoogleProxyManager


def test_proxy_manager_failover_uses_ranked_candidate_without_scanning(monkeypatch) -> None:
    manager = GoogleProxyManager(refresh_seconds=300)
    manager._current_proxy = "http://first"  # noqa: SLF001
    manager._candidates = [  # noqa: SLF001
        {"name": "first", "proxy_url": "http://first", "latency_ms": 100},
        {"name": "second", "proxy_url": "http://second", "latency_ms": 150},
    ]
    monkeypatch.setattr(manager, "refresh_async", lambda: False)

    selected = manager.failover("http://first")

    assert selected == "http://second"
    assert manager.current()[0] == "http://second"
    assert manager.current()[1] == 1


def test_proxy_manager_allows_only_one_async_refresh(monkeypatch) -> None:
    manager = GoogleProxyManager(refresh_seconds=300)
    release = __import__("threading").Event()
    monkeypatch.setattr(manager, "_scan_candidates", lambda: (release.wait(1), [])[1])

    assert manager.refresh_async() is True
    assert manager.refresh_async() is False
    release.set()
