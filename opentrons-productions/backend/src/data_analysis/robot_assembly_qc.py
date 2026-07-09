from __future__ import annotations

from typing import Any

from .common import build_file_info, collect_status_checks, first_text, get_cell, summarize_checks


def analyze(file_path: str, rows: list[list[str]], metadata: dict[str, Any]) -> dict[str, Any]:
    checks = collect_status_checks(rows)
    summary = summarize_checks(checks)
    failed_checks = int(summary["failed_checks"])

    return {
        "file": build_file_info(file_path),
        "channel": "robot_assembly_qc",
        "channel_label": "Robot Assembly QC",
        "status": "success",
        "result": "Pass" if failed_checks == 0 and checks else "Fail",
        "passed": failed_checks == 0 and bool(checks),
        "product": "Flex",
        "sn": resolve_serial_number(metadata, rows),
        "test_name": first_text(metadata.get("test_name"), find_row_value(rows, "test_name")),
        "test_time_utc": metadata.get("test_time_utc"),
        "metadata": metadata,
        "checks": checks,
        "summary": {
            "check_count": len(checks),
            **summary,
        },
    }


def resolve_serial_number(metadata: dict[str, Any], rows: list[list[str]]) -> str:
    return first_text(
        metadata.get("test_device_id"),
        metadata.get("test_robot_id"),
        metadata.get("test_tag"),
        find_row_value(rows, "test_device_id"),
        find_row_value(rows, "test_robot_id"),
    )


def find_row_value(rows: list[list[str]], key: str) -> Any:
    normalized_key = normalize_key(key)
    for row in rows:
        if normalize_key(get_cell(row, 1)) == normalized_key:
            return get_cell(row, 2)
    return None


def normalize_key(value: Any) -> str:
    return "".join(char for char in str(value or "").lower() if char.isalnum())
