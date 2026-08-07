# Google proxy configuration

Put `skill_config.json` and the proxy subscription YAML in this directory for standalone operation. These runtime files are ignored by git.

The subscription is requested with a Clash user agent because Ghelper returns
Clash YAML only for compatible clients. Override it with
`GHELPER_SUBSCRIPTION_USER_AGENT` or `ghelper_subscription.user_agent` when a
provider requires another client identifier.

The unified API reads proxy configuration from `apps/backend/ghelper-test`. Override the directory with `PRODUCTION_PLATFORM_GHELPER_DIR` when deployment requires an external runtime location.
