from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import settings as setting
from database.mongodb import mongodb
from upload_handler.models import Productions, TestTypes
from upload_handler.product_catalog import (
    UPLOAD_HANDLER_CONFIGS,
    get_upload_config_key,
    get_upload_handler_config,
)

from api.services.logging import logger


DEFAULT_REQUIRE_FINISHED = True
MONGO_TIMEOUT_PATTERN = re.compile(r"(?P<target>[\w.-]+:\d+): timed out", re.IGNORECASE)


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


def get_finish_settings_collection():
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


def serialize_finish_setting(doc: dict[str, Any] | None, *, model: str, test_type: str, config_key: str) -> dict[str, Any]:
    handler_config = UPLOAD_HANDLER_CONFIGS.get(config_key)
    return {
        "model": model,
        "test_type": test_type,
        "config_key": config_key,
        "test_display_name": handler_config.test_display_name if handler_config else test_type,
        "require_finished": DEFAULT_REQUIRE_FINISHED if doc is None else bool(doc.get("require_finished", DEFAULT_REQUIRE_FINISHED)),
        "source": "default" if doc is None else "database",
        "updated_at": doc.get("updated_at") if doc else None,
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


def get_upload_finish_settings() -> dict[str, Any]:
    options = build_upload_setting_options()
    try:
        collection = get_finish_settings_collection()
        docs = {
            (doc.get("model"), doc.get("test_type")): doc
            for doc in collection.find({}, {"_id": 0})
        }
        settings = [
            serialize_finish_setting(
                docs.get((item["model"], item["test_type"])),
                model=item["model"],
                test_type=item["test_type"],
                config_key=item["config_key"],
            )
            for item in options
        ]
        return {
            "options": options,
            "settings": settings,
            "database_available": True,
        }
    except Exception as exc:
        logger.error(f"Failed to load upload finish settings: {exc}")
        return {
            "options": options,
            "settings": [
                serialize_finish_setting(
                    None,
                    model=item["model"],
                    test_type=item["test_type"],
                    config_key=item["config_key"],
                )
                for item in options
            ],
            "database_available": False,
            "error": format_database_error(exc),
        }


def update_upload_finish_setting(payload: dict[str, Any]) -> dict[str, Any]:
    model = normalize_model(payload.get("model"))
    test_type = normalize_test_type(payload.get("test_type"))
    require_finished = bool(payload.get("require_finished"))
    config_key = get_upload_config_key(model, test_type)
    now = datetime.now()
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
    return serialize_finish_setting(doc, model=model, test_type=test_type, config_key=config_key)


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
