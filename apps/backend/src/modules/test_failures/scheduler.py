from __future__ import annotations

import logging
import math
import os
import threading

from core import config
from core.runtime_mode import is_simulating
from .service import get_service
from .writeback import write_pending_confirmations


logger = logging.getLogger(__name__)
_lock = threading.Lock()
_stop = threading.Event()
_threads: tuple[threading.Thread, ...] = ()


def start_test_failure_scheduler() -> None:
    global _threads
    with _lock:
        if any(thread.is_alive() for thread in _threads):
            return
        try:
            configured_interval = float(os.getenv("PRODUCTION_PLATFORM_TEST_FAILURE_SCAN_SECONDS", "60"))
            interval = max(5.0, configured_interval) if math.isfinite(configured_interval) else 60.0
        except ValueError:
            interval = 60.0
        _stop.clear()
        service = get_service()

        def scan() -> None:
            service.scan()
            while not _stop.wait(interval):
                service.scan()

        def writeback_stopped() -> bool:
            return _stop.is_set() or is_simulating()

        def writeback() -> None:
            while not _stop.is_set():
                service.writeback_ready.wait(interval)
                service.writeback_ready.clear()
                scan_status = service.scan_status()
                if writeback_stopped() or (scan_status["source_status"] not in {"available", "degraded"}
                                           and scan_status.get("mongo_status") != "available"):
                    continue
                try:
                    write_pending_confirmations(service, config.DATA_DB_NAME, interval, stopped=writeback_stopped)
                except Exception:
                    logger.exception("Automatic failure writeback batch failed")

        _threads = (
            threading.Thread(target=scan, name="test-failure-scheduler", daemon=True),
            threading.Thread(target=writeback, name="test-failure-writeback", daemon=True),
        )
        for thread in _threads:
            thread.start()


def stop_test_failure_scheduler() -> None:
    global _threads
    with _lock:
        _stop.set()
        threads = _threads
        if threads:
            get_service().writeback_ready.set()
    for thread in threads:
        thread.join(timeout=3)
    with _lock:
        if _threads is threads and not any(thread.is_alive() for thread in threads):
            _threads = ()
