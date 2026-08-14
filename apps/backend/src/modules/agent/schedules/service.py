from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import core.config as setting
from core.database import mongodb
from core.logging import get_logger
from modules.agent.models import AgentChatMessage, AgentChatRequest
from modules.agent.schedules.models import AgentSchedule, AgentScheduleInput, AgentScheduleRun


logger = get_logger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat()


def _schedule_tz() -> ZoneInfo:
    try:
        return ZoneInfo(setting.AGENT_SCHEDULE_TIMEZONE)
    except Exception:
        logger.warning("Invalid AGENT_SCHEDULE_TIMEZONE=%s, fallback to Asia/Shanghai", setting.AGENT_SCHEDULE_TIMEZONE)
        return ZoneInfo("Asia/Shanghai")


def _parse_daily_time(value: str | None) -> tuple[int, int]:
    text = str(value or "").strip()
    hour_text, minute_text = text.split(":", 1)
    return int(hour_text), int(minute_text)


def compute_next_run_at(
    *,
    schedule_kind: str,
    interval_minutes: int,
    daily_time: str | None,
    enabled: bool,
    after: datetime | None = None,
) -> datetime | None:
    if not enabled:
        return None
    base = after or _now()
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)

    if schedule_kind == "daily":
        if not daily_time:
            return None
        hour, minute = _parse_daily_time(daily_time)
        local_tz = _schedule_tz()
        local_after = base.astimezone(local_tz)
        candidate = local_after.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= local_after:
            candidate = candidate + timedelta(days=1)
        return candidate.astimezone(timezone.utc)

    return base + timedelta(minutes=max(1, int(interval_minutes)))


