from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from pymongo.errors import DuplicateKeyError

from core.persistence import get_document_collection
from modules.bridge_tokens.models import AllocationRecord, TokenSnapshot, utc_now


class BridgeTokenRepository:
    SNAPSHOTS = "bridge_token_snapshots"
    RECORDS = "bridge_token_allocation_records"
    RUNS = "bridge_token_automation_runs"
    STATE = "bridge_token_automation_state"

    def __init__(self, collection_factory: Callable[[str], Any] = get_document_collection) -> None:
        self._collection_factory = collection_factory

    def _collection(self, name: str):
        return self._collection_factory(name)

    def initialize(self) -> None:
        self._collection(self.SNAPSHOTS).create_index("key_name")
        self._collection(self.RECORDS).create_index([("key_id", 1), ("created_at", -1)])
        self._collection(self.RUNS).create_index("started_at")

    def save_snapshot(self, snapshot: TokenSnapshot) -> TokenSnapshot:
        document = snapshot.model_dump(mode="json")
        self._collection(self.SNAPSHOTS).update_one(
            {"_id": snapshot.key_id},
            {"$set": document},
            upsert=True,
        )
        return snapshot

    def list_snapshots(self) -> list[TokenSnapshot]:
        snapshots: list[TokenSnapshot] = []
        for document in self._collection(self.SNAPSHOTS).find({}):
            payload = dict(document)
            payload.pop("_id", None)
            snapshots.append(TokenSnapshot.model_validate(payload))
        return snapshots

    def save_record(self, record: AllocationRecord) -> AllocationRecord:
        document = record.model_dump(mode="json")
        document["_id"] = document.pop("id")
        self._collection(self.RECORDS).insert_one(document)
        return record

    def list_records(
        self,
        *,
        key_ids: set[str],
        key_names: set[str],
        action: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[AllocationRecord], int]:
        normalized_names = {name.casefold() for name in key_names if name}
        records: list[AllocationRecord] = []
        for document in self._collection(self.RECORDS).find({}):
            key_id = str(document.get("key_id") or "")
            key_name = str(document.get("key_name") or "")
            if key_id not in key_ids and key_name.casefold() not in normalized_names:
                continue
            if action and document.get("action") != action:
                continue
            payload = dict(document)
            payload["id"] = str(payload.pop("_id", payload.get("id") or ""))
            records.append(AllocationRecord.model_validate(payload))
        records.sort(key=lambda item: item.created_at, reverse=True)
        total = len(records)
        start = (page - 1) * page_size
        return records[start : start + page_size], total

    def claim_run(self, *, action: str, slot: str) -> bool:
        run_id = f"{action}:{slot}"
        collection = self._collection(self.RUNS)
        now = utc_now()
        try:
            collection.insert_one(
                {
                    "_id": run_id,
                    "action": action,
                    "slot": slot,
                    "status": "running",
                    "attempt": 1,
                    "started_at": now.isoformat(),
                }
            )
        except DuplicateKeyError:
            existing = collection.find_one({"_id": run_id}) or {}
            attempt = int(existing.get("attempt") or 1)
            if action != "weekly_allocation" or existing.get("status") != "failed" or attempt >= 3:
                return False
            next_retry_text = str(existing.get("next_retry_at") or "")
            try:
                next_retry_at = datetime.fromisoformat(next_retry_text).astimezone(timezone.utc)
            except ValueError:
                next_retry_at = now
            if next_retry_at > now:
                return False
            claimed = collection.find_one_and_update(
                {"_id": run_id, "status": "failed", "attempt": attempt},
                {
                    "$set": {
                        "status": "running",
                        "attempt": attempt + 1,
                        "started_at": now.isoformat(),
                    }
                },
            )
            return claimed is not None
        return True

    def finish_run(self, *, action: str, slot: str, summary: dict[str, Any]) -> None:
        now = utc_now()
        failed = bool(summary.get("errors"))
        next_retry_at = (
            (now + timedelta(minutes=5)).isoformat()
            if failed and action == "weekly_allocation"
            else ""
        )
        self._collection(self.RUNS).update_one(
            {"_id": f"{action}:{slot}"},
            {
                "$set": {
                    "status": "failed" if failed else "completed",
                    "finished_at": now.isoformat(),
                    "next_retry_at": next_retry_at,
                    "summary": summary,
                }
            },
        )

    def get_state(self, state_id: str) -> dict[str, Any]:
        document = self._collection(self.STATE).find_one({"_id": state_id})
        if not document:
            return {}
        payload = dict(document)
        payload.pop("_id", None)
        return payload

    def set_state(self, state_id: str, state: dict[str, Any]) -> None:
        self._collection(self.STATE).update_one(
            {"_id": state_id},
            {"$set": dict(state)},
            upsert=True,
        )
