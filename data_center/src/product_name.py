from __future__ import annotations

from typing import Any


def normalize_product_name(value: Any) -> str:
    """Return the canonical product name used by upload and analysis paths."""
    if value is None:
        return ""
    normalized = str(value).strip().replace("-", "")
    return " ".join(normalized.split())


def normalize_product_fields(data: Any) -> Any:
    if isinstance(data, dict):
        normalized = {}
        for key, value in data.items():
            if key in {"product", "product_name", "Production"}:
                normalized[key] = normalize_product_name(value)
            else:
                normalized[key] = normalize_product_fields(value)
        return normalized
    if isinstance(data, list):
        return [normalize_product_fields(item) for item in data]
    return data
