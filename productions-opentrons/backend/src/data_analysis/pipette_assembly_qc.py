from __future__ import annotations

from typing import Any

from .common import (
    build_file_info,
    clean_number,
    collect_status_checks,
    first_text,
    get_cell,
    normalize_status,
    parse_sections,
    section_key_values,
    summarize_checks,
)


IGNORED_STRUCTURED_SECTIONS = {"META_DATA", "RESULTS_OVERVIEW"}
SECTION_LABELS = {
    "PLUNGER": "Plunger",
    "JAWS": "Jaws",
    "CAPACITANCE": "Capacitance",
    "PRESSURE": "Pressure",
    "ENVIRONMENT-SENSOR": "Environment Sensor",
    "TIP-SENSOR": "Tip Sensor",
    "DROPLETS": "Droplets",
    "ENCODER": "Encoder",
}


def analyze(file_path: str, rows: list[list[str]], metadata: dict[str, Any]) -> dict[str, Any]:
    sections = parse_sections(rows)
    metadata_table = build_metadata_table(rows, metadata)
    result_overview = parse_result_overview(sections.get("RESULTS_OVERVIEW", []))
    test_sections = parse_test_sections(rows)
    checks = build_checks_from_sections(test_sections) or collect_status_checks(rows)
    summary = summarize_checks(checks)
    failed_checks = int(summary["failed_checks"])
    section_results = build_section_results(result_overview, test_sections)
    test_matrices = build_test_matrices(test_sections)

    return {
        "file": build_file_info(file_path),
        "channel": "pipette_assembly_qc",
        "channel_label": "Pipette Assembly QC",
        "status": "success",
        "result": "Pass" if failed_checks == 0 and checks else "Fail",
        "passed": failed_checks == 0 and bool(checks),
        "product": resolve_product(metadata, rows),
        "sn": resolve_serial_number(metadata, rows),
        "test_name": first_text(metadata.get("test_name"), metadata.get("test-name"), find_row_value(rows, "test-name")),
        "test_time_utc": metadata.get("test_time_utc") or find_row_value(rows, "date"),
        "metadata": metadata,
        "metadata_table": metadata_table,
        "section_results": section_results,
        "test_sections": test_sections,
        "test_matrices": test_matrices,
        "checks": checks,
        "summary": {
            "check_count": len(checks),
            "section_count": len(test_sections),
            "matrix_count": len(test_matrices),
            **summary,
        },
    }


def resolve_serial_number(metadata: dict[str, Any], rows: list[list[str]]) -> str:
    return first_text(
        metadata.get("test_device_id"),
        metadata.get("test_tag"),
        metadata.get("pipette"),
        find_row_value(rows, "pipette"),
        find_row_value(rows, "pipette-barcode"),
    )


def resolve_product(metadata: dict[str, Any], rows: list[list[str]]) -> str:
    serial_number = resolve_serial_number(metadata, rows)
    if serial_number.startswith("P50S"):
        return "P50S"
    if serial_number.startswith("P1KS"):
        return "P1000S"
    if serial_number.startswith("P50M"):
        return "P50M"
    if serial_number.startswith("P1KM"):
        return "P1000M"
    if serial_number.startswith("P2HH"):
        return "P200-96"
    if serial_number.startswith("P1KH"):
        return "P1000-96"
    return "Unknown"


def find_row_value(rows: list[list[str]], key: str) -> Any:
    normalized_key = normalize_key(key)
    for row in rows:
        if normalize_key(get_cell(row, 1)) == normalized_key:
            return get_cell(row, 2)
    return None


def normalize_key(value: Any) -> str:
    return "".join(char for char in str(value or "").lower() if char.isalnum())


def build_metadata_table(rows: list[list[str]], metadata: dict[str, Any]) -> list[dict[str, Any]]:
    metadata_rows = parse_sections(rows).get("META_DATA", [])
    table = [
        {
            "key": str(row.get("key") or ""),
            "label": format_label(row.get("key")),
            "value": row.get("value"),
            "status": None,
        }
        for row in metadata_rows
        if row.get("key")
    ]
    if table:
        return table
    return [
        {
            "key": str(key),
            "label": format_label(key),
            "value": value,
            "status": None,
        }
        for key, value in metadata.items()
    ]