class AgentScheduleService:
    def __init__(self) -> None:
        self._lock = threading.RLock()

    @property
    def storage(self) -> str:
        return "sqlite" if setting.use_sqlite_persistence() else "mongodb"

    def _collection(self, name: str):
        if setting.use_sqlite_persistence():
            from core.sqlite_store import get_platform_store

            return get_platform_store()[name]
        if mongodb.client is None and not mongodb.connect():
            raise RuntimeError("定时任务数据库连接失败")
        collection = mongodb.get_database(setting.MESSAGE_COLLECTION)[name]
        return collection

    def _schedules(self):
        return self._collection(setting.AGENT_SCHEDULE_COLLECTION)

    def _runs(self):
        return self._collection(setting.AGENT_SCHEDULE_RUN_COLLECTION)

    @staticmethod
    def _serialize_schedule(document: dict[str, Any]) -> dict[str, Any]:
        payload = dict(document)
        payload["id"] = str(payload.pop("_id", payload.get("id") or ""))
        payload.setdefault("schedule_kind", "interval")
        payload.setdefault("interval_minutes", 60)
        payload.setdefault("daily_time", None)
        for key in ("next_run_at", "last_run_at"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                try:
                    payload[key] = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    payload[key] = None
        return payload

    @staticmethod
    def _serialize_run(document: dict[str, Any]) -> dict[str, Any]:
        payload = dict(document)
        payload["id"] = str(payload.pop("_id", payload.get("id") or ""))
        payload.setdefault("metadata", {})
        return payload

    def list_schedules(self) -> dict[str, Any]:
        items = [self._serialize_schedule(item) for item in self._schedules().find({})]
        items.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
        return {
            "items": [AgentSchedule.model_validate(item) for item in items],
            "total": len(items),
            "storage": self.storage,
        }

    def get_schedule(self, schedule_id: str) -> AgentSchedule | None:
        document = self._schedules().find_one({"_id": schedule_id})
        if not document:
            return None
        return AgentSchedule.model_validate(self._serialize_schedule(document))

    def create_schedule(self, payload: AgentScheduleInput, *, created_by: str | None = None) -> AgentSchedule:
        now = _now()
        schedule_id = f"agent_schedule_{uuid4().hex[:16]}"
        next_run = compute_next_run_at(
            schedule_kind=payload.schedule_kind,
            interval_minutes=payload.interval_minutes,
            daily_time=payload.daily_time,
            enabled=payload.enabled,
            after=now,
        )
        document = {
            "name": payload.name.strip(),
            "description": payload.description.strip(),
            "enabled": bool(payload.enabled),
            "schedule_kind": payload.schedule_kind,
            "interval_minutes": int(payload.interval_minutes),
            "daily_time": payload.daily_time,
            "next_run_at": _iso(next_run) if next_run else None,
            "last_run_at": None,
            "last_status": None,
            "last_result_preview": None,
            "created_by": created_by,
            "created_at": _iso(now),
            "updated_at": _iso(now),
        }
        self._schedules().update_one({"_id": schedule_id}, {"$set": document}, upsert=True)
        stored = self._schedules().find_one({"_id": schedule_id}) or {"_id": schedule_id, **document}
        return AgentSchedule.model_validate(self._serialize_schedule(stored))

    def update_schedule(self, schedule_id: str, payload: AgentScheduleInput) -> AgentSchedule:
        existing = self.get_schedule(schedule_id)
        if existing is None:
            raise KeyError(schedule_id)
        now = _now()
        schedule_changed = (
            not existing.enabled
            or existing.schedule_kind != payload.schedule_kind
            or existing.interval_minutes != payload.interval_minutes
            or existing.daily_time != payload.daily_time
            or payload.enabled != existing.enabled
        )
        if payload.enabled and schedule_changed:
            next_run = compute_next_run_at(
                schedule_kind=payload.schedule_kind,
                interval_minutes=payload.interval_minutes,
                daily_time=payload.daily_time,
                enabled=True,
                after=now,
            )
        elif payload.enabled:
            next_run = existing.next_run_at
        else:
            next_run = None
        document = {
            "name": payload.name.strip(),
            "description": payload.description.strip(),
            "enabled": bool(payload.enabled),
            "schedule_kind": payload.schedule_kind,
            "interval_minutes": int(payload.interval_minutes),
            "daily_time": payload.daily_time,
            "next_run_at": _iso(next_run) if next_run else None,
            "updated_at": _iso(now),
        }
        self._schedules().update_one({"_id": schedule_id}, {"$set": document})
        stored = self._schedules().find_one({"_id": schedule_id})
        return AgentSchedule.model_validate(self._serialize_schedule(stored or {"_id": schedule_id, **document}))

    def delete_schedule(self, schedule_id: str) -> bool:
        return self._schedules().delete_one({"_id": schedule_id}).deleted_count > 0

    def list_runs(self, schedule_id: str | None = None, *, limit: int = 30) -> dict[str, Any]:
        documents = [self._serialize_run(item) for item in self._runs().find({})]
        if schedule_id:
            documents = [item for item in documents if item.get("schedule_id") == schedule_id]
        documents.sort(key=lambda item: str(item.get("started_at") or ""), reverse=True)
        limited = documents[: max(1, min(int(limit), 100))]
        return {
            "items": [AgentScheduleRun.model_validate(item) for item in limited],
            "total": len(documents),
        }

    def list_due_schedules(self) -> list[AgentSchedule]:
        now = _now()
        due: list[AgentSchedule] = []
        for item in self._schedules().find({}):
            schedule = AgentSchedule.model_validate(self._serialize_schedule(item))
            if not schedule.enabled or schedule.next_run_at is None:
                continue
            next_run = schedule.next_run_at
            if next_run.tzinfo is None:
                next_run = next_run.replace(tzinfo=timezone.utc)
            if next_run <= now:
                due.append(schedule)
        return due

    def trigger_schedule(self, schedule_id: str, *, trigger: str = "scheduled") -> AgentScheduleRun:
        with self._lock:
            schedule = self.get_schedule(schedule_id)
            if schedule is None:
                raise KeyError(schedule_id)
            run_id = f"agent_run_{uuid4().hex[:16]}"
            started = _now()
            run_doc = {
                "schedule_id": schedule.id,
                "schedule_name": schedule.name,
                "description": schedule.description,
                "status": "running",
                "trigger": trigger,
                "result": "",
                "error": None,
                "started_at": _iso(started),
                "finished_at": None,
                "metadata": {},
            }
            self._runs().update_one({"_id": run_id}, {"$set": run_doc}, upsert=True)
            self._schedules().update_one(
                {"_id": schedule.id},
                {
                    "$set": {
                        "last_status": "running",
                        "updated_at": _iso(started),
                    }
                },
            )

        try:
            result = self._execute_agent(schedule.description)
            status = "failed" if result.get("error") else "success"
            content = str(result.get("content") or "").strip()
            error = str(result.get("error") or "").strip() or None
            if status == "success" and not content:
                content = "助手未返回内容。"
            preview = (content or error or "")[:500]
        except Exception as exc:
            logger.exception("Agent schedule %s failed", schedule_id)
            status = "failed"
            content = ""
            error = str(exc)
            preview = error[:500]
            result = {"tools": []}

        finished = _now()
        next_run = compute_next_run_at(
            schedule_kind=schedule.schedule_kind,
            interval_minutes=schedule.interval_minutes,
            daily_time=schedule.daily_time,
            enabled=schedule.enabled,
            after=finished,
        )
        with self._lock:
            self._runs().update_one(
                {"_id": run_id},
                {
                    "$set": {
                        "status": status,
                        "result": content,
                        "error": error,
                        "finished_at": _iso(finished),
                        "metadata": {"tool_count": len(result.get("tools") or [])},
                    }
                },
            )
            self._schedules().update_one(
                {"_id": schedule.id},
                {
                    "$set": {
                        "last_run_at": _iso(finished),
                        "last_status": status,
                        "last_result_preview": preview,
                        "next_run_at": _iso(next_run) if next_run else None,
                        "updated_at": _iso(finished),
                    }
                },
            )
        stored = self._runs().find_one({"_id": run_id}) or {"_id": run_id, **run_doc, "status": status}
        return AgentScheduleRun.model_validate(self._serialize_run(stored))

    def _execute_agent(self, description: str) -> dict[str, Any]:
        from modules.agent.service import agent_service

        if not agent_service.configured:
            raise RuntimeError("未配置 PRODUCTION_PLATFORM_LLM_API_KEY，无法执行定时任务")

        prompt = (
            "这是一条由系统定时触发的生产助手任务。请根据下面的自然语言描述完成任务，"
            "需要时调用工具获取实时证据，并给出简洁可执行的结论。\n\n"
            f"任务描述：\n{description.strip()}"
        )
        request = AgentChatRequest(
            messages=[AgentChatMessage(role="user", content=prompt)],
            context="定时任务自动执行",
        )

        async def _collect() -> dict[str, Any]:
            parts: list[str] = []
            tools: list[dict[str, Any]] = []
            error: str | None = None
            async for event in agent_service.stream_events(request):
                if event.type == "chunk" and event.content:
                    parts.append(event.content)
                elif event.type == "error" and event.content:
                    error = event.content
                elif event.type == "tool_result" and event.data:
                    tools.append(dict(event.data))
            return {"content": "".join(parts).strip(), "error": error, "tools": tools}

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(_collect())

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_collect())
        finally:
            loop.close()


class AgentScheduleScheduler:
    def __init__(self, service: AgentScheduleService, poll_seconds: float = 5) -> None:
        self.service = service
        self.poll_seconds = max(1, poll_seconds)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="agent-schedule-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self.poll_seconds + 1)
        self._thread = None

    def _run(self) -> None:
        while not self._stop_event.wait(self.poll_seconds):
            try:
                for schedule in self.service.list_due_schedules():
                    try:
                        self.service.trigger_schedule(schedule.id, trigger="scheduled")
                    except Exception:
                        logger.exception("Failed to trigger agent schedule %s", schedule.id)
            except Exception:
                logger.exception("Agent schedule poll failed")


agent_schedule_service = AgentScheduleService()
agent_schedule_scheduler = AgentScheduleScheduler(
    agent_schedule_service,
    poll_seconds=setting.AGENT_SCHEDULER_POLL_SECONDS,
)
