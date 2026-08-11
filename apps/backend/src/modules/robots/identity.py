from __future__ import annotations

import re
from typing import Any, Mapping


_PLACEHOLDER_SERIALS = {"", "unknown", "n/a", "na", "none", "null", "undefined"}
_ROBOT_NAME_SERIAL_PATTERNS = (
    re.compile(r"^FLX[A-Z0-9]\d{13}$", re.IGNORECASE),
    re.compile(r"^OT2[A-Z0-9]+$", re.IGNORECASE),
)
_SERIAL_KEYS = ("robot_serial", "serialNumber", "serial_number")
_NAME_KEYS = ("name", "robot_name")


def _valid_serial(value: Any) -> str | None:
    if not isinstance(value, (str, int)):
        return None
    normalized = str(value).replace("\x00", "").strip()
    if normalized.casefold() in _PLACEHOLDER_SERIALS:
        return None
    return normalized


def resolve_robot_serial(*payloads: Mapping[str, Any] | None) -> str | None:
    """Resolve a robot serial from Robot Server and Update Server responses."""
    for payload in payloads:
        if not payload:
            continue
        for key in _SERIAL_KEYS:
            serial = _valid_serial(payload.get(key))
            if serial:
                return serial

    # Some production robots are named after their barcode. Only accept names
    # that match a known robot serial format to avoid treating aliases as IDs.
    for payload in payloads:
        if not payload:
            continue
        for key in _NAME_KEYS:
            name = _valid_serial(payload.get(key))
            if name and any(pattern.fullmatch(name) for pattern in _ROBOT_NAME_SERIAL_PATTERNS):
                return name
    return None
