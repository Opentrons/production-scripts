from __future__ import annotations

import json
from pathlib import Path
from threading import RLock

import core.config as setting
from core.logging import get_logger

logger = get_logger(__name__)

_LOCK = RLock()
_SIMULATING: bool | None = None


def _mode_file() -> Path:
    return Path(setting.DB_ROOT) / "mode.json"


def _read_mode_file() -> bool:
    path = _mode_file()
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to read simulating mode file %s: %s", path, exc)
        return False
    return bool(payload.get("simulating"))


def _write_mode_file(simulating: bool) -> None:
    path = _mode_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"simulating": bool(simulating)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def is_simulating() -> bool:
    global _SIMULATING
    with _LOCK:
        if _SIMULATING is None:
            _SIMULATING = _read_mode_file()
        return bool(_SIMULATING)


def set_simulating(enabled: bool) -> bool:
    global _SIMULATING
    value = bool(enabled)
    with _LOCK:
        _write_mode_file(value)
        _SIMULATING = value
    try:
        from modules.auth.dependencies import reset_auth_service

        reset_auth_service()
    except Exception as exc:
        logger.warning("Failed to reset auth service after mode change: %s", exc)
    logger.info("Simulating mode %s", "enabled" if value else "disabled")
    return value


def get_simulating_status() -> dict:
    simulating = is_simulating()
    active_dir = setting.get_active_db_dir()
    return {
        "simulating": simulating,
        "persistence": "sqlite" if simulating else "mongodb",
        "auth_persistence": setting.AUTH_STORAGE,
        "device_scan_mode": "simulated" if setting.use_simulated_device_scan() else "real",
        "db_root": str(setting.DB_ROOT),
        "active_db_dir": str(active_dir),
        "business_db_dir": str(setting.DB_BUSINESS_DIR),
        "simulating_db_dir": str(setting.DB_SIMULATING_DIR),
        "platform_db_path": str(setting.resolve_sqlite_path("platform.sqlite3")),
        "auth_db_path": str(setting.AUTH_DB_PATH),
    }


def ensure_db_layout() -> None:
    setting.DB_BUSINESS_DIR.mkdir(parents=True, exist_ok=True)
    setting.DB_SIMULATING_DIR.mkdir(parents=True, exist_ok=True)
    migrate_legacy_sqlite_files()


def migrate_legacy_sqlite_files() -> None:
    """Move historical data/*.sqlite3 files into db-storage/business/ once."""
    mapping = {
        "workflows.sqlite3": setting.DB_BUSINESS_DIR / "workflows.sqlite3",
        "sop_cache.sqlite3": setting.DB_BUSINESS_DIR / "sop_cache.sqlite3",
        "duro_cache.sqlite3": setting.DB_BUSINESS_DIR / "duro_cache.sqlite3",
    }
    data_dir = Path(setting.DATA_DIR)
    for name, destination in mapping.items():
        source = data_dir / name
        if not source.exists() or destination.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            source.replace(destination)
            logger.info("Migrated legacy sqlite %s -> %s", source, destination)
        except Exception as exc:
            logger.warning("Failed to migrate legacy sqlite %s: %s", source, exc)
