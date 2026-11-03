from __future__ import annotations

import os
import threading

from .service import get_service


_lock = threading.Lock()
_stop = threading.Event()
_thread: threading.Thread | None = None


def start_test_failure_scheduler() -> None:
    global _thread
    with _lock:
        if _thread is not None and _thread.is_alive():
            return
        try:
            interval = max(5.0, float(os.getenv("PRODUCTION_PLATFORM_TEST_FAILURE_SCAN_SECONDS", "60")))
        except ValueError:
            interval = 60.0
        _stop.clear()

        def run() -> None:
            service = get_service()
            service.scan()
            while not _stop.wait(interval):
                service.scan()

        _thread = threading.Thread(target=run, name="test-failure-scheduler", daemon=True)
        _thread.start()


def stop_test_failure_scheduler() -> None:
    global _thread
    with _lock:
        _stop.set()
        thread = _thread
    if thread is not None:
        thread.join(timeout=3)
    with _lock:
        if _thread is thread and (thread is None or not thread.is_alive()):
            _thread = None
