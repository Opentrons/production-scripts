from __future__ import annotations

from core import config
from modules.bridge_tokens.configuration import (
    BridgeTokenConfigurationService,
    BridgeTokenStoredConfiguration,
    MongoBridgeTokenConfigurationRepository,
)
from modules.bridge_tokens.emailer import BridgeEmailSender, BridgeEmailSettings
from modules.bridge_tokens.repository import BridgeTokenRepository
from modules.bridge_tokens.scheduler import BridgeTokenScheduler
from modules.bridge_tokens.service import BridgeTokenService, BridgeTokenSettings


bridge_token_settings = BridgeTokenSettings(
    base_url=config.BRIDGEFLOODS_BASE_URL,
    access_token=config.BRIDGEFLOODS_ACCESS_TOKEN,
    refresh_token=config.BRIDGEFLOODS_REFRESH_TOKEN,
    whitelist_path=config.BRIDGEFLOODS_WHITELIST_PATH,
    timezone=config.BRIDGEFLOODS_TIMEZONE,
    page_size=config.BRIDGEFLOODS_PAGE_SIZE,
    request_timeout_seconds=config.BRIDGEFLOODS_REQUEST_TIMEOUT_SECONDS,
    monitor_threshold=config.BRIDGEFLOODS_QUOTA_THRESHOLD,
    topup_increment=config.BRIDGEFLOODS_QUOTA_INCREMENT,
    main_balance_threshold=config.BRIDGEFLOODS_MAIN_BALANCE_ALERT_THRESHOLD,
    weekly_budget=config.BRIDGEFLOODS_WEEKLY_TOKEN_BUDGET,
    lookback_days=config.BRIDGEFLOODS_ALLOCATION_LOOKBACK_DAYS,
    minimum_weekly_allocation=config.BRIDGEFLOODS_MIN_WEEKLY_ALLOCATION,
    minimum_rebalance_remaining=config.BRIDGEFLOODS_MIN_REBALANCE_REMAINING,
    reminder_subject=config.BRIDGEFLOODS_REMINDER_SUBJECT,
    admin_email=config.BRIDGEFLOODS_ADMIN_EMAIL,
    automation_enabled=config.BRIDGEFLOODS_AUTOMATION_ENABLED,
    scheduler_poll_seconds=config.BRIDGEFLOODS_SCHEDULER_POLL_SECONDS,
)

bridge_email_settings = BridgeEmailSettings(
    provider=config.BRIDGEFLOODS_EMAIL_PROVIDER,
    from_address=config.BRIDGEFLOODS_EMAIL_FROM,
    gmail_token_path=config.BRIDGEFLOODS_GMAIL_TOKEN_PATH,
    smtp_host=config.BRIDGEFLOODS_SMTP_HOST,
    smtp_port=config.BRIDGEFLOODS_SMTP_PORT,
    smtp_username=config.BRIDGEFLOODS_SMTP_USERNAME,
    smtp_password=config.BRIDGEFLOODS_SMTP_PASSWORD,
    smtp_use_ssl=config.BRIDGEFLOODS_SMTP_USE_SSL,
    smtp_starttls=config.BRIDGEFLOODS_SMTP_STARTTLS,
)
bridge_email_sender = BridgeEmailSender(bridge_email_settings)
bridge_token_repository = BridgeTokenRepository()
bridge_token_service = BridgeTokenService(
    settings=bridge_token_settings,
    repository=bridge_token_repository,
    email_sender=bridge_email_sender,
)
bridge_token_scheduler = BridgeTokenScheduler(bridge_token_service)


def apply_bridge_token_configuration(
    _: BridgeTokenStoredConfiguration,
    token_settings: BridgeTokenSettings,
    email_settings: BridgeEmailSettings,
) -> None:
    bridge_token_service.update_settings(token_settings)
    bridge_email_sender.update_settings(email_settings)
    bridge_token_scheduler.reconfigure()


bridge_token_configuration_repository = MongoBridgeTokenConfigurationRepository()
bridge_token_configuration_service = BridgeTokenConfigurationService(
    repository=bridge_token_configuration_repository,
    base_token_settings=bridge_token_settings,
    base_email_settings=bridge_email_settings,
    apply_configuration=apply_bridge_token_configuration,
)
