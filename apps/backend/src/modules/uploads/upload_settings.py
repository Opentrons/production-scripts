from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import core.config as setting
from core.database import mongodb
from modules.uploads.handler.models import Productions, TestTypes
from modules.uploads.handler.product_catalog import (
    UPLOAD_HANDLER_CONFIGS,
    get_upload_config_key,
    get_upload_handler_config,
)
from modules.uploads.handler.repositories.config_repository import ConfigRepository

from core.logging import get_logger

logger = get_logger(__name__)


DEFAULT_REQUIRE_FINISHED = True
DEFAULT_LAST_ROW_RANGE = "F:I"
MONGO_TIMEOUT_PATTERN = re.compile(r"(?P<target>[\w.-]+:\d+): timed out", re.IGNORECASE)
DEFAULT_OEM = "Opentrons"
DEFAULT_CONFIG_ENVIRONMENT = "production"
CONFIG_ENVIRONMENT_ALIASES = {
    "production": "production",
    "prod": "production",
    "eng": "debug",
    "engineering": "debug",
    "debug": "debug",
}
OEM_OPTIONS = ["Opentrons", "Ultima", "BD", "Millipore", "Sf"]
OEM_TO_YAML_KEY = {
    "Opentrons": "default",
    "Ultima": "ultima",
}
OEM_TO_LEGACY_PREFIX = {
    "Ultima": "Ultima",
}


def normalize_model(model: str | None) -> str:
    production = Productions.from_string(str(model or ""))
    if production is None:
        raise ValueError(f"Invalid product: {model}")
    return production.value


def normalize_test_type(test_type: str | None) -> str:
    normalized_test = TestTypes.from_string(str(test_type or ""))
    if normalized_test is None:
        raise ValueError(f"Invalid test type: {test_type}")
    return normalized_test.value


def normalize_oem(oem: str | None) -> str:
    value = str(oem or DEFAULT_OEM).strip() or DEFAULT_OEM
    for known in (*OEM_TO_YAML_KEY.keys(), "Millipore", "Sophion"):
        if value.lower() == known.lower():
            return known
    return value


def normalize_config_environment(environment: str | None) -> str:
    key = str(environment or DEFAULT_CONFIG_ENVIRONMENT).strip().lower()
    try:
        return CONFIG_ENVIRONMENT_ALIASES[key]
    except KeyError as exc:
        raise ValueError(f"Invalid upload config environment: {environment}") from exc


def sync_debug_upload_config_from_production() -> None:
    ConfigRepository.copy_environment_config("production", "debug")


def oem_yaml_key(oem: str) -> str:
    return OEM_TO_YAML_KEY.get(oem, oem.strip().lower())


def oem_legacy_key(oem: str, common_key: str) -> str:
    return f"{OEM_TO_LEGACY_PREFIX[oem]}{common_key}" if oem in OEM_TO_LEGACY_PREFIX else common_key


def get_oem_value(value: Any, oem: str, default: Any = "") -> Any:
    if not isinstance(value, dict):
        return default if value is None else value
    key = oem_yaml_key(oem)
    if key in value and value[key] not in (None, ""):
        return value[key]
    return value.get("default", default)


def set_oem_value(value: Any, oem: str, new_value: Any) -> dict[str, Any]:
    values = dict(value) if isinstance(value, dict) else {"default": value or ""}
    values[oem_yaml_key(oem)] = new_value
    return values


def get_legacy_oem_value(cfg: dict[str, Any], common_key: str, oem: str, default: Any = "") -> Any:
    selected_key = oem_legacy_key(oem, common_key)
    if selected_key in cfg and cfg[selected_key] not in (None, ""):
        return cfg[selected_key]
    return cfg.get(common_key, default)


def set_legacy_oem_value(cfg: dict[str, Any], common_key: str, oem: str, value: Any) -> None:
    cfg[oem_legacy_key(oem, common_key)] = value


def build_oem_options(config: dict[str, Any]) -> list[str]:
    if isinstance(config.get("oem"), dict):
        return [oem for oem in OEM_OPTIONS if oem in config["oem"]]
    options = {DEFAULT_OEM}
    for key in (config.get("ifcopytemplate") or {}).keys():
        if key == "default":
            continue
        for label, yaml_key in OEM_TO_YAML_KEY.items():
            if key == yaml_key:
                options.add(label)
    for copy_cfg in config.get("ifcopydata") or []:
        if "UltimacopyRange" in copy_cfg or "Ultimafailures" in copy_cfg:
            options.add("Ultima")
    for paste_cfg in config.get("ifpaste") or []:
        if "Ultimapastefileid" in paste_cfg or "UltimapastelineRange" in paste_cfg:
            options.add("Ultima")
    return [DEFAULT_OEM] + sorted(option for option in options if option != DEFAULT_OEM)


