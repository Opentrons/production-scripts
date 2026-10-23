"""ECN feature module."""

from modules.ecn.definition import (
    ECN_FOLDER_ID,
    ECN_KIND,
    ECN_NUMBER_LABELS,
    ECN_NUMBER_PATTERN,
    ECN_NUMBER_PREFIX,
    ECN_PRODUCT_MODEL_LABELS,
    ECN_SOURCE_URL,
    normalize_ecn_number,
    resolve_ecn_subject,
)

__all__ = [
    "ECN_FOLDER_ID",
    "ECN_KIND",
    "ECN_NUMBER_LABELS",
    "ECN_NUMBER_PATTERN",
    "ECN_NUMBER_PREFIX",
    "ECN_PRODUCT_MODEL_LABELS",
    "ECN_SOURCE_URL",
    "normalize_ecn_number",
    "resolve_ecn_subject",
]
