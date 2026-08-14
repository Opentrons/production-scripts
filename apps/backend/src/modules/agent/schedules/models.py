from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class AgentScheduleInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(
        min_length=1,
        max_length=8000,
        description="自然语言任务描述，到点后由生产助手解读并执行",
    )
    enabled: bool = True
    schedule_kind: Literal["interval", "daily"] = "interval"
    interval_minutes: int = Field(default=60, ge=1, le=10080)
    daily_time: str | None = Field(
        default=None,
        description="每天执行时刻，格式 HH:MM（按 AGENT_SCHEDULE_TIMEZONE）",
    )

    @field_validator("daily_time")
    @classmethod
    def validate_daily_time(cls, value: str | None) -> str | None:
        if value is None or not str(value).strip():
            return None
        text = str(value).strip()
        parts = text.split(":")
        if len(parts) != 2:
            raise ValueError("daily_time 必须是 HH:MM")
        try:
            hour = int(parts[0])
            minute = int(parts[1])
        except ValueError as exc:
            raise ValueError("daily_time 必须是 HH:MM") from exc
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError("daily_time 超出有效范围")
        return f"{hour:02d}:{minute:02d}"

    @model_validator(mode="after")
    def validate_schedule_fields(self) -> AgentScheduleInput:
        if self.schedule_kind == "daily" and not self.daily_time:
            raise ValueError("每天执行需要设置 daily_time")
        return self


class AgentSchedule(AgentScheduleInput):
    id: str
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    last_status: Literal["success", "failed", "running"] | None = None
    last_result_preview: str | None = None
    created_by: str | None = None
    created_at: str
    updated_at: str


class AgentScheduleListResponse(BaseModel):
    items: list[AgentSchedule] = Field(default_factory=list)
    total: int = 0
    storage: str = "sqlite"


class AgentScheduleRun(BaseModel):
    id: str
    schedule_id: str
    schedule_name: str
    description: str
    status: Literal["success", "failed", "running"]
    trigger: Literal["scheduled", "manual"] = "scheduled"
    result: str = ""
    error: str | None = None
    started_at: str
    finished_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentScheduleRunListResponse(BaseModel):
    items: list[AgentScheduleRun] = Field(default_factory=list)
    total: int = 0
