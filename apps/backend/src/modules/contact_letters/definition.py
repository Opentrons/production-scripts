from __future__ import annotations

import re
from pathlib import Path
from typing import Final, Literal


CONTACT_KIND: Final[Literal["contact"]] = "contact"
CONTACT_FOLDER_ID: Final = "1rC0Q2FtayNKkO3gY4_39CuaQdYA_wVtF"
CONTACT_SOURCE_URL: Final = f"https://drive.google.com/drive/folders/{CONTACT_FOLDER_ID}"
CONTACT_NUMBER_PREFIX: Final = "ENG-"
CONTACT_NUMBER_PATTERN: Final = re.compile(
    r"(?<![A-Za-z0-9])ENG[\s\-_－—]*\d{3,}(?:[\-_－—]\d+)*",
    re.IGNORECASE,
)
CONTACT_NUMBER_LABELS: Final = ("联络编号", "联络函编号")
CONTACT_SUBJECT_LABELS: Final = ("主题", "标题", "变更主题", "联络函主题", "Subject")


def normalize_contact_number(raw_value: str, *, allow_bare: bool = False) -> str:
    """Normalize an engineering contact-letter identifier."""

    match = CONTACT_NUMBER_PATTERN.search(raw_value)
    if match:
        value = re.sub(r"[\s_－—-]+", "-", match.group(0).upper())
        return value.strip("-")
    if not allow_bare:
        return ""
    digits = re.search(r"(?<!\d)\d{3,}(?:[-_－—]\d+)*(?!\d)", raw_value)
    if not digits:
        return ""
    value = re.sub(r"[_－—]+", "-", digits.group(0))
    return f"{CONTACT_NUMBER_PREFIX}{value}"


def resolve_contact_subject(
    file_name: str,
    *,
    sheet_subject: str = "",
    description: str = "",
) -> str:
    """Resolve a contact-letter subject using sheet data and Drive metadata."""

    for candidate in (sheet_subject, description):
        cleaned = re.sub(r"\s+", " ", candidate or "").strip()
        if cleaned:
            return cleaned

    subject = Path(file_name).stem
    subject = CONTACT_NUMBER_PATTERN.sub("", subject, count=1)
    subject = re.sub(r"^[\s\-_:：－—]+", "", subject).strip()
    return subject or file_name
