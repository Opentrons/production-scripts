from __future__ import annotations

import logging
import threading
from concurrent.futures import CancelledError

from modules.supplies.service import SupplementaryMaterialService, SupplementaryMaterialSyncInProgressError


logger = logging.getLogger(__name__)


class SupplementaryMaterialSyncScheduler:
    def __init__(self, service: SupplementaryMaterialService, interval_seconds: float = 3600) -> None:
        self.service = service
        self.interval_seconds = max(1, interval_seconds)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not self.service.auto_sync_enabled or (self._thread and self._thread.is_alive()):
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="supplies-sheet-sync", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.service.sync_from_source(cancel_event=self._stop_event)
            except (SupplementaryMaterialSyncInProgressError, CancelledError):
                pass
            except Exception:
                logger.exception("辅料原表自动更新失败，保留已保存数据")
            if self._stop_event.wait(self.interval_seconds):
                break
