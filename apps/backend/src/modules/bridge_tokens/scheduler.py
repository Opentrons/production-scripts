from __future__ import annotations

import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from core.logging import get_logger
from modules.bridge_tokens.service import BridgeTokenService


logger = get_logger(__name__)


def due_task_slots(now: datetime) -> list[tuple[str, str]]:
    local_now = now
    monday = (local_now - timedelta(days=local_now.weekday())).date()
    tasks: list[tuple[str, str]] = []

    weekly_schedule = (
        ("weekly_allocation", monday, 0, 9),
        ("weekly_reminder", monday, 2, 10),
        ("weekly_rebalance", monday, 3, 10),
    )
    for action, week_start, day_offset, hour in weekly_schedule:
        scheduled = datetime.combine(
            week_start + timedelta(days=day_offset),
            datetime.min.time(),
            tzinfo=local_now.tzinfo,
        ).replace(hour=hour)
        if local_now >= scheduled:
            tasks.append((action, monday.isoformat()))

    monitor_slot = local_now.replace(
        minute=(local_now.minute // 30) * 30,
        second=0,
        microsecond=0,
    )
    tasks.append(("monitor", monitor_slot.isoformat()))
    return tasks


class BridgeTokenScheduler:
    def __init__(self, service: BridgeTokenService) -> None:
        self.service = service
        self.poll_seconds = max(5.0, service.settings.scheduler_poll_seconds)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not self.service.settings.automation_enabled:
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="bridge-token-scheduler",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self.poll_seconds + 1)
        self._thread = None

    def reconfigure(self) -> None:
        self.poll_seconds = max(5.0, self.service.settings.scheduler_poll_seconds)
        if self.service.settings.automation_enabled:
            if self._thread is not None and self._thread.is_alive():
                self.stop()
            self.start()
        else:
            self.stop()

    def _run(self) -> None:
        try:
            timezone = ZoneInfo(self.service.settings.timezone)
        except Exception:
            timezone = ZoneInfo("Asia/Shanghai")
        while not self._stop_event.is_set():
            if self.service.configured:
                for action, slot in due_task_slots(datetime.now(timezone)):
                    try:
                        self.service.execute_scheduled(action, slot)
                    except Exception:
                        logger.exception("Bridge token scheduled task failed: %s", action)
            self._stop_event.wait(self.poll_seconds)
