from __future__ import annotations

import re
from pathlib import Path
from typing import Final, Literal


ECN_KIND: Final[Literal["ecn"]] = "ecn"
ECN_FOLDER_ID: Final = "1cAlMjAWMnk47cvvxSPEtG4_xn6O3xmMB"
ECN_SOURCE_URL: Final = f"https://drive.google.com/drive/folders/{ECN_FOLDER_ID}"
ECN_NUMBER_PREFIX: Final = "ECN-"
ECN_NUMBER_PATTERN: Final = re.compile(
    r"(?<![A-Za-z0-9])(?:QR[\s\-_－—]*ENG[\s\-_－—]*\d{3,}(?:[\-_－—]\d+)*|ECN[\s\-_－—]*\d{3,}(?:[\-_－—]\d+)*)",
    re.IGNORECASE,
)
ECN_NUMBER_LABELS: Final = ("ECN编号", "ECN单号", "工程变更编号", "ECN No.")
ECN_PRODUCT_MODEL_LABELS: Final = (
    "产品型号",
    "产品机型",
    "Product number",
    "Product model",
)


def normalize_ecn_number(raw_value: str, *, allow_bare: bool = False) -> str:
    """Normalize an ECN identifier read from a filename or sheet cell."""

    match = ECN_NUMBER_PATTERN.search(raw_value)
    if match:
        value = re.sub(r"[\s_－—-]+", "-", match.group(0).upper())
        if value.startswith("QR-ENG-"):
            return value
        suffix = re.sub(r"^ECN-?", "", value).strip("-")
        return f"{ECN_NUMBER_PREFIX}{suffix}"
    if not allow_bare:
        return ""
    digits = re.search(r"(?<!\d)\d{3,}(?:[-_－—]\d+)*(?!\d)", raw_value)
    if not digits:
        return ""
    value = re.sub(r"[_－—]+", "-", digits.group(0))
    return f"{ECN_NUMBER_PREFIX}{value}"


def resolve_ecn_subject(file_name: str, document_title: str = "") -> str:
    """Use the Google Sheet document title as the ECN subject when available."""

    title = re.sub(r"\s+", " ", document_title or "").strip()
    return title or Path(file_name).stem.strip() or file_name