def build_legacy_oem_config(config: dict[str, Any], oem: str) -> dict[str, Any]:
    copy_data = (config.get("ifcopydata") or [{}])[0]
    paste = (config.get("ifpaste") or [{}])[0]
    paste_range = get_legacy_oem_value(paste, "pastelineRange", oem, {}) or {}
    template = config.get("ifcopytemplate") or {}
    return {
        "copytemplate": get_oem_value(template, oem),
        "result_cell": get_oem_value(config.get("result_cell", ""), oem),
        "total_result_cell": get_oem_value(config.get("total_result_cell", ""), oem),
        "failures": get_legacy_oem_value(copy_data, "failures", oem, "N/A"),
        "copyRange": get_legacy_oem_value(copy_data, "copyRange", oem, []),
        "pastefileid": get_legacy_oem_value(paste, "pastefileid", oem, ""),
        "pastelineRange": paste_range,
    }


def get_oem_config(config: dict[str, Any], oem: str) -> dict[str, Any]:
    oem_configs = config.get("oem")
    if isinstance(oem_configs, dict):
        selected = oem_configs.get(oem) or oem_configs.get(DEFAULT_OEM) or {}
        if isinstance(selected, dict):
            return selected
    return build_legacy_oem_config(config, oem)


def get_finish_settings_collection():
    if setting.use_sqlite_persistence():
        from core.sqlite_store import get_platform_store

        return get_platform_store()[setting.UPLOAD_FINISH_SETTINGS_COLLECTION]
    if mongodb.client is None and not mongodb.connect():
        raise RuntimeError("Upload finish settings database connection failed")
    collection = mongodb.get_database(setting.MESSAGE_COLLECTION)[setting.UPLOAD_FINISH_SETTINGS_COLLECTION]
    try:
        collection.create_index([("model", 1), ("test_type", 1)], unique=True)
        collection.create_index("config_key")
    except Exception as exc:
        logger.warning(f"Failed to ensure upload finish settings indexes: {exc}")
    return collection


def format_database_error(exc: Exception) -> str:
    message = str(exc)
    match = MONGO_TIMEOUT_PATTERN.search(message)
    if match:
        return f"{match.group('target')}: timed out，数据库未连接"

    target = "MongoDB"
    if getattr(mongodb, "uri", ""):
        target = "MongoDB URI"
    elif getattr(mongodb, "host", None):
        target = f"{mongodb.host}:{mongodb.port}"
    return f"{target}: 数据库未连接"


def serialize_finish_setting(
    doc: dict[str, Any] | None,
    *,
    model: str,
    test_type: str,
    config_key: str,
    oem: str = DEFAULT_OEM,
    config: dict[str, Any] | None = None,
    environment: str = DEFAULT_CONFIG_ENVIRONMENT,
) -> dict[str, Any]:
    handler_config = UPLOAD_HANDLER_CONFIGS.get(config_key)
    oem = normalize_oem(oem)
    config = config or ConfigRepository.from_environment(environment).get_upload_config(config_key)
    oem_config = get_oem_config(config, oem)
    paste_range = oem_config.get("pastelineRange") or {}
    return {
        "model": model,
        "test_type": test_type,
        "config_key": config_key,
        "oem": oem,
        "oem_options": build_oem_options(config),
        "test_display_name": handler_config.test_display_name if handler_config else test_type,
        "require_finished": DEFAULT_REQUIRE_FINISHED if doc is None else bool(doc.get("require_finished", DEFAULT_REQUIRE_FINISHED)),
        "source": "yaml",
        "updated_at": doc.get("updated_at") if doc else None,
        "copytemplate": oem_config.get("copytemplate", ""),
        "result_cell": oem_config.get("result_cell", ""),
        "total_result_cell": oem_config.get("total_result_cell", ""),
        "failures": oem_config.get("failures", "N/A"),
        "csv_range": config.get("Range", []),
        "summary_source_sheet_name": (config.get("ifcopydata") or [{}])[0].get("summary_source_sheet_name", ""),
        "copy_range": oem_config.get("copyRange", []),
        "pastefileid": oem_config.get("pastefileid", ""),
        "paste_start": paste_range.get("star", ""),
        "paste_end": paste_range.get("end", ""),
        "last_row": config.get("last_row", DEFAULT_LAST_ROW_RANGE),
    }


def build_upload_setting_options() -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    for production in Productions:
        for test_type in TestTypes:
            try:
                config_key = get_upload_config_key(production.value, test_type.value)
                handler_config = get_upload_handler_config(config_key)
            except Exception:
                continue

            options.append(
                {
                    "model": production.value,
                    "test_type": test_type.value,
                    "config_key": config_key,
                    "test_display_name": handler_config.test_display_name,
                }
            )

    return options


