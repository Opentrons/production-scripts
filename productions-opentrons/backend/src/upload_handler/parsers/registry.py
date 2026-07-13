from typing import Any, Dict, Optional

from settings import get_logger
from upload_handler.product_catalog import (
    SERIAL_NUMBER_METADATA_KEYS,
    get_parser_definition,
    get_upload_config_key_from_metadata,
    get_upload_uploader_key,
)

from .csv_common import extract_meta_data_from_csv, parse_csv_by_definition

logger = get_logger(__name__)

META_FIELD_ALIASES = {
    "test_device": "test_device_id",
    "test-device": "test_device_id",
    "test-device-id": "test_device_id",
    "device_id": "test_device_id",
}


def normalize_meta_override(meta: dict[str, Any] | None = None) -> dict[str, Any]:
    if not meta:
        return {}
    normalized = {}
    for key, value in meta.items():
        if key is None or value in (None, ""):
            continue
        normalized_key = META_FIELD_ALIASES.get(str(key), str(key))
        normalized[normalized_key] = value
    return normalized


def apply_meta_override(meta_data: dict[str, Any], meta_override: dict[str, Any]) -> None:
    if not meta_override:
        return

    serial_number_override = next(
        (
            meta_override[key]
            for key in SERIAL_NUMBER_METADATA_KEYS
            if key in meta_override
        ),
        None,
    )
    if serial_number_override is not None:
        for key in SERIAL_NUMBER_METADATA_KEYS:
            meta_data[key] = serial_number_override

    meta_data.update(meta_override)


def extract_csv(file_path: str, meta: dict[str, Any] | None = None) -> Optional[Dict[str, Any]]:
    meta_data = extract_meta_data_from_csv(file_path)
    if meta_data.get("failed"):
        return {
            "metadata": {},
            "failed": True,
            "error": meta_data["error"],
        }
    meta_override = normalize_meta_override(meta)
    apply_meta_override(meta_data, meta_override)

    try:
        upload_config_key = get_upload_config_key_from_metadata(meta_data)
    except ValueError as exc:
        logger.warning("Cannot resolve parser config for %s: %s", file_path, exc)
        return None

    definition = get_parser_definition(upload_config_key)
    if definition is None:
        logger.warning("Parser definition not found: %s", upload_config_key)
        return None

    result = parse_csv_by_definition(file_path, definition, meta=meta_override, metadata=meta_data)
    result["upload_uploader_key"] = get_upload_uploader_key(result.get("model"))
    return result
