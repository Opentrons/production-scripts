from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from threading import RLock
from typing import Any, Callable
from zoneinfo import ZoneInfo

from modules.auth.store import AuthUser
from modules.bridge_tokens.client import BridgefloodsClient
from modules.bridge_tokens.emailer import BridgeEmailSender
from modules.bridge_tokens.models import (
    AllocationRecord,
    AllocationRecordPage,
    AutomationRunSummary,
    CurrentUserTokenResponse,
    TokenBalanceResponse,
    TokenSnapshot,
    WhitelistEntry,
    utc_now,
)
from modules.bridge_tokens.repository import BridgeTokenRepository


MAIN_BALANCE_ALERT_SUBJECT = "Kimmy，小桥token余额告急，记得充值。"


class BridgeTokenConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class BridgeTokenSettings:
    base_url: str
    access_token: str
    refresh_token: str
    whitelist_path: Path
    timezone: str = "Asia/Shanghai"
    page_size: int = 100
    request_timeout_seconds: float = 30.0
    monitor_threshold: float = 50.0
    topup_increment: float = 100.0
    main_balance_threshold: float = 50.0
    weekly_budget: float = 2000.0
    lookback_days: int = 14
    minimum_weekly_allocation: float = 50.0
    minimum_rebalance_remaining: float = 20.0
    reminder_subject: str = "Bridgefloods API token 使用提醒"
    admin_email: str = ""
    automation_enabled: bool = True
    scheduler_poll_seconds: float = 30.0

    @property
    def configured(self) -> bool:
        return self.whitelist_path.is_file() and bool(self.access_token or self.refresh_token)


@dataclass(frozen=True)
class MatchedKey:
    entry: WhitelistEntry
    key: dict[str, Any]

    @property
    def key_id(self) -> str:
        return str(self.key.get("id") or self.key.get("key_id") or "").strip()

    @property
    def key_name(self) -> str:
        return str(
            self.key.get("name")
            or self.entry.key_name
            or self.entry.display_name
            or self.key_id
        ).strip()

    @property
    def quota(self) -> float:
        return as_float(self.key.get("quota"))

    @property
    def quota_used(self) -> float:
        return as_float(self.key.get("quota_used"))


@dataclass(frozen=True)
class PendingMutation:
    action: str
    matched: MatchedKey
    amount: float
    quota_before: float
    quota_after: float
    quota_used: float