def load_finish_setting_docs_if_ready() -> tuple[dict[tuple[str, str], dict[str, Any]], bool, str | None]:
    if setting.use_sqlite_persistence():
        try:
            collection = get_finish_settings_collection()
            return {
                (doc.get("model"), doc.get("test_type")): doc
                for doc in collection.find({}, {"_id": 0})
            }, True, None
        except Exception as exc:
            logger.error(f"Failed to load upload finish settings from sqlite: {exc}")
            return {}, False, format_database_error(exc)

    if mongodb.client is None:
        return {}, False, "数据库未连接，Finished 上传拦截使用默认值"

    try:
        collection = mongodb.get_database(setting.MESSAGE_COLLECTION)[setting.UPLOAD_FINISH_SETTINGS_COLLECTION]
        return {
            (doc.get("model"), doc.get("test_type")): doc
            for doc in collection.find({}, {"_id": 0})
        }, True, None
    except Exception as exc:
        logger.error(f"Failed to load upload finish settings from mongodb: {exc}")
        return {}, False, format_database_error(exc)


def build_serialized_settings(
    options: list[dict[str, Any]],
    docs: dict[tuple[str, str], dict[str, Any]],
    *,
    environment: str,
) -> list[dict[str, Any]]:
    repository = ConfigRepository.from_environment(environment)
    settings: list[dict[str, Any]] = []
    for item in options:
        config = repository.get_upload_config(item["config_key"])
        doc = docs.get((item["model"], item["test_type"]))
        default_setting = serialize_finish_setting(
            doc,
            model=item["model"],
            test_type=item["test_type"],
            config_key=item["config_key"],
            config=config,
            environment=environment,
        )
        settings.append(default_setting)
        for oem in default_setting.get("oem_options", []):
            if oem == default_setting.get("oem"):
                continue
            settings.append(
                serialize_finish_setting(
                    doc,
                    model=item["model"],
                    test_type=item["test_type"],
                    config_key=item["config_key"],
                    oem=oem,
                    config=config,
                    environment=environment,
                )
            )
    return settings


def get_upload_finish_settings(environment: str | None = None, sync_from_production: bool = False) -> dict[str, Any]:
    config_environment = normalize_config_environment(environment)
    if sync_from_production and config_environment == "debug":
        sync_debug_upload_config_from_production()
    options = build_upload_setting_options()
    repository = ConfigRepository.from_environment(config_environment)
    last_row = repository.get_last_row_range()
    try:
        docs, database_available, error = load_finish_setting_docs_if_ready()
        return {
            "options": options,
            "settings": build_serialized_settings(options, docs, environment=config_environment),
            "database_available": database_available,
            "error": error,
            "environment": config_environment,
            "config_file": ConfigRepository.from_environment(config_environment).config_file_name,
            "last_row": last_row,
        }
    except Exception as exc:
        logger.error(f"Failed to load upload finish settings: {exc}")
        return {
            "options": options,
            "settings": build_serialized_settings(options, {}, environment=config_environment),
            "database_available": False,
            "error": format_database_error(exc),
            "environment": config_environment,
            "config_file": ConfigRepository.from_environment(config_environment).config_file_name,
            "last_row": last_row,
        }


