from __future__ import annotations

import copy
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import settings as setting
from database.mongodb import mongodb


SPEC_COLLECTION_NAME = "data_analysis_specs"
SPEC_DOCUMENT_KIND = "gravimetric"
SPEC_TEST_TYPE = "gravimetric"
SPEC_TEST_NAME = "Gravimetric"

DEFAULT_GRAVIMETRIC_SPEC: dict[str, dict[float, dict[str, float]]] = {
    "P50M": {
        1.0: {"cv": 6.4, "d": 8.0},
        10.0: {"cv": 0.8, "d": 2.0},
        50.0: {"cv": 0.48, "d": 1.0},
    },
    "P50S": {
        1.0: {"cv": 5.6, "d": 6.4},
        10.0: {"cv": 0.4, "d": 1.2},
        50.0: {"cv": 0.32, "d": 1.0},
    },
    "P1000M": {
        5.0: {"cv": 3.2, "d": 6.4},
        50.0: {"cv": 0.48, "d": 2.0},
        200.0: {"cv": 0.2, "d": 0.8},
        1000.0: {"cv": 0.12, "d": 0.56},
    },
    "P1000S": {
        5.0: {"cv": 2.0, "d": 4.0},
        50.0: {"cv": 0.24, "d": 0.4},
        200.0: {"cv": 0.12, "d": 0.4},
        1000.0: {"cv": 0.12, "d": 0.4},
    },
    "P1000-96": {
        5.0: {"cv": 100.0, "d": 8.0},
        50.0: {"cv": 100.0, "d": 2.0},
        200.0: {"cv": 100.0, "d": 1.2},
        1000.0: {"cv": 100.0, "d": 1.2},
    },
    "P200-96": {
        1.0: {"cv": 100.0, "d": 8.0},
        50.0: {"cv": 100.0, "d": 1.2},
        200.0: {"cv": 100.0, "d": 0.8},
    },
}

GRAVIMETRIC_PRODUCT_CATALOG: list[dict[str, str]] = [
    {"product": "P50S", "product_name": "P50S", "analysis_product": "P50S"},
    {"product": "P1000S", "product_name": "P1000S", "analysis_product": "P1000S"},
    {"product": "P50M", "product_name": "P50M", "analysis_product": "P50M"},
    {"product": "P1000M", "product_name": "P1000M", "analysis_product": "P1000M"},
    {"product": "P2HH", "product_name": "P2HH", "analysis_product": "P200-96"},
    {"product": "P1KH", "product_name": "P1KH", "analysis_product": "P1000-96"},
]


def list_gravimetric_specs() -> dict[str, Any]:
    saved_specs, storage, error = load_saved_specs()
    saved_by_product = {item["product"]: item for item in saved_specs}
    saved_by_analysis_product = {
        item["analysis_product"]: item
        for item in saved_specs
        if item.get("analysis_product")
    }

    specs = []
    for catalog_item in GRAVIMETRIC_PRODUCT_CATALOG:
        item = build_default_spec_item(catalog_item)
        saved_item = saved_by_product.get(item["product"]) or saved_by_analysis_product.get(item["analysis_product"])
        if saved_item:
            item = merge_spec_items(item, saved_item)
            item["source"] = storage
        specs.append(item)

    return {
        "products": [
            {
                **item,
                "test_type": SPEC_TEST_TYPE,
                "test_name": SPEC_TEST_NAME,
            }
            for item in GRAVIMETRIC_PRODUCT_CATALOG
        ],
        "specs": specs,
        "storage": storage,
        "error": error,
    }


def save_gravimetric_spec(payload: dict[str, Any]) -> dict[str, Any]:
    item = normalize_spec_item(payload)
    storage = "json"
    error = None

    if save_spec_to_mongo(item):
        storage = "mongo"
    else:
        try:
            save_spec_to_json(item)
        except Exception as exc:
            error = str(exc)
            raise

    return {
        **item,
        "source": storage,
        "storage": storage,
        "error": error,
    }


def get_gravimetric_spec(product: str) -> dict[float, dict[str, float]]:
    analysis_product = normalize_analysis_product(product)
    spec = copy.deepcopy(DEFAULT_GRAVIMETRIC_SPEC.get(analysis_product, {}))
    saved_specs, _, _ = load_saved_specs()

    for item in saved_specs:
        if normalize_analysis_product(item.get("analysis_product") or item.get("product")) != analysis_product:
            continue
        for row in item.get("volumes", []):
            volume = to_float(row.get("volume"))
            cv = to_float(row.get("cv"))
            d_value = to_float(row.get("d"))
            if volume is None or cv is None or d_value is None:
                continue
            spec[volume] = {"cv": cv, "d": d_value}

    return spec


def load_saved_specs() -> tuple[list[dict[str, Any]], str, str | None]:
    mongo_specs = load_specs_from_mongo()
    if mongo_specs is not None:
        return mongo_specs, "mongo", None

    try:
        json_specs = load_specs_from_json()
    except Exception as exc:
        return [], "default", str(exc)

    if json_specs is not None:
        return json_specs, "json", None
    return [], "default", None


def load_specs_from_mongo() -> list[dict[str, Any]] | None:
    if mongodb.client is None:
        return None
    try:
        database = mongodb.get_database(setting.DATA_DB_NAME)
        collection = database[SPEC_COLLECTION_NAME]
        docs = collection.find({"kind": SPEC_DOCUMENT_KIND})
        return [clean_mongo_doc(doc) for doc in docs]
    except Exception:
        return None


