from __future__ import annotations

from datetime import datetime, timezone

from modules.agent.schedules.models import AgentScheduleInput
from modules.agent.schedules.service import AgentScheduleService, compute_next_run_at


class MemoryCollection:
    def __init__(self) -> None:
        self.docs: dict[str, dict] = {}

    def find(self, _query=None):
        return list(self.docs.values())

    def find_one(self, query):
        key = query.get("_id")
        doc = self.docs.get(key)
        return dict(doc) if doc else None

    def update_one(self, query, update, upsert=False):
        key = query["_id"]
        current = self.docs.get(key, {"_id": key})
        if "$set" in update:
            current.update(update["$set"])
        if "$setOnInsert" in update and key not in self.docs:
            current.update(update["$setOnInsert"])
        if upsert or key in self.docs:
            self.docs[key] = current
        return type("Result", (), {"matched_count": 1, "modified_count": 1})()

    def delete_one(self, query):
        key = query["_id"]
        existed = key in self.docs
        self.docs.pop(key, None)
        return type("Result", (), {"deleted_count": 1 if existed else 0})()


def test_agent_schedule_crud_and_due_list(monkeypatch) -> None:
    schedules = MemoryCollection()
    runs = MemoryCollection()
    service = AgentScheduleService()
    monkeypatch.setattr(service, "_schedules", lambda: schedules)
    monkeypatch.setattr(service, "_runs", lambda: runs)

    created = service.create_schedule(
        AgentScheduleInput(
            name="daily-upload-brief",
            description="汇总今天的数据上传成功率",
            enabled=True,
            interval_minutes=30,
        ),
        created_by="user-1",
    )
    assert created.id.startswith("agent_schedule_")
    assert created.next_run_at is not None
    assert service.list_schedules()["total"] == 1

    updated = service.update_schedule(
        created.id,
        AgentScheduleInput(
            name=created.name,
            description=created.description,
            enabled=False,
            interval_minutes=30,
        ),
    )
    assert updated.enabled is False
    assert updated.next_run_at is None
    assert service.list_due_schedules() == []
    assert service.delete_schedule(created.id) is True


def test_compute_next_run_at_daily_rolls_forward() -> None:
    after = datetime(2026, 8, 14, 10, 0, tzinfo=timezone.utc)  # 18:00 Asia/Shanghai
    next_run = compute_next_run_at(
        schedule_kind="daily",
        interval_minutes=60,
        daily_time="09:00",
        enabled=True,
        after=after,
    )
    assert next_run is not None
    # Next local 09:00 Asia/Shanghai after 18:00 is tomorrow 01:00 UTC
    assert next_run == datetime(2026, 8, 15, 1, 0, tzinfo=timezone.utc)


def test_daily_schedule_requires_time() -> None:
    try:
        AgentScheduleInput(
            name="bad",
            description="x",
            schedule_kind="daily",
            daily_time=None,
        )
        assert False, "expected validation error"
    except Exception:
        assert True