def update_upload_finish_setting(payload: dict[str, Any]) -> dict[str, Any]:
    model = normalize_model(payload.get("model"))
    test_type = normalize_test_type(payload.get("test_type"))
    oem = normalize_oem(payload.get("oem"))
    config_environment = normalize_config_environment(payload.get("environment"))
    require_finished = bool(payload.get("require_finished"))
    config_key = get_upload_config_key(model, test_type)
    now = datetime.now()
    repository = ConfigRepository.from_environment(config_environment)
    if payload.get("last_row") is not None:
        last_row = str(payload["last_row"]).strip().upper() or DEFAULT_LAST_ROW_RANGE
        if not re.fullmatch(r"[A-Z]+\s*:\s*[A-Z]+", last_row):
            raise ValueError("last_row 必须是类似 F:I 的列范围")
        repository.update_last_row_range(last_row)
    config = repository.get_upload_config(config_key)
    config_updates: dict[str, Any] = {}
    oem_configs = dict(config.get("oem") or {})
    base_config = get_oem_config(config, DEFAULT_OEM)
    for option in OEM_OPTIONS:
        if option not in oem_configs:
            oem_configs[option] = dict(base_config)
    selected_oem_config = dict(oem_configs.get(oem) or base_config)
    if payload.get("copytemplate") is not None:
        selected_oem_config["copytemplate"] = str(payload["copytemplate"]).strip()
    for payload_key, config_field in (("result_cell", "result_cell"), ("total_result_cell", "total_result_cell")):
        if payload.get(payload_key) is not None:
            selected_oem_config[config_field] = str(payload[payload_key]).strip()
    if payload.get("csv_range"):
        config_updates["Range"] = [str(item).strip() for item in payload["csv_range"] if str(item).strip()]

    copy_data = dict((config.get("ifcopydata") or [{}])[0])
    paste = dict((config.get("ifpaste") or [{}])[0])
    if payload.get("summary_source_sheet_name") is not None:
        copy_data["summary_source_sheet_name"] = str(payload["summary_source_sheet_name"]).strip()
    if payload.get("copy_range") is not None:
        selected_oem_config["copyRange"] = [str(item).strip() for item in payload["copy_range"] if str(item).strip()]
    selected_oem_config["failures"] = str(payload.get("failures") or "N/A").strip() or "N/A"
    if payload.get("pastefileid") is not None:
        selected_oem_config["pastefileid"] = str(payload["pastefileid"]).strip()
    selected_paste_range = dict(selected_oem_config.get("pastelineRange") or {})
    if payload.get("paste_start") is not None:
        selected_paste_range["star"] = str(payload["paste_start"]).strip()
    if payload.get("paste_end") is not None:
        selected_paste_range["end"] = str(payload["paste_end"]).strip()
    selected_oem_config["pastelineRange"] = selected_paste_range
    oem_configs[oem] = selected_oem_config
    config_updates["oem"] = {option: oem_configs[option] for option in OEM_OPTIONS}

    opentrons_config = config_updates["oem"][DEFAULT_OEM]
    ultima_config = config_updates["oem"]["Ultima"]
    template = dict(config.get("ifcopytemplate") or {})
    template["default"] = opentrons_config.get("copytemplate", "")
    template["ultima"] = ultima_config.get("copytemplate", template["default"])
    config_updates["ifcopytemplate"] = template
    config_updates["result_cell"] = {
        "default": opentrons_config.get("result_cell", ""),
        "ultima": ultima_config.get("result_cell", opentrons_config.get("result_cell", "")),
    }
    config_updates["total_result_cell"] = {
        "default": opentrons_config.get("total_result_cell", ""),
        "ultima": ultima_config.get("total_result_cell", opentrons_config.get("total_result_cell", "")),
    }
    copy_data["copyRange"] = opentrons_config.get("copyRange", [])
    copy_data["UltimacopyRange"] = ultima_config.get("copyRange", copy_data.get("copyRange", []))
    copy_data["failures"] = opentrons_config.get("failures", "N/A")
    copy_data["Ultimafailures"] = ultima_config.get("failures", copy_data.get("failures", "N/A"))
    paste["pastefileid"] = opentrons_config.get("pastefileid", "")
    paste["Ultimapastefileid"] = ultima_config.get("pastefileid", paste.get("pastefileid", ""))
    paste["pastelineRange"] = opentrons_config.get("pastelineRange", {})
    paste["UltimapastelineRange"] = ultima_config.get("pastelineRange", paste.get("pastelineRange", {}))
    config_updates["ifcopydata"] = [copy_data]
    config_updates["ifpaste"] = [paste]
    repository.update_upload_config(config_key, config_updates)
    doc = {
        "model": model,
        "test_type": test_type,
        "config_key": config_key,
        "require_finished": require_finished,
        "updated_at": now,
    }
    collection = get_finish_settings_collection()
    collection.update_one(
        {"model": model, "test_type": test_type},
        {"$set": doc, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return serialize_finish_setting(
        doc,
        model=model,
        test_type=test_type,
        config_key=config_key,
        oem=oem,
        environment=config_environment,
    )


def should_require_finished(model: str | None, test_type: str | TestTypes | None) -> bool:
    try:
        normalized_model = normalize_model(model)
        normalized_test = normalize_test_type(test_type.value if isinstance(test_type, TestTypes) else test_type)
    except Exception as exc:
        logger.warning(f"Failed to normalize upload finish setting key, fallback to require finished: {exc}")
        return DEFAULT_REQUIRE_FINISHED

    try:
        collection = get_finish_settings_collection()
        doc = collection.find_one(
            {"model": normalized_model, "test_type": normalized_test},
            {"_id": 0, "require_finished": 1},
        )
        if doc is None:
            return DEFAULT_REQUIRE_FINISHED
        return bool(doc.get("require_finished", DEFAULT_REQUIRE_FINISHED))
    except Exception as exc:
        logger.error(f"Failed to read upload finish setting, fallback to require finished: {exc}")
        return DEFAULT_REQUIRE_FINISHED