def parse_result_overview(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    overview = []
    for row in rows:
        key = str(row.get("key") or "")
        if not key.startswith("RESULT_"):
            continue
        section = key.replace("RESULT_", "", 1)
        status = normalize_status(row.get("value"))
        overview.append(
            {
                "section": section,
                "label": format_section_label(section),
                "status": status or row.get("value"),
                "passed": status == "PASS" if status else None,
            }
        )
    return overview


def parse_test_sections(rows: list[list[str]]) -> list[dict[str, Any]]:
    raw_sections = collect_raw_sections(rows)
    parsed_sections = []

    for section_key, section_rows in raw_sections.items():
        if section_key in IGNORED_STRUCTURED_SECTIONS:
            continue
        parsed_rows = parse_section_rows(section_rows)
        if not parsed_rows:
            continue
        failed_count = sum(1 for row in parsed_rows if row.get("status") == "FAIL")
        pass_count = sum(1 for row in parsed_rows if row.get("status") == "PASS")
        checked_count = pass_count + failed_count
        parsed_sections.append(
            {
                "section": section_key,
                "label": format_section_label(section_key),
                "status": "FAIL" if failed_count else ("PASS" if checked_count else None),
                "passed": False if failed_count else (True if checked_count else None),
                "total": checked_count,
                "pass": pass_count,
                "fail": failed_count,
                "rows": parsed_rows,
                "metrics": [row for row in parsed_rows if row.get("actual") is not None],
            }
        )

    return parsed_sections


def collect_raw_sections(rows: list[list[str]]) -> dict[str, list[list[str]]]:
    sections: dict[str, list[list[str]]] = {}
    current_section: str | None = None

    for row in rows:
        key = get_cell(row, 1)
        if not key:
            continue
        if key.endswith("_START"):
            current_section = key.removesuffix("_START")
            sections.setdefault(current_section, [])
            continue
        if key.endswith("_END") and current_section == key.removesuffix("_END"):
            current_section = None
            continue
        if current_section:
            sections.setdefault(current_section, []).append(row)

    return sections


def parse_section_rows(rows: list[list[str]]) -> list[dict[str, Any]]:
    specs = collect_row_specs(rows)
    parsed_rows = []

    for row in rows:
        key = get_cell(row, 1)
        if not key or is_spec_key(key):
            continue
        parsed = parse_test_row(row, specs.get(key, {}))
        if parsed is not None:
            parsed_rows.append(parsed)

    return parsed_rows


def collect_row_specs(rows: list[list[str]]) -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = get_cell(row, 1)
        spec_kind = parse_spec_kind(key)
        if spec_kind is None:
            continue
        base_key, kind = spec_kind
        specs.setdefault(base_key, {})[kind] = clean_number(get_cell(row, 2))
    return specs


def parse_test_row(row: list[str], spec: dict[str, Any]) -> dict[str, Any] | None:
    key = get_cell(row, 1)
    value_cells = [get_cell(row, index) for index in range(2, len(row))]
    status = None
    status_index = None
    for index, value in enumerate(value_cells):
        parsed_status = normalize_status(value)
        if parsed_status is not None:
            status = parsed_status
            status_index = index
            break

    if status_index is None:
        values = [value for value in value_cells if value not in ("", None)]
        trailing_values: list[str] = []
    else:
        values = [value for value in value_cells[:status_index] if value not in ("", None)]
        trailing_values = [value for value in value_cells[status_index + 1:] if value not in ("", None)]

    if not values and status is None:
        return None

    numeric_values = [clean_number(value) for value in values]
    numeric_values = [value for value in numeric_values if value is not None]
    actual = numeric_values[0] if numeric_values else None
    target = numeric_values[1] if len(numeric_values) > 1 else None
    spec_payload = {
        "min": spec.get("min"),
        "max": spec.get("max"),
        "target": target,
        "expected": values[1] if len(values) > 1 else None,
    }

    return {
        "key": key,
        "label": format_label(key),
        "time_s": clean_number(get_cell(row, 0)),
        "actual": actual,
        "target": target,
        "values": values,
        "extra_values": trailing_values,
        "status": status,
        "passed": status == "PASS" if status else None,
        "spec": spec_payload,
    }


def build_checks_from_sections(test_sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checks = []
    for section in test_sections:
        for row in section.get("rows") or []:
            if row.get("status") not in {"PASS", "FAIL"}:
                continue
            checks.append(
                {
                    "time_s": row.get("time_s"),
                    "key": row.get("key"),
                    "status": row.get("status"),
                    "values": row.get("values") or [],
                    "group": section.get("section"),
                }
            )
    return checks


def build_section_results(
    result_overview: list[dict[str, Any]],
    test_sections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    section_lookup = {str(section.get("section")): section for section in test_sections}
    results = []
    seen = set()

    for overview in result_overview:
        section_key = str(overview.get("section") or "")
        if section_key == "META_DATA":
            continue
        section = section_lookup.get(section_key)
        result = {
            "section": section_key,
            "label": overview.get("label") or format_section_label(section_key),
            "status": overview.get("status"),
            "passed": overview.get("passed"),
            "total": section.get("total", 0) if section else 0,
            "pass": section.get("pass", 0) if section else 0,
            "fail": section.get("fail", 0) if section else 0,
        }
        if result["passed"] is None and section:
            result["status"] = section.get("status")
            result["passed"] = section.get("passed")
        results.append(result)
        seen.add(section_key)

    for section in test_sections:
        section_key = str(section.get("section") or "")
        if section_key in seen:
            continue
        results.append(
            {
                "section": section_key,
                "label": section.get("label"),
                "status": section.get("status"),
                "passed": section.get("passed"),
                "total": section.get("total", 0),
                "pass": section.get("pass", 0),
                "fail": section.get("fail", 0),
            }
        )

    return results


def parse_spec_kind(key: str) -> tuple[str, str] | None:
    if key.endswith("-min"):
        return key.removesuffix("-min"), "min"
    if key.endswith("-max"):
        return key.removesuffix("-max"), "max"
    return None


def is_spec_key(key: str) -> bool:
    return parse_spec_kind(key) is not None


def build_test_matrices(test_sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    section_lookup = {str(section.get("section") or ""): section for section in test_sections}
    matrices = []
    plunger_matrix = build_plunger_matrix(section_lookup.get("PLUNGER"))
    if plunger_matrix:
        matrices.append(plunger_matrix)
    jaws_matrix = build_jaws_matrix(section_lookup.get("JAWS"))
    if jaws_matrix:
        matrices.append(jaws_matrix)
    return matrices


def build_plunger_matrix(section: dict[str, Any] | None) -> dict[str, Any] | None:
    rows = (section or {}).get("rows") or []
    if not rows:
        return None

    lookup = {str(row.get("key") or ""): row for row in rows}
    columns = []
    seen_columns = set()
    row_keys = [
        ("down-start", "Down-start"),
        ("down-end", "Down-end"),
        ("up-start", "Up-start"),
        ("up-end", "Up-end"),
    ]

    for row in rows:
        key = str(row.get("key") or "")
        parsed = parse_plunger_key(key)
        if parsed is None:
            continue
        column_key, _ = parsed
        if column_key in seen_columns:
            continue
        seen_columns.add(column_key)
        columns.append({"key": column_key, "label": column_key})

    matrix_rows = []
    for suffix, label in row_keys:
        values = []
        for column in columns:
            source = lookup.get(f"{column['key']}-{suffix}", {})
            values.append(build_matrix_cell(source))
        matrix_rows.append({"key": suffix, "label": label, "values": values})

    result_values = []
    for column in columns:
        column_statuses = []
        for suffix, _ in row_keys:
            status = (lookup.get(f"{column['key']}-{suffix}", {}) or {}).get("status")
            if status:
                column_statuses.append(str(status))
        result_values.append(
            {
                "status": "FAIL" if "FAIL" in column_statuses else ("PASS" if column_statuses else None),
                "passed": False if "FAIL" in column_statuses else (True if column_statuses else None),
                "actual": None,
                "target": None,
                "spec": {},
            }
        )
    matrix_rows.append({"key": "results", "label": "Results", "values": result_values})

    return {
        "key": "plunger",
        "section": "PLUNGER",
        "title": "Plunger Test",
        "columns": columns,
        "rows": matrix_rows,
    }


def build_jaws_matrix(section: dict[str, Any] | None) -> dict[str, Any] | None:
    rows = (section or {}).get("rows") or []
    if not rows:
        return None

    columns = [{"key": str(row.get("key") or ""), "label": str(row.get("key") or "")} for row in rows]
    values = [build_matrix_cell(row) for row in rows]
    return {
        "key": "jaws",
        "section": "JAWS",
        "title": "Jaws Test",
        "columns": columns,
        "rows": [{"key": "results", "label": "Results", "values": values}],
    }


def parse_plunger_key(key: str) -> tuple[str, str] | None:
    for suffix in ("down-start", "down-end", "up-start", "up-end"):
        marker = f"-{suffix}"
        if key.endswith(marker):
            return key.removesuffix(marker), suffix
    return None


def build_matrix_cell(row: dict[str, Any]) -> dict[str, Any]:
    status = row.get("status")
    return {
        "status": status,
        "passed": row.get("passed"),
        "actual": row.get("actual"),
        "target": row.get("target"),
        "spec": row.get("spec") or {},
        "key": row.get("key"),
    }


def format_section_label(value: Any) -> str:
    key = str(value or "")
    return SECTION_LABELS.get(key, format_label(key))


def format_label(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return " ".join(part.capitalize() for part in text.replace("_", "-").split("-") if part)
