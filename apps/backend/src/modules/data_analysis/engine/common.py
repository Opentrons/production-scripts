from __future__ import annotations

import re
from pathlib import Path
from typing import Any


SECTION_START_PATTERN = re.compile(r"^(.+)_START$")
SECTION_END_PATTERN = re.compile(r"^(.+)_END$")


def parse_sections(rows: list[list[str]]) -> dict[str, list[dict[str, Any]]]:
    sections: dict[str, list[dict[str, Any]]] = {}
    current_section: str | None = None

    for row in rows:
        key = get_cell(row, 1)
        if not key:
            continue

        start_match = SECTION_START_PATTERN.match(key)
        if start_match:
            current_section = start_match.group(1)
            sections.setdefault(current_section, [])
            continue

        end_match = SECTION_END_PATTERN.match(key)
        if end_match and current_section == end_match.group(1):
            current_section = None
            continue

        if current_section:
            sections[current_section].append(
                {
                    "time_s": clean_number(get_cell(row, 0)),
                    "key": key,
                    "value": normalize_value(get_cell(row, 2)),
                }
            )

    return sections


def section_key_values(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {str(row["key"]): row.get("value") for row in rows if row.get("key")}


def build_file_info(file_path: str) -> dict[str, Any]:
    path = Path(file_path)
    info = {
        "name": path.name,
        "path": str(path),
    }
    try:
        info["size"] = path.stat().st_size
    except OSError:
        pass
    return info


def get_cell(row: list[str], index: int) -> str:
    if index >= len(row):
        return ""
    return str(row[index]).strip()


def normalize_value(value: str) -> Any:
    if value in ("", "None", "N/A"):
        return None
    return to_number(value)


def to_number(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip()
    if text == "":
        return None
    try:
        number = float(text)
    except ValueError:
        return value
    if number.is_integer():
        return int(number)
    return number


def clean_number(value: Any) -> float | int | None:
    value = to_number(value)
    if isinstance(value, (int, float)):
        return round_float(value)
    return None


def round_float(value: float | int | None, digits: int = 4) -> float | int | None:
    if value is None:
        return None
    rounded = round(float(value), digits)
    if rounded.is_integer():
        return int(rounded)
    return rounded


def first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def normalize_status(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    if text in {"PASS", "PASSED"}:
        return "PASS"
    if text in {"FAIL", "FAILED"}:
        return "FAIL"
    return None


def collect_status_checks(rows: list[list[str]]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for row in rows:
        key = get_cell(row, 1)
        if not key or is_section_marker(key):
            continue

        status = None
        status_index = None
        for index, cell in enumerate(row[2:], start=2):
            parsed_status = normalize_status(cell)
            if parsed_status is not None:
                status = parsed_status
                status_index = index
                break

        if status is None or status_index is None:
            continue

        checks.append(
            {
                "time_s": clean_number(get_cell(row, 0)),
                "key": key,
                "status": status,
                "values": [cell for cell in row[2:status_index] if str(cell).strip()],
                "group": infer_check_group(key),
            }
        )
    return checks


def summarize_checks(checks: list[dict[str, Any]]) -> dict[str, Any]:
    passed_checks = sum(1 for check in checks if check.get("status") == "PASS")
    failed_checks = sum(1 for check in checks if check.get("status") == "FAIL")
    failures = [str(check.get("key") or "") for check in checks if check.get("status") == "FAIL"]
    groups: dict[str, dict[str, int]] = {}

    for check in checks:
        group = str(check.get("group") or "other")
        group_item = groups.setdefault(group, {"pass": 0, "fail": 0, "total": 0})
        group_item["total"] += 1
        if check.get("status") == "PASS":
            group_item["pass"] += 1
        elif check.get("status") == "FAIL":
            group_item["fail"] += 1

    return {
        "passed_checks": passed_checks,
        "failed_checks": failed_checks,
        "failures": failures,
        "groups": [
            {"group": group, **counts}
            for group, counts in sorted(groups.items())
        ],
    }


def infer_check_group(key: str) -> str:
    text = str(key or "").strip().lower()
    for separator in ("-", "_"):
        if separator in text:
            return text.split(separator, 1)[0] or "other"
    return text or "other"


def is_section_marker(key: str) -> bool:
    text = str(key or "").strip()
    if not text:
        return True
    if set(text) <= {"-", "_"}:
        return True
    upper = text.upper()
    return upper.endswith("_START") or upper.endswith("_END")
