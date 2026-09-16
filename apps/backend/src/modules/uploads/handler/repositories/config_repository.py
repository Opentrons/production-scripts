from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import shutil
from typing import Any

import yaml

from core.config import ENVIRONMENT


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
        config_dir = Path(__file__).resolve().parents[1] / "configs"
        return cls(config_dir=config_dir, environment=environment)

    @property
    def config_file_name(self) -> str:
        try:
            return self.FILE_BY_ENVIRONMENT[self.environment]
        except KeyError as exc:
            raise ValueError(f"Unsupported config environment: {self.environment}") from exc

    @property
    def config_path(self) -> Path:
        return self.config_dir / self.config_file_name

    @classmethod
    def copy_environment_config(cls, source: str, target: str) -> Path:
        repository = cls.from_environment(source)
        source_path = repository.config_path
        target_path = cls.from_environment(target).config_path
        shutil.copyfile(source_path, target_path)
        return target_path

    def get_upload_config(self, key: str) -> dict[str, Any]:
        # Settings can update the YAML while the process is running. Reload on
        # every upload so a long-lived worker never uses a stale config snapshot.
        self.data = self._load()
        value = self.data.get(key)
        if not isinstance(value, list) or not value:
            raise ValueError(f"Upload config '{key}' is missing or is not a non-empty list")
        if not isinstance(value[0], dict):
            raise ValueError(f"Upload config '{key}' first item must be a dict")
        config = deepcopy(value[0])
        config["last_row"] = self.get_last_row_range()
        return config

    def get_last_row_range(self) -> str:
        value = self.data.get("last_row")
        return str(value or "F:I").strip() or "F:I"

    def update_last_row_range(self, value: str) -> str:
        normalized = str(value or "").strip().upper() or "F:I"
        data = self._load()
        data["last_row"] = normalized
        with self.config_path.open("w", encoding="utf-8") as yaml_file:
            yaml.safe_dump(data, yaml_file, allow_unicode=True, sort_keys=False, default_flow_style=False)
        self.data = data
        return normalized

    def update_upload_config(self, key: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Update one upload config block and persist it back to the YAML file."""
        data = self._load()
        value = data.get(key)
        if not isinstance(value, list) or not value or not isinstance(value[0], dict):
            raise ValueError(f"Upload config '{key}' is missing or invalid")
        config = value[0]
        config.update(deepcopy(updates))
        with self.config_path.open("w", encoding="utf-8") as yaml_file:
            yaml.safe_dump(data, yaml_file, allow_unicode=True, sort_keys=False, default_flow_style=False)
        self.data = data
        return deepcopy(config)

    def _load(self) -> dict[str, Any]:
        config_path = self.config_path
        if not config_path.exists():
            raise FileNotFoundError(f"Upload config file not found: {config_path}")

        with config_path.open("r", encoding="utf-8") as yaml_file:
            data = yaml.safe_load(yaml_file) or {}

        if not isinstance(data, dict):
            raise ValueError(f"Upload config file must contain a mapping: {config_path}")

        return data
