from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from settings import ENVIRONMENT, PROJECT_ROOT


class ConfigRepository:
    """Read upload configuration for the current environment."""

    FILE_BY_ENVIRONMENT = {
        "debug": "upload_debug.yaml",
        "production": "upload_production.yaml",
    }

    def __init__(self, config_dir: Path, environment: str = ENVIRONMENT) -> None:
        self.config_dir = Path(config_dir)
        self.environment = environment
        self.data = self._load()

    @classmethod
    def from_environment(cls, environment: str = ENVIRONMENT) -> "ConfigRepository":
        config_dir = Path(PROJECT_ROOT) / "src" / "upload_handler" / "configs"
        return cls(config_dir=config_dir, environment=environment)

    @property
    def config_file_name(self) -> str:
        try:
            return self.FILE_BY_ENVIRONMENT[self.environment]
        except KeyError as exc:
            raise ValueError(f"Unsupported config environment: {self.environment}") from exc

    def get_upload_config(self, key: str) -> dict[str, Any]:
        value = self.data.get(key)
        if not isinstance(value, list) or not value:
            raise ValueError(f"Upload config '{key}' is missing or is not a non-empty list")
        if not isinstance(value[0], dict):
            raise ValueError(f"Upload config '{key}' first item must be a dict")
        return deepcopy(value[0])

    def _load(self) -> dict[str, Any]:
        config_path = self.config_dir / self.config_file_name
        if not config_path.exists():
            raise FileNotFoundError(f"Upload config file not found: {config_path}")

        with config_path.open("r", encoding="utf-8") as yaml_file:
            data = yaml.safe_load(yaml_file) or {}

        if not isinstance(data, dict):
            raise ValueError(f"Upload config file must contain a mapping: {config_path}")

        return data