def save_spec_to_mongo(item: dict[str, Any]) -> bool:
    if mongodb.client is None:
        return False
    try:
        database = mongodb.get_database(setting.DATA_DB_NAME)
        collection = database[SPEC_COLLECTION_NAME]
        fields = {key: value for key, value in item.items() if key != "_id"}
        collection.update_one(
            {"_id": item["_id"]},
            {"$set": fields},
            upsert=True,
        )
        return True
    except Exception:
        return False


def load_specs_from_json() -> list[dict[str, Any]] | None:
    path = get_spec_json_path()
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    specs = data.get("specs") if isinstance(data, dict) else data
    if not isinstance(specs, list):
        return []
    return [normalize_spec_item(item, strict=False) for item in specs]


def save_spec_to_json(item: dict[str, Any]) -> None:
    path = get_spec_json_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    current_specs = load_specs_from_json() or []
    next_specs = [
        spec
        for spec in current_specs
        if not (spec["product"] == item["product"] and spec["test_type"] == item["test_type"])
    ]
    next_specs.append(item)
    next_specs.sort(key=lambda spec: (spec["product"], spec["test_type"]))
    with path.open("w", encoding="utf-8") as file:
        json.dump(
            {
                "updated_at": now_iso(),
                "specs": next_specs,
            },
            file,
            ensure_ascii=False,
            indent=2,
        )


def get_spec_json_path() -> Path:
    configured = os.getenv("DATA_ANALYSIS_SPEC_JSON_PATH")
    if configured:
        return Path(configured)
    return Path(setting.CONFIG_DIR) / "data_analysis_specs.json"


def build_default_spec_item(catalog_item: dict[str, str]) -> dict[str, Any]:
    analysis_product = catalog_item["analysis_product"]
    volumes = [
        {"volume": volume, "cv": values["cv"], "d": values["d"]}
        for volume, values in sorted(DEFAULT_GRAVIMETRIC_SPEC.get(analysis_product, {}).items())
    ]
    return normalize_spec_item(
        {
            **catalog_item,
            "test_type": SPEC_TEST_TYPE,
            "test_name": SPEC_TEST_NAME,
            "volumes": volumes,
            "source": "default",
        },
        strict=False,
    )


def merge_spec_items(default_item: dict[str, Any], saved_item: dict[str, Any]) -> dict[str, Any]:
    volume_rows = {row["volume"]: dict(row) for row in default_item.get("volumes", [])}
    for row in saved_item.get("volumes", []):
        volume = to_float(row.get("volume"))
        cv = to_float(row.get("cv"))
        d_value = to_float(row.get("d"))
        if volume is None or cv is None or d_value is None:
            continue
        volume_rows[volume] = {"volume": volume, "cv": cv, "d": d_value}

    return {
        **default_item,
        **{key: value for key, value in saved_item.items() if key not in ("_id", "volumes")},
        "volumes": [volume_rows[volume] for volume in sorted(volume_rows)],
    }


def normalize_spec_item(item: dict[str, Any], *, strict: bool = True) -> dict[str, Any]:
    product = str(item.get("product") or "").strip()
    catalog_item = find_catalog_item(product)
    if catalog_item is None and strict:
        raise ValueError(f"Unsupported product: {product}")

    analysis_product = str(
        item.get("analysis_product")
        or (catalog_item or {}).get("analysis_product")
        or normalize_analysis_product(product)
    )
    test_type = str(item.get("test_type") or SPEC_TEST_TYPE).strip()
    if test_type != SPEC_TEST_TYPE and strict:
        raise ValueError(f"Unsupported test type: {test_type}")

    product_name = str(item.get("product_name") or (catalog_item or {}).get("product_name") or product)
    volumes = normalize_volume_rows(item.get("volumes") or [])

    if strict and not volumes:
        raise ValueError("Spec volumes cannot be empty")

    return {
        "_id": f"{SPEC_DOCUMENT_KIND}:{product}",
        "kind": SPEC_DOCUMENT_KIND,
        "product": product,
        "product_name": product_name,
        "analysis_product": analysis_product,
        "test_type": test_type,
        "test_name": str(item.get("test_name") or SPEC_TEST_NAME),
        "volumes": volumes,
        "updated_at": str(item.get("updated_at") or now_iso()),
    }


def normalize_volume_rows(rows: list[dict[str, Any]]) -> list[dict[str, float]]:
    volume_rows: dict[float, dict[str, float]] = {}
    for row in rows:
        volume = to_float(row.get("volume"))
        cv = to_float(row.get("cv"))
        d_value = to_float(row.get("d"))
        if volume is None or cv is None or d_value is None:
            continue
        volume_rows[volume] = {
            "volume": volume,
            "cv": cv,
            "d": d_value,
        }
    return [volume_rows[volume] for volume in sorted(volume_rows)]


def find_catalog_item(product: str) -> dict[str, str] | None:
    for item in GRAVIMETRIC_PRODUCT_CATALOG:
        if item["product"] == product or item["analysis_product"] == product:
            return item
    return None


def normalize_analysis_product(product: Any) -> str:
    text = str(product or "").strip()
    catalog_item = find_catalog_item(text)
    if catalog_item:
        return catalog_item["analysis_product"]
    return text


def clean_mongo_doc(doc: dict[str, Any]) -> dict[str, Any]:
    clean_doc = dict(doc)
    clean_doc.pop("_id", None)
    return normalize_spec_item(clean_doc, strict=False)


def to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
