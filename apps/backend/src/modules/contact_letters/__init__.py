"""Engineering contact-letter feature module."""

from modules.contact_letters.definition import (
    CONTACT_FOLDER_ID,
    CONTACT_KIND,
    CONTACT_NUMBER_LABELS,
    CONTACT_NUMBER_PATTERN,
    CONTACT_NUMBER_PREFIX,
    CONTACT_SOURCE_URL,
    CONTACT_SUBJECT_LABELS,
    normalize_contact_number,
    resolve_contact_subject,
)

__all__ = [
    "CONTACT_FOLDER_ID",
    "CONTACT_KIND",
    "CONTACT_NUMBER_LABELS",
    "CONTACT_NUMBER_PATTERN",
    "CONTACT_NUMBER_PREFIX",
    "CONTACT_SOURCE_URL",
    "CONTACT_SUBJECT_LABELS",
    "normalize_contact_number",
    "resolve_contact_subject",
]
