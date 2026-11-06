from __future__ import annotations

from concurrent.futures import CancelledError
from threading import Event, Lock
from typing import Any

from modules.supplies.models import (
    SupplementaryMaterial,
    SupplementaryMaterialCreate,
    SupplementaryMaterialUpdate,
    SupplementaryMaterialSyncResult,
    SupplementaryMaterialSyncStatus,
    utc_now,
)
from modules.supplies.source import GoogleSupplementaryMaterialSource
from modules.supplies.repository import (
    DuplicateSupplementaryMaterialError,
)


class SupplementaryMaterialNotFoundError(LookupError):
    pass


class SupplementaryMaterialSyncInProgressError(RuntimeError):
    pass


class SupplementaryMaterialService:
    def __init__(
        self, repository: Any, source: GoogleSupplementaryMaterialSource | None = None,
        *, sync_interval_seconds: int = 3600, auto_sync_enabled: bool = True,
    ) -> None:
        self.repository = repository
        self.source = source
        self.sync_interval_seconds = sync_interval_seconds
        self.auto_sync_enabled = auto_sync_enabled
        self._sync_lock = Lock()
        self._last_error = ""

    def sync_status(self) -> SupplementaryMaterialSyncStatus:
        state = self.repository.get_sheet_sync_state()
        return SupplementaryMaterialSyncStatus(
            source_url=self.source.source_url if self.source else "",
            interval_seconds=self.sync_interval_seconds,
            auto_sync_enabled=self.auto_sync_enabled,
            last_synced_at=state.get("synced_at"), last_error=self._last_error,
            syncing=self._sync_lock.locked(),
        )

    def sync_from_source(self, *, cancel_event: Event | None = None) -> SupplementaryMaterialSyncResult:
        if not self._sync_lock.acquire(blocking=False):
            raise SupplementaryMaterialSyncInProgressError("辅料原表正在更新，请稍后重试")
        try:
            if self.source is None:
                raise ValueError("辅料原表数据源未配置")
            payloads = self.source.read()
            if cancel_event is not None and cancel_event.is_set():
                raise CancelledError("辅料自动更新已停止")
            synced_at = utc_now()
            plan = self.repository.sync_from_sheet(payloads, synced_at)
            self._last_error = ""
            return SupplementaryMaterialSyncResult(
                source_url=self.source.source_url, synced_at=synced_at, total=len(plan.materials),
                created_count=plan.created_count, updated_count=plan.updated_count, removed_count=len(plan.removed_ids),
            )
        except CancelledError:
            raise
        except Exception as exc:
            self._last_error = str(exc)
            raise
        finally:
            self._sync_lock.release()

    def list(self, query: str | None = None) -> list[SupplementaryMaterial]:
        return self.repository.list(query)

    def create(self, payload: SupplementaryMaterialCreate) -> SupplementaryMaterial:
        return self.repository.create(payload)

    def update(
        self,
        material_id: str,
        payload: SupplementaryMaterialUpdate,
    ) -> SupplementaryMaterial:
        material = self.repository.update(material_id, payload)
        if material is None:
            raise SupplementaryMaterialNotFoundError(f"辅料不存在: {material_id}")
        return material

    def delete(self, material_id: str) -> None:
        if not self.repository.delete(material_id):
            raise SupplementaryMaterialNotFoundError(f"辅料不存在: {material_id}")
