from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Callable, Literal, Protocol
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator

from core import config
from core.database import mongodb
from modules.bridge_tokens.client import BridgefloodsClient
from modules.bridge_tokens.emailer import BridgeEmailSettings
from modules.bridge_tokens.service import BridgeTokenSettings


CONFIGURATION_ID = "active"
CONFIGURATION_COLLECTION = "bridge_token_configuration"


class BridgeTokenConfigurationUnavailable(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BridgeTokenStoredConfiguration(BaseModel):
    schema_version: int = 1
    automation_enabled: bool = False
    base_url: str
    timezone: str = "Asia/Shanghai"
    quota_threshold: float = Field(ge=0)
    quota_increment: float = Field(gt=0)
    main_balance_alert_threshold: float = Field(ge=0)
    weekly_token_budget: float = Field(gt=0)
    allocation_lookback_days: int = Field(ge=1, le=365)
    min_weekly_allocation: float = Field(ge=0)
    min_rebalance_remaining: float = Field(ge=0)
    reminder_subject: str = Field(min_length=1, max_length=240)
    admin_email: str = Field(default="", max_length=320)
    email_provider: Literal["gmail", "smtp"] = "gmail"
    email_from: str = Field(default="", max_length=320)
    smtp_host: str = Field(default="", max_length=255)
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = Field(default="", max_length=320)
    smtp_use_ssl: bool = False
    smtp_starttls: bool = True
    access_token: str = ""
    refresh_token: str = ""
    smtp_password: str = ""
    updated_at: datetime = Field(default_factory=utc_now)
    updated_by: str = "env-migration"

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Bridgefloods API 地址必须是有效的 HTTP(S) URL")
        return normalized

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        normalized = value.strip()
        try:
            ZoneInfo(normalized)
        except Exception as exc:
            raise ValueError("时区名称无效") from exc
        return normalized

    @field_validator(
        "reminder_subject",
        "admin_email",
        "email_from",
        "smtp_host",
        "smtp_username",
        "access_token",
        "refresh_token",
        "smtp_password",
        "updated_by",
    )
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class BridgeTokenConfigurationUpdate(BaseModel):
    automation_enabled: bool
    base_url: str
    timezone: str
    quota_threshold: float = Field(ge=0)
    quota_increment: float = Field(gt=0)
    main_balance_alert_threshold: float = Field(ge=0)
    weekly_token_budget: float = Field(gt=0)
    allocation_lookback_days: int = Field(ge=1, le=365)
    min_weekly_allocation: float = Field(ge=0)
    min_rebalance_remaining: float = Field(ge=0)
    reminder_subject: str = Field(min_length=1, max_length=240)
    admin_email: str = Field(default="", max_length=320)
    email_provider: Literal["gmail", "smtp"]
    email_from: str = Field(default="", max_length=320)
    smtp_host: str = Field(default="", max_length=255)
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = Field(default="", max_length=320)
    smtp_use_ssl: bool = False
    smtp_starttls: bool = True
    access_token: str | None = Field(default=None, max_length=8000)
    refresh_token: str | None = Field(default=None, max_length=8000)
    smtp_password: str | None = Field(default=None, max_length=8000)


class BridgeTokenConfigurationResponse(BaseModel):
    source: Literal["mongodb"] = "mongodb"
    automation_enabled: bool
    base_url: str
    timezone: str
    quota_threshold: float
    quota_increment: float
    main_balance_alert_threshold: float
    weekly_token_budget: float
    allocation_lookback_days: int
    min_weekly_allocation: float
    min_rebalance_remaining: float
    reminder_subject: str
    admin_email: str
    email_provider: Literal["gmail", "smtp"]
    email_from: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_use_ssl: bool
    smtp_starttls: bool
    access_token_configured: bool
    refresh_token_configured: bool
    smtp_password_configured: bool
    gmail_token_configured: bool
    updated_at: datetime
    updated_by: str


class BridgeTokenConfigurationRepositoryProtocol(Protocol):
    def initialize(self) -> None: ...
    def get(self) -> BridgeTokenStoredConfiguration | None: ...
    def save(self, configuration: BridgeTokenStoredConfiguration) -> BridgeTokenStoredConfiguration: ...


class MongoBridgeTokenConfigurationRepository:
    def _collection(self):
        if mongodb.client is None and not mongodb.connect():
            raise BridgeTokenConfigurationUnavailable(
                "MongoDB 不可用，Bridge 自动化配置无法读取或保存"
            )
        return mongodb.get_database(config.MESSAGE_COLLECTION)[CONFIGURATION_COLLECTION]

    def initialize(self) -> None:
        self._collection().create_index("updated_at")

    def get(self) -> BridgeTokenStoredConfiguration | None:
        document = self._collection().find_one({"_id": CONFIGURATION_ID})
        if not document:
            return None
        payload = dict(document)
        payload.pop("_id", None)
        return BridgeTokenStoredConfiguration.model_validate(payload)

    def save(
        self,
        configuration: BridgeTokenStoredConfiguration,
    ) -> BridgeTokenStoredConfiguration:
        document = configuration.model_dump(mode="python")
        document["_id"] = CONFIGURATION_ID
        self._collection().replace_one(
            {"_id": CONFIGURATION_ID},
            document,
            upsert=True,
        )
        return configuration


class BridgeTokenConfigurationService:
    def __init__(
        self,
        *,
        repository: BridgeTokenConfigurationRepositoryProtocol,
        base_token_settings: BridgeTokenSettings,
        base_email_settings: BridgeEmailSettings,
        apply_configuration: Callable[
            [BridgeTokenStoredConfiguration, BridgeTokenSettings, BridgeEmailSettings],
            None,
        ],
        validate_credentials: Callable[[BridgeTokenStoredConfiguration], None] | None = None,
    ) -> None:
        self.repository = repository
        self.base_token_settings = base_token_settings
        self.base_email_settings = base_email_settings
        self._apply_configuration = apply_configuration
        self._validate_credentials = (
            validate_credentials or self._validate_bridge_credentials
        )

    def _validate_bridge_credentials(
        self,
        configuration: BridgeTokenStoredConfiguration,
    ) -> None:
        try:
            BridgefloodsClient(
                base_url=configuration.base_url,
                access_token=configuration.access_token,
                refresh_token=configuration.refresh_token,
                timeout_seconds=self.base_token_settings.request_timeout_seconds,
            ).get_profile()
        except Exception as exc:
            raise ValueError("Bridgefloods 凭据验证失败，未开启自动化") from exc

    def _environment_configuration(self) -> BridgeTokenStoredConfiguration:
        token = self.base_token_settings
        email = self.base_email_settings
        return BridgeTokenStoredConfiguration(
            automation_enabled=token.automation_enabled,
            base_url=token.base_url,
            timezone=token.timezone,
            quota_threshold=token.monitor_threshold,
            quota_increment=token.topup_increment,
            main_balance_alert_threshold=token.main_balance_threshold,
            weekly_token_budget=token.weekly_budget,
            allocation_lookback_days=token.lookback_days,
            min_weekly_allocation=token.minimum_weekly_allocation,
            min_rebalance_remaining=token.minimum_rebalance_remaining,
            reminder_subject=token.reminder_subject,
            admin_email=token.admin_email,
            email_provider=email.provider if email.provider in {"gmail", "smtp"} else "gmail",
            email_from=email.from_address,
            smtp_host=email.smtp_host,
            smtp_port=email.smtp_port,
            smtp_username=email.smtp_username,
            smtp_use_ssl=email.smtp_use_ssl,
            smtp_starttls=email.smtp_starttls,
            access_token=token.access_token,
            refresh_token=token.refresh_token,
            smtp_password=email.smtp_password,
            updated_by="env-migration",
        )

    def _runtime_settings(
        self,
        stored: BridgeTokenStoredConfiguration,
    ) -> tuple[BridgeTokenSettings, BridgeEmailSettings]:
        token_settings = replace(
            self.base_token_settings,
            base_url=stored.base_url,
            access_token=stored.access_token,
            refresh_token=stored.refresh_token,
            timezone=stored.timezone,
            monitor_threshold=stored.quota_threshold,
            topup_increment=stored.quota_increment,
            main_balance_threshold=stored.main_balance_alert_threshold,
            weekly_budget=stored.weekly_token_budget,
            lookback_days=stored.allocation_lookback_days,
            minimum_weekly_allocation=stored.min_weekly_allocation,
            minimum_rebalance_remaining=stored.min_rebalance_remaining,
            reminder_subject=stored.reminder_subject,
            admin_email=stored.admin_email,
            automation_enabled=stored.automation_enabled,
        )
        email_settings = replace(
            self.base_email_settings,
            provider=stored.email_provider,
            from_address=stored.email_from,
            smtp_host=stored.smtp_host,
            smtp_port=stored.smtp_port,
            smtp_username=stored.smtp_username,
            smtp_password=stored.smtp_password,
            smtp_use_ssl=stored.smtp_use_ssl,
            smtp_starttls=stored.smtp_starttls,
        )
        return token_settings, email_settings

    def _apply(self, stored: BridgeTokenStoredConfiguration) -> None:
        token_settings, email_settings = self._runtime_settings(stored)
        self._apply_configuration(stored, token_settings, email_settings)

    def initialize(self) -> BridgeTokenStoredConfiguration:
        self.repository.initialize()
        stored = self.repository.get()
        if stored is None:
            stored = self.repository.save(self._environment_configuration())
        self._apply(stored)
        return stored

    def get_configuration(self) -> BridgeTokenConfigurationResponse:
        stored = self.repository.get()
        if stored is None:
            stored = self.initialize()
        return self._response(stored)

    def update_configuration(
        self,
        payload: BridgeTokenConfigurationUpdate,
        *,
        updated_by: str,
    ) -> BridgeTokenConfigurationResponse:
        current = self.repository.get() or self._environment_configuration()
        values = payload.model_dump(
            exclude={"access_token", "refresh_token", "smtp_password"}
        )
        candidate = BridgeTokenStoredConfiguration(
            **values,
            access_token=(payload.access_token or "").strip() or current.access_token,
            refresh_token=(payload.refresh_token or "").strip() or current.refresh_token,
            smtp_password=(payload.smtp_password or "").strip() or current.smtp_password,
            updated_at=utc_now(),
            updated_by=updated_by,
        )
        if candidate.automation_enabled and not (
            candidate.access_token or candidate.refresh_token
        ):
            raise ValueError("开启自动化前必须配置 Bridgefloods access token 或 refresh token")
        credentials_changed = bool(
            (payload.access_token or "").strip()
            or (payload.refresh_token or "").strip()
        )
        if candidate.automation_enabled and (
            not current.automation_enabled or credentials_changed
        ):
            self._validate_credentials(candidate)
        saved = self.repository.save(candidate)
        self._apply(saved)
        return self._response(saved)

    def _response(
        self,
        stored: BridgeTokenStoredConfiguration,
    ) -> BridgeTokenConfigurationResponse:
        return BridgeTokenConfigurationResponse(
            **stored.model_dump(
                exclude={"access_token", "refresh_token", "smtp_password"}
            ),
            access_token_configured=bool(stored.access_token),
            refresh_token_configured=bool(stored.refresh_token),
            smtp_password_configured=bool(stored.smtp_password),
            gmail_token_configured=self.base_email_settings.gmail_token_path.is_file(),
        )
