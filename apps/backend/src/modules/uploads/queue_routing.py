"""Product groups for independent upload capacity; no Google calls are needed."""

from __future__ import annotations

from modules.uploads.handler.models import Productions
from modules.uploads.handler.parsers.csv_common import extract_meta_data_from_csv
from modules.uploads.handler.parsers.registry import apply_meta_override, normalize_meta_override
from modules.uploads.handler.product_catalog import (
    PIPETTE_1CH_MODELS,
    PIPETTE_8CH_MODELS,
    PIPETTE_96CH_MODELS,
    get_model_from_serial_number,
    get_serial_number_from_metadata,
)


UPLOAD_PRODUCT_GROUPS = ("pipette", "robot", "other")


def resolve_upload_product_group(
    csv_path: str, meta: dict | None = None, file_desc: dict | None = None,
) -> str:
    model = Productions.from_string((file_desc or {}).get("model"))
    if model is None:
        metadata = extract_meta_data_from_csv(csv_path)
        apply_meta_override(metadata, normalize_meta_override(meta))
        model = Productions.from_string(
            get_model_from_serial_number(get_serial_number_from_metadata(metadata))
        )
    if model == Productions.ROBOT:
        return "robot"
    if model in PIPETTE_1CH_MODELS | PIPETTE_8CH_MODELS | PIPETTE_96CH_MODELS:
        return "pipette"
    return "other"
