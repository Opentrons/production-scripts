from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


BridgeAction = Literal[
    "weekly_allocation",
    "low_balance_topup",
    "weekly_rebalance",
    "weekly_reminder",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class WhitelistEntry(BaseModel):
    key_id: str = ""
    key_name: str = ""
    email: str = ""
    display_name: str = ""
    enabled: bool = True


class TokenSnapshot(BaseModel):
    key_id: str
    key_name: str
    quota: float
    quota_used: float
    remaining: float
    status: str = ""
    updated_at: datetime = Field(default_factory=utc_now)


class TokenBalanceResponse(TokenSnapshot):
    email_hint: str = ""


class AllocationRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"bridge_record_{uuid4().hex}")
    key_id: str
    key_name: str
    action: BridgeAction
    amount: float = 0.0
    quota_before: float
    quota_after: float
    quota_used: float
    remaining_after: float
    success: bool
    email_sent: bool = False
    message: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class AllocationRecordPage(BaseModel):
    records: list[AllocationRecord]
    total: int
    page: int
    page_size: int


class CurrentUserTokenResponse(BaseModel):
    configured: bool
    linked: bool
    live: bool
    username: str
    keys: list[TokenBalanceResponse]
    total_quota: float = 0.0
    total_used: float = 0.0
    total_remaining: float = 0.0
    refreshed_at: datetime | None = None
    error: str = ""


class AutomationRunSummary(BaseModel):
    action: str
    checked: int = 0
    eligible: int = 0
    updated: int = 0
    skipped: int = 0
    emails_sent: int = 0
    errors: list[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None

    def finish(self) -> "AutomationRunSummary":
        self.finished_at = utc_now()
        return self
