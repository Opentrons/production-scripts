# Google proxy configuration

Put `skill_config.json` and the proxy subscription YAML in this directory for standalone operation. These runtime files are ignored by git.

During local monorepo development, Productions Versions falls back to `productions-opentrons/backend/ghelper-test` when local proxy configuration is absent. The directory can also be overridden with `PRODUCTIONS_VERSIONS_GHELPER_DIR`.
