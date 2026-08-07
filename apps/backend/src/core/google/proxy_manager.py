from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from core.config import GOOGLE_PROXY_REFRESH_SECONDS
from core.google import proxy as proxy_tools


class GoogleProxyManager:
    """Maintain ranked Google proxies outside user request threads."""

    def __init__(self, refresh_seconds: int = GOOGLE_PROXY_REFRESH_SECONDS) -> None:
        self.refresh_seconds = max(30, refresh_seconds)
        self._lock = threading.RLock()
        self._refresh_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._candidates: list[dict[str, Any]] = []
        self._current_proxy = proxy_tools.get_proxy_url()
        self._current_node = ""
        self._version = 0
        self._refreshing = False
        self._last_checked_at: str | None = None
        self._last_error = ""

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, name="google-proxy-manager", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2)

    def current(self) -> tuple[str | None, int]:
        with self._lock:
            return self._current_proxy, self._version

    def failover(self, failed_proxy: str | None) -> str | None:
        with self._lock:
            for candidate in self._candidates:
                proxy_url = str(candidate.get("proxy_url") or "")
                if proxy_url and proxy_url != failed_proxy:
                    self._set_current_locked(proxy_url, str(candidate.get("name") or ""))
                    self.refresh_async()
                    return proxy_url
        self.refresh_async()
        return None

    def refresh_async(self) -> bool:
        with self._lock:
            if self._refreshing:
                return False
            self._refreshing = True
        threading.Thread(target=self._refresh_once, name="google-proxy-refresh", daemon=True).start()
        return True

    def status(self) -> dict[str, Any]:
        with self._lock:
            current = next(
                (item for item in self._candidates if item.get("proxy_url") == self._current_proxy),
                {},
            )
            status = "unavailable"
            if self._current_proxy:
                status = "degraded" if self._last_error else "healthy"
            return {
                "status": status,
                "node": self._current_node or current.get("name", ""),
                "latency_ms": current.get("latency_ms"),
                "last_checked_at": self._last_checked_at,
                "refreshing": self._refreshing,
                "fallback_count": max(0, len(self._candidates) - 1),
                "last_error": self._last_error,
                "version": self._version,
            }

    def _run(self) -> None:
        self.refresh_async()
        while not self._stop_event.wait(self.refresh_seconds):
            self.refresh_async()

    def _refresh_once(self) -> None:
        if not self._refresh_lock.acquire(blocking=False):
            with self._lock:
                self._refreshing = False
            return
        try:
            candidates = self._scan_candidates()
            with self._lock:
                self._last_checked_at = datetime.now(timezone.utc).isoformat()
                if candidates:
                    self._candidates = candidates
                    best = candidates[0]
                    self._set_current_locked(str(best["proxy_url"]), str(best["name"]))
                    self._last_error = ""
                else:
                    self._last_error = "No available Google proxy nodes"
        except Exception as exc:
            with self._lock:
                self._last_checked_at = datetime.now(timezone.utc).isoformat()
                self._last_error = str(exc)
        finally:
            with self._lock:
                self._refreshing = False
            self._refresh_lock.release()

    def _scan_candidates(self) -> list[dict[str, Any]]:
        node_test = proxy_tools._load_module(
            proxy_tools.GHELPER_DIR / "node_test.py",
            "production_backend_background_node_test",
        )
        if node_test is None:
            return []
        node_test.update_subscription_config()
        proxies = node_test.load_proxies_from_yml(node_test.DEFAULT_YML_FILE)
        results = node_test.run_tests(
            proxies,
            max_threads=25,
            test_url=proxy_tools.GOOGLE_PROXY_TEST_URL,
        )
        successful = sorted(
            (result for result in results if result.success and result.proxy_url),
            key=lambda result: result.latency or float("inf"),
        )
        return [
            {
                "name": result.name,
                "proxy_url": result.proxy_url,
                "latency_ms": round(result.latency, 2) if result.latency is not None else None,
            }
            for result in successful[:3]
        ]

    def _set_current_locked(self, proxy_url: str, node_name: str) -> None:
        if proxy_url != self._current_proxy:
            self._current_proxy = proxy_url
            self._current_node = node_name
            self._version += 1


google_proxy_manager = GoogleProxyManager()