def as_bool(value: Any, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on", "enabled"}


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def available_balance(profile: dict[str, Any]) -> float | None:
    for name in (
        "balance",
        "quota_balance",
        "available_balance",
        "remaining_balance",
        "credits",
    ):
        value = profile.get(name)
        if value not in (None, ""):
            return as_float(value)
    return None


def entry_matches_key(entry: WhitelistEntry, key: dict[str, Any]) -> bool:
    key_id = str(key.get("id") or key.get("key_id") or "").strip()
    if entry.key_id:
        return entry.key_id == key_id
    key_name = str(key.get("name") or "").strip()
    return bool(entry.key_name and entry.key_name == key_name)


def allocate_budget(
    key_ids: list[str],
    weights: dict[str, float],
    budget: float,
    minimum: float,
) -> dict[str, float]:
    if not key_ids:
        return {}
    normalized_budget = max(round(budget, 2), 0.0)
    minimum_each = min(max(minimum, 0.0), normalized_budget / len(key_ids))
    allocations = {key_id: minimum_each for key_id in key_ids}
    remaining = max(normalized_budget - minimum_each * len(key_ids), 0.0)
    total_weight = sum(max(weights.get(key_id, 0.0), 0.0) for key_id in key_ids)
    if remaining > 0:
        if total_weight <= 0:
            for key_id in key_ids:
                allocations[key_id] += remaining / len(key_ids)
        else:
            for key_id in key_ids:
                allocations[key_id] += (
                    remaining * max(weights.get(key_id, 0.0), 0.0) / total_weight
                )
    rounded = {key_id: round(value, 2) for key_id, value in allocations.items()}
    delta = round(normalized_budget - sum(rounded.values()), 2)
    if delta:
        target_id = max(key_ids, key=lambda key_id: (weights.get(key_id, 0.0), key_id))
        rounded[target_id] = round(rounded[target_id] + delta, 2)
    return rounded


def actual_cost_from_stats(stats: dict[str, Any]) -> float:
    for name in ("total_actual_cost", "actual_cost", "total_cost", "cost"):
        if name in stats:
            return as_float(stats.get(name))
    return 0.0


def mask_email(value: str) -> str:
    local, separator, domain = value.partition("@")
    if not separator:
        return ""
    if len(local) <= 2:
        masked_local = f"{local[:1]}*"
    else:
        masked_local = f"{local[:1]}{'*' * min(4, len(local) - 2)}{local[-1:]}"
    return f"{masked_local}@{domain}"


class BridgeTokenService:
    def __init__(
        self,
        *,
        settings: BridgeTokenSettings,
        repository: BridgeTokenRepository,
        email_sender: BridgeEmailSender,
        client_factory: Callable[[], BridgefloodsClient] | None = None,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.email_sender = email_sender
        self._client_factory = client_factory or self._default_client
        self._lock = RLock()
        self._client_lock = RLock()
        self._client: BridgefloodsClient | None = None

    @property
    def configured(self) -> bool:
        return self.settings.configured

    def initialize(self) -> None:
        self.repository.initialize()

    def update_settings(self, settings: BridgeTokenSettings) -> None:
        with self._lock, self._client_lock:
            self.settings = settings
            self._client = None

    def _default_client(self) -> BridgefloodsClient:
        with self._client_lock:
            if self._client is None:
                self._client = BridgefloodsClient(
                    base_url=self.settings.base_url,
                    access_token=self.settings.access_token,
                    refresh_token=self.settings.refresh_token,
                    timeout_seconds=self.settings.request_timeout_seconds,
                )
            return self._client

    def _timezone(self) -> ZoneInfo:
        try:
            return ZoneInfo(self.settings.timezone)
        except Exception:
            return ZoneInfo("Asia/Shanghai")

    def load_whitelist(self) -> list[WhitelistEntry]:
        path = self.settings.whitelist_path
        if not path.is_file():
            raise BridgeTokenConfigurationError("Bridgefloods whitelist is not configured")
        entries: list[WhitelistEntry] = []
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                entry = WhitelistEntry(
                    key_id=str(row.get("key_id") or "").strip(),
                    key_name=str(row.get("key_name") or "").strip(),
                    email=str(row.get("email") or "").strip(),
                    display_name=str(
                        row.get("display_name") or row.get("key_name") or ""
                    ).strip(),
                    enabled=as_bool(row.get("enabled"), default=True),
                )
                if entry.enabled and not entry.key_id and not entry.key_name:
                    raise BridgeTokenConfigurationError(
                        "Enabled whitelist rows require key_id or key_name"
                    )
                entries.append(entry)
        return entries

    @staticmethod
    def _match_entries(
        entries: list[WhitelistEntry],
        keys: list[dict[str, Any]],
    ) -> tuple[list[MatchedKey], list[str]]:
        matched: list[MatchedKey] = []
        errors: list[str] = []
        for entry in entries:
            found = [key for key in keys if entry_matches_key(entry, key)]
            label = entry.display_name or entry.key_name or entry.key_id
            if not found:
                errors.append(f"{label}: whitelist key was not found")
                continue
            if len(found) > 1 and not entry.key_id:
                errors.append(f"{label}: key_name matched more than one key")
                continue
            item = MatchedKey(entry=entry, key=found[0])
            if not item.key_id:
                errors.append(f"{label}: API response did not include key id")
                continue
            matched.append(item)
        return matched, errors

    @staticmethod
    def _snapshot(item: MatchedKey, *, updated_at: datetime | None = None) -> TokenSnapshot:
        return TokenSnapshot(
            key_id=item.key_id,
            key_name=item.key_name,
            quota=item.quota,
            quota_used=item.quota_used,
            remaining=item.quota - item.quota_used,
            status=str(item.key.get("status") or ""),
            updated_at=updated_at or utc_now(),
        )

    def _save_snapshots(self, matched: list[MatchedKey]) -> list[TokenSnapshot]:
        now = utc_now()
        snapshots = [self._snapshot(item, updated_at=now) for item in matched]
        for snapshot in snapshots:
            self.repository.save_snapshot(snapshot)
        return snapshots

    def current_user_dashboard(
        self,
        user: AuthUser,
        *,
        refresh: bool = True,
    ) -> CurrentUserTokenResponse:
        if not self.configured:
            return CurrentUserTokenResponse(
                configured=False,
                linked=False,
                live=False,
                username=user.username,
                keys=[],
                error="not_configured",
            )
        try:
            entries = [entry for entry in self.load_whitelist() if entry.enabled]
        except BridgeTokenConfigurationError:
            entries = []
        if not entries:
            return CurrentUserTokenResponse(
                configured=True,
                linked=False,
                live=False,
                username=user.username,
                keys=[],
                error="no_enabled_keys",
            )

        live = False
        error = ""
        snapshots: list[TokenSnapshot] = []
        if refresh:
            try:
                keys = self._client_factory().list_keys(self.settings.page_size)
                matched, match_errors = self._match_entries(entries, keys)
                snapshots = self._save_snapshots(matched)
                live = not match_errors and len(matched) == len(entries)
                if match_errors:
                    error = "key_match_failed"
            except Exception:
                error = "live_refresh_failed"

        if not snapshots:
            key_ids = {entry.key_id for entry in entries if entry.key_id}
            key_names = {entry.key_name.casefold() for entry in entries if entry.key_name}
            snapshots = [
                snapshot
                for snapshot in self.repository.list_snapshots()
                if snapshot.key_id in key_ids or snapshot.key_name.casefold() in key_names
            ]

        emails_by_id = {entry.key_id: entry.email for entry in entries if entry.key_id}
        emails_by_name = {entry.key_name.casefold(): entry.email for entry in entries}
        response_keys = [
            TokenBalanceResponse(
                **snapshot.model_dump(),
                email_hint=mask_email(
                    emails_by_id.get(snapshot.key_id)
                    or emails_by_name.get(snapshot.key_name.casefold(), "")
                ),
            )
            for snapshot in sorted(snapshots, key=lambda item: item.key_name.casefold())
        ]
        refreshed_at = max((item.updated_at for item in response_keys), default=None)
        return CurrentUserTokenResponse(
            configured=True,
            linked=True,
            live=live,
            username=user.username,
            keys=response_keys,
            total_quota=round(sum(item.quota for item in response_keys), 4),
            total_used=round(sum(item.quota_used for item in response_keys), 4),
            total_remaining=round(sum(item.remaining for item in response_keys), 4),
            refreshed_at=refreshed_at,
            error=error,
        )

    def list_user_records(
        self,
        _user: AuthUser,
        *,
        action: str | None,
        page: int,
        page_size: int,
    ) -> AllocationRecordPage:
        if not self.settings.whitelist_path.is_file():
            return AllocationRecordPage(records=[], total=0, page=page, page_size=page_size)
        entries = [entry for entry in self.load_whitelist() if entry.enabled]
        key_ids = {entry.key_id for entry in entries if entry.key_id}
        key_names = {entry.key_name for entry in entries if entry.key_name}
        for snapshot in self.repository.list_snapshots():
            if snapshot.key_name.casefold() in {name.casefold() for name in key_names}:
                key_ids.add(snapshot.key_id)
        records, total = self.repository.list_records(
            key_ids=key_ids,
            key_names=key_names,
            action=action,
            page=page,
            page_size=page_size,
        )
        return AllocationRecordPage(
            records=records,
            total=total,
            page=page,
            page_size=page_size,
        )

    def _record_failure(
        self,
        *,
        action: str,
        item: MatchedKey,
        amount: float,
        target_quota: float,
        message: str,
    ) -> None:
        self.repository.save_record(
            AllocationRecord(
                key_id=item.key_id,
                key_name=item.key_name,
                action=action,
                amount=amount,
                quota_before=item.quota,
                quota_after=target_quota,
                quota_used=item.quota_used,
                remaining_after=target_quota - item.quota_used,
                success=False,
                message=message,
            )
        )

    def _verify_mutations(
        self,
        *,
        client: BridgefloodsClient,
        enabled_entries: list[WhitelistEntry],
        pending: list[PendingMutation],
        summary: AutomationRunSummary,
    ) -> None:
        if not pending:
            return
        try:
            final_keys = client.list_keys(self.settings.page_size)
        except Exception:
            for mutation in pending:
                self._record_failure(
                    action=mutation.action,
                    item=mutation.matched,
                    amount=mutation.amount,
                    target_quota=mutation.quota_after,
                    message="updated_but_verification_failed",
                )
            summary.errors.append("Updated quotas could not be verified")
            return

        final_matches, final_errors = self._match_entries(enabled_entries, final_keys)
        summary.errors.extend(final_errors)
        self._save_snapshots(final_matches)
        final_by_id = {item.key_id: item for item in final_matches}
        for mutation in pending:
            final = final_by_id.get(mutation.matched.key_id)
            success = final is not None and abs(final.quota - mutation.quota_after) <= 0.01
            if success:
                summary.updated += 1
            else:
                summary.errors.append(f"{mutation.matched.key_name}: quota verification failed")
            quota_after = final.quota if final is not None else mutation.quota_after
            quota_used = final.quota_used if final is not None else mutation.quota_used
            self.repository.save_record(
                AllocationRecord(
                    key_id=mutation.matched.key_id,
                    key_name=mutation.matched.key_name,
                    action=mutation.action,
                    amount=mutation.amount,
                    quota_before=mutation.quota_before,
                    quota_after=quota_after,
                    quota_used=quota_used,
                    remaining_after=quota_after - quota_used,
                    success=success,
                    message="" if success else "verification_failed",
                )
            )

    def _usage_costs(
        self,
        client: BridgefloodsClient,
        matched: list[MatchedKey],
        *,
        start_date: str,
        end_date: str,
        summary: AutomationRunSummary,
    ) -> dict[str, float]:
        costs: dict[str, float] = {}
        for item in matched:
            try:
                stats = client.get_usage_stats(
                    start_date=start_date,
                    end_date=end_date,
                    key_id=item.key_id,
                )
                costs[item.key_id] = actual_cost_from_stats(stats)
            except Exception:
                costs[item.key_id] = 0.0
                summary.errors.append(f"{item.key_name}: usage history could not be loaded")
        return costs

    def _date_range_for_lookback(self, days: int) -> tuple[str, str]:
        current = datetime.now(self._timezone()).date()
        return (current - timedelta(days=max(days, 1))).isoformat(), current.isoformat()

    def _current_week_range(self) -> tuple[str, str]:
        current = datetime.now(self._timezone()).date()
        return (current - timedelta(days=current.weekday())).isoformat(), current.isoformat()

    def _notify_admin(
        self,
        subject: str,
        lines: list[str],
        summary: AutomationRunSummary,
    ) -> bool:
        if not self.settings.admin_email or not self.email_sender.configured:
            summary.errors.append("Administrator email is not configured")
            return False
        try:
            self.email_sender.send(self.settings.admin_email, subject, "\n".join(lines))
        except Exception:
            summary.errors.append("Administrator email delivery failed")
            return False
        return True

    def _handle_main_balance_alert(
        self,
        balance: float,
        summary: AutomationRunSummary,
    ) -> None:
        state = self.repository.get_state("main_balance_alert")
        was_sent = bool(state.get("low_alert_sent"))
        is_low = balance < self.settings.main_balance_threshold
        if is_low and not was_sent:
            sent = self._notify_admin(
                MAIN_BALANCE_ALERT_SUBJECT,
                [
                    f"当前小桥 Bridgefloods 总账户可用余额为 ${balance:.4f}。",
                    f"告警阈值为低于 ${self.settings.main_balance_threshold:.2f}，请及时充值。",
                ],
                summary,
            )
            if sent:
                state["low_alert_sent"] = True
                state["last_alert_at"] = utc_now().isoformat()
        elif not is_low and was_sent:
            state["low_alert_sent"] = False
            state["recovered_at"] = utc_now().isoformat()
        state["last_balance"] = round(balance, 4)
        state["last_checked_at"] = utc_now().isoformat()
        self.repository.set_state("main_balance_alert", state)

    def run_monitor(self) -> AutomationRunSummary:
        with self._lock:
            summary = AutomationRunSummary(action="low_balance_monitor")
            entries = [entry for entry in self.load_whitelist() if entry.enabled]
            client = self._client_factory()
            keys = client.list_keys(self.settings.page_size)
            matched, match_errors = self._match_entries(entries, keys)
            summary.errors.extend(match_errors)
            summary.checked = len(matched)
            self._save_snapshots(matched)

            try:
                balance = available_balance(client.get_profile())
            except Exception:
                balance = None
            if balance is None:
                summary.errors.append("Main account balance could not be confirmed")
            else:
                self._handle_main_balance_alert(balance, summary)

            pending: list[PendingMutation] = []
            urgent_lines: list[str] = []
            cached_balance = balance
            for item in sorted(
                matched,
                key=lambda current: (current.quota - current.quota_used, current.key_name),
            ):
                remaining = item.quota - item.quota_used
                if item.quota <= 0 or remaining > self.settings.monitor_threshold:
                    summary.skipped += 1
                    continue
                summary.eligible += 1
                if cached_balance is None:
                    summary.skipped += 1
                    self._record_failure(
                        action="low_balance_topup",
                        item=item,
                        amount=0,
                        target_quota=item.quota,
                        message="main_balance_unavailable",
                    )
                    continue

                amount = self.settings.topup_increment
                if cached_balance < amount:
                    emergency_minimum = max(self.settings.monitor_threshold - remaining, 0.0)
                    if remaining <= 0 and cached_balance > emergency_minimum:
                        amount = cached_balance
                        summary.errors.append(
                            f"{item.key_name}: only a partial emergency top-up was available"
                        )
                    else:
                        summary.skipped += 1
                        summary.errors.append(f"{item.key_name}: main balance is too low for top-up")
                        self._record_failure(
                            action="low_balance_topup",
                            item=item,
                            amount=0,
                            target_quota=item.quota,
                            message="main_balance_too_low",
                        )
                        continue
                if amount <= 0:
                    summary.skipped += 1
                    continue
                target = item.quota + amount
                try:
                    next_status = (
                        "active"
                        if str(item.key.get("status") or "") == "quota_exhausted"
                        else None
                    )
                    client.update_key_quota(item.key_id, target, status=next_status)
                except Exception:
                    summary.errors.append(f"{item.key_name}: top-up request failed")
                    self._record_failure(
                        action="low_balance_topup",
                        item=item,
                        amount=amount,
                        target_quota=target,
                        message="update_failed",
                    )
                    continue
                cached_balance -= amount
                pending.append(
                    PendingMutation(
                        action="low_balance_topup",
                        matched=item,
                        amount=amount,
                        quota_before=item.quota,
                        quota_after=target,
                        quota_used=item.quota_used,
                    )
                )
                if remaining <= 0:
                    urgent_lines.append(
                        f"{item.key_name}: remaining={remaining:.4f}, target_quota={target:.4f}"
                    )

            self._verify_mutations(
                client=client,
                enabled_entries=entries,
                pending=pending,
                summary=summary,
            )
            if urgent_lines:
                self._notify_admin(
                    "[Bridgefloods] API quota automation needs attention",
                    [f"[urgent] {line}" for line in urgent_lines],
                    summary,
                )
            return summary.finish()

    def run_weekly_allocation(self) -> AutomationRunSummary:
        with self._lock:
            summary = AutomationRunSummary(action="weekly_allocation")
            entries = [entry for entry in self.load_whitelist() if entry.enabled]
            client = self._client_factory()
            keys = client.list_keys(self.settings.page_size)
            matched, match_errors = self._match_entries(entries, keys)
            summary.errors.extend(match_errors)
            summary.checked = len(matched)
            self._save_snapshots(matched)
            start_date, end_date = self._date_range_for_lookback(self.settings.lookback_days)
            history = self._usage_costs(
                client,
                matched,
                start_date=start_date,
                end_date=end_date,
                summary=summary,
            )
            allocations = allocate_budget(
                [item.key_id for item in matched],
                history,
                self.settings.weekly_budget,
                self.settings.minimum_weekly_allocation,
            )
            pending: list[PendingMutation] = []
            for item in matched:
                amount = allocations.get(item.key_id, 0.0)
                target = item.quota_used + amount
                try:
                    client.update_key_quota(item.key_id, target, status="active")
                except Exception:
                    summary.errors.append(f"{item.key_name}: weekly allocation failed")
                    self._record_failure(
                        action="weekly_allocation",
                        item=item,
                        amount=amount,
                        target_quota=target,
                        message="update_failed",
                    )
                    continue
                pending.append(
                    PendingMutation(
                        action="weekly_allocation",
                        matched=item,
                        amount=amount,
                        quota_before=item.quota,
                        quota_after=target,
                        quota_used=item.quota_used,
                    )
                )
            self._verify_mutations(
                client=client,
                enabled_entries=entries,
                pending=pending,
                summary=summary,
            )
            return summary.finish()

    def run_weekly_rebalance(self) -> AutomationRunSummary:
        with self._lock:
            summary = AutomationRunSummary(action="weekly_rebalance")
            entries = [entry for entry in self.load_whitelist() if entry.enabled]
            client = self._client_factory()
            keys = client.list_keys(self.settings.page_size)
            matched, match_errors = self._match_entries(entries, keys)
            summary.errors.extend(match_errors)
            summary.checked = len(matched)
            self._save_snapshots(matched)
            week_start, today = self._current_week_range()
            history_start, history_end = self._date_range_for_lookback(
                self.settings.lookback_days
            )
            week_usage = self._usage_costs(
                client,
                matched,
                start_date=week_start,
                end_date=today,
                summary=summary,
            )
            history_usage = self._usage_costs(
                client,
                matched,
                start_date=history_start,
                end_date=history_end,
                summary=summary,
            )
            remaining_budget = max(
                self.settings.weekly_budget - sum(week_usage.values()),
                0.0,
            )
            weights = {
                item.key_id: max(week_usage.get(item.key_id, 0.0), 0.0) * 2
                + max(history_usage.get(item.key_id, 0.0), 0.0)
                for item in matched
            }
            allocations = allocate_budget(
                [item.key_id for item in matched],
                weights,
                remaining_budget,
                self.settings.minimum_rebalance_remaining,
            )
            pending: list[PendingMutation] = []
            for item in matched:
                target = max(item.quota_used, week_usage.get(item.key_id, 0.0)) + allocations.get(
                    item.key_id,
                    0.0,
                )
                amount = target - item.quota
                try:
                    client.update_key_quota(item.key_id, target, status="active")
                except Exception:
                    summary.errors.append(f"{item.key_name}: weekly rebalance failed")
                    self._record_failure(
                        action="weekly_rebalance",
                        item=item,
                        amount=amount,
                        target_quota=target,
                        message="update_failed",
                    )
                    continue
                pending.append(
                    PendingMutation(
                        action="weekly_rebalance",
                        matched=item,
                        amount=amount,
                        quota_before=item.quota,
                        quota_after=target,
                        quota_used=item.quota_used,
                    )
                )
            self._verify_mutations(
                client=client,
                enabled_entries=entries,
                pending=pending,
                summary=summary,
            )
            return summary.finish()

    def run_weekly_reminders(self) -> AutomationRunSummary:
        with self._lock:
            summary = AutomationRunSummary(action="weekly_reminder")
            entries = [entry for entry in self.load_whitelist() if entry.enabled]
            client = self._client_factory()
            keys = client.list_keys(self.settings.page_size)
            matched, match_errors = self._match_entries(entries, keys)
            summary.errors.extend(match_errors)
            summary.checked = len(matched)
            self._save_snapshots(matched)

            recipients: dict[str, list[MatchedKey]] = {}
            for item in matched:
                if not item.entry.email:
                    summary.skipped += 1
                    summary.errors.append(f"{item.key_name}: reminder email is missing")
                    self._record_failure(
                        action="weekly_reminder",
                        item=item,
                        amount=0,
                        target_quota=item.quota,
                        message="email_missing",
                    )
                    continue
                recipients.setdefault(item.entry.email.casefold(), []).append(item)

            for recipient_items in recipients.values():
                email = recipient_items[0].entry.email
                display_name = (
                    recipient_items[0].entry.display_name
                    or recipient_items[0].key_name
                    or "同事"
                )
                status_parts = [
                    f"{item.key_name} ${item.quota_used:.2f} / ${item.quota:.2f}"
                    for item in recipient_items
                ]
                subject = (
                    f"{self.settings.reminder_subject}现额度使用情况: "
                    + "; ".join(status_parts)
                )
                remaining_lines = [
                    f"- {item.key_name}：目前剩余 token 额度 {item.quota - item.quota_used:.4f}"
                    for item in recipient_items
                ]
                body = (
                    f"{display_name}，你好：\n\n"
                    "提醒你及时使用本周分配的 Bridgefloods API token 额度，避免额度闲置浪费。\n"
                    "当前额度情况：\n"
                    + "\n".join(remaining_lines)
                    + "\n如你已经不需要当前额度，请及时告知管理员调整分配。\n\n谢谢。"
                )
                delivered = False
                message = ""
                try:
                    self.email_sender.send(email, subject, body)
                    delivered = True
                    summary.emails_sent += 1
                except Exception:
                    message = "email_delivery_failed"
                    summary.errors.append(f"{display_name}: reminder email delivery failed")
                for item in recipient_items:
                    self.repository.save_record(
                        AllocationRecord(
                            key_id=item.key_id,
                            key_name=item.key_name,
                            action="weekly_reminder",
                            amount=0,
                            quota_before=item.quota,
                            quota_after=item.quota,
                            quota_used=item.quota_used,
                            remaining_after=item.quota - item.quota_used,
                            success=delivered,
                            email_sent=delivered,
                            message=message,
                        )
                    )
            if self.settings.admin_email:
                self._notify_admin(
                    "[Bridgefloods] Weekly API reminder summary",
                    [
                        f"Enabled whitelist entries: {len(entries)}",
                        f"Reminder emails sent: {summary.emails_sent}",
                        f"Skipped: {summary.skipped}",
                        f"Errors: {len(summary.errors)}",
                    ],
                    summary,
                )
            return summary.finish()

    def execute_scheduled(self, action: str, slot: str) -> AutomationRunSummary | None:
        if not self.configured or not self.repository.claim_run(action=action, slot=slot):
            return None
        try:
            if action == "monitor":
                summary = self.run_monitor()
            elif action == "weekly_allocation":
                summary = self.run_weekly_allocation()
            elif action == "weekly_reminder":
                summary = self.run_weekly_reminders()
            elif action == "weekly_rebalance":
                summary = self.run_weekly_rebalance()
            else:
                raise ValueError(f"Unsupported Bridge token action: {action}")
        except Exception as exc:
            summary = AutomationRunSummary(
                action=action,
                errors=[str(exc) or "Automation run failed before completion"],
            ).finish()
        self.repository.finish_run(
            action=action,
            slot=slot,
            summary=summary.model_dump(mode="json"),
        )
        return summary
