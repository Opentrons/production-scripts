from __future__ import annotations

import csv
import os
import re
from datetime import datetime
from typing import Any

import settings as setting
from api.services.data import serialize_mongo_doc
from api.services.data_analysis import (
    read_google_sheet_rows,
    resolve_analysis_mapping,
)
from api.services.logging import logger
from api.services.test_names import canonical_test_type
from data_analysis.service import analyze_file
from database.mongodb import mongodb
from upload_handler.drivers.google_drive import GoogleDriveDriver
from upload_handler.parsers.csv_common import extract_meta_data_from_csv, read_csv_rows
from upload_handler.product_catalog import get_model_from_serial_number


UNIT_TRACKER_CACHE_DIR = os.path.join(setting.TESTING_DATA_DIR, "unit_tracker_cache")

STANDARD_COLUMNS = [
    {"key": "location", "label": "Location"},
    {"key": "firmware", "label": "FW"},
    {"key": "sn", "label": "SN"},
    {"key": "link", "label": "Link"},
    {"key": "operator_name", "label": "OperatorName"},
    {"key": "current_plunger", "label": "CurrentPlunger"},
    {"key": "current_jaws", "label": "CurrentJaws"},
    {"key": "capacitance", "label": "CAPACITANCE"},
    {"key": "pressure", "label": "PRESSURE"},
    {"key": "environment_sensor", "label": "ENVIRONMENT-SENSOR"},
    {"key": "tip_sensor", "label": "TIP-SENSOR"},
    {"key": "droplets", "label": "DROPLETS"},
    {"key": "plunger_current_0_6_speed_5", "label": "current-0.6-speed-5"},
    {"key": "plunger_current_0_6_speed_15", "label": "current-0.6-speed-15"},
    {"key": "plunger_current_0_6_speed_22", "label": "current-0.6-speed-22"},
    {"key": "plunger_current_0_7_speed_5", "label": "current-0.7-speed-5"},
    {"key": "plunger_current_0_7_speed_15", "label": "current-0.7-speed-15"},
    {"key": "plunger_current_0_7_speed_22", "label": "current-0.7-speed-22"},
    {"key": "plunger_current_0_8_speed_5", "label": "current-0.8-speed-5"},
    {"key": "plunger_current_0_8_speed_15", "label": "current-0.8-speed-15"},
    {"key": "plunger_current_0_8_speed_22", "label": "current-0.8-speed-22"},
    {"key": "jaws_current_0_7_speed_8", "label": "current-0.7-speed-8"},
    {"key": "jaws_current_0_7_speed_12", "label": "current-0.7-speed-12"},
    {"key": "jaws_current_1_5_speed_8", "label": "current-1.5-speed-8"},
    {"key": "jaws_current_1_5_speed_12", "label": "current-1.5-speed-12"},
    {"key": "capacitance_primary_air", "label": "Air"},
    {"key": "capacitance_primary_attached", "label": "Attached"},
    {"key": "capacitance_primary_deck", "label": "Deck"},
    {"key": "capacitance_secondary_air", "label": "Air"},
    {"key": "capacitance_secondary_attached", "label": "Attached"},
    {"key": "capacitance_secondary_deck", "label": "Deck"},
    {"key": "pressure_primary_open", "label": "Open"},
    {"key": "pressure_primary_sealed", "label": "Sealed"},
    {"key": "pressure_primary_aspirate", "label": "Aspirate"},
    {"key": "pressure_primary_dispense", "label": "Dispense"},
    {"key": "pressure_secondary_open", "label": "Open"},
    {"key": "pressure_secondary_sealed", "label": "Sealed"},
    {"key": "pressure_secondary_aspirate", "label": "Aspirate"},
    {"key": "pressure_secondary_dispense", "label": "Dispense"},
    {"key": "environment_s0_celsius", "label": "Celsius"},
    {"key": "environment_s0_humidity", "label": "Humidity"},
    {"key": "environment_s1_celsius", "label": "Celsius"},
    {"key": "environment_s1_humidity", "label": "Humidity"},
    {"key": "tip_empty", "label": "Empty"},
    {"key": "tip_with_tip", "label": "With Tip"},
    {"key": "droplets_96_tips", "label": "96 Tips"},
    {"key": "file_path", "label": "File Path"},
]

SUPPORTED_TESTS = {"Assembly QC"}


def resolve_standard_columns(product: str | None, test_type: str | None) -> list[dict[str, Any]]:
    if product and test_type:
        try:
            mapping = resolve_analysis_mapping(product, test_type)
            return standard_columns_from_mapping(mapping)
        except Exception as exc:
            logger.warning("Unit tracker standard columns fallback for %s/%s: %s", product, test_type, exc)
    return [dict(column) for column in STANDARD_COLUMNS]


def standard_columns_from_mapping(mapping: dict[str, Any]) -> list[dict[str, Any]]:
    standard_line = mapping.get("standard_line") or {}
    groups = standard_line.get("groups") or []
    columns: list[dict[str, Any]] = []

    for group in groups:
        group_label = str(group.get("label") or group.get("key") or "").strip()
        group_key = str(group.get("key") or group_label).strip()
        for column in group.get("columns") or []:
            key = str(column.get("key") or "").strip()
            if not key:
                continue
            columns.append(
                {
                    "key": key,
                    "label": str(column.get("label") or key).strip(),
                    "group": group_label,
                    "group_key": group_key,
                }
            )

    return columns or [dict(column) for column in STANDARD_COLUMNS]


def get_unit_tracker_collection():
    if mongodb.client is None and not mongodb.connect():
        raise RuntimeError("Unit tracker database connection failed")
    collection = mongodb.get_database(setting.MESSAGE_COLLECTION)[setting.UNIT_TRACKER_COLLECTION]
    try:
        collection.create_index("record_id", unique=True)
        collection.create_index("product")
        collection.create_index("test_type")
        collection.create_index("sn")
        collection.create_index("updated_at")
    except Exception as exc:
        logger.warning("Unit tracker index creation skipped: %s", exc)
    return collection


def get_upload_record_collection():
    if mongodb.client is None and not mongodb.connect():
        raise RuntimeError("Upload record database connection failed")
    return mongodb.get_database(setting.MESSAGE_COLLECTION)[setting.DATA_UPLOAD_RECORD_COLLECTION]


def list_rows(page: int = 1, page_size: int = 100, product: str | None = None, test_type: str | None = None, barcode: str | None = None) -> dict[str, Any]:
    try:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 2000)
        query: dict[str, Any] = {}
        normalized_product = str(product or "").strip()
        normalized_test_type = canonical_test_type(test_type) if test_type else ""
        if product:
            query["product"] = normalized_product
        if test_type:
            query["test_type"] = normalized_test_type
        if barcode:
            query["sn"] = {"$regex": re.escape(str(barcode).strip()), "$options": "i"}

        columns = resolve_standard_columns(normalized_product, normalized_test_type)
        collection = get_unit_tracker_collection()
        total = collection.count_documents(query)
        cursor = collection.find(query).sort("updated_at", -1).skip((page - 1) * page_size).limit(page_size)
        return {
            "columns": columns,
            "rows": [serialize_mongo_doc(doc) for doc in cursor],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except Exception as exc:
        logger.error("Error fetching unit tracker rows: %s", exc, exc_info=True)
        return {
            "columns": resolve_standard_columns(product or "", test_type or ""),
            "rows": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "error": str(exc),
        }


def sync_all_rows(limit: int | None = None) -> dict[str, Any]:
    collection = get_upload_record_collection()
    query = {
        "status": "success",
        "$or": [
            {"result.csv_link": {"$exists": True, "$nin": [None, "", "N/A", "NA"]}},
            {"upload_result.csv_link": {"$exists": True, "$nin": [None, "", "N/A", "NA"]}},
        ],
    }
    cursor = collection.find(query).sort("request_started_at", -1)
    if limit:
        cursor = cursor.limit(max(1, int(limit)))

    scanned = 0
    updated = 0
    skipped = 0
    errors: list[dict[str, Any]] = []

    for record in cursor:
        scanned += 1
        try:
            result = sync_record(record)
            if result.get("updated"):
                updated += 1
            else:
                skipped += 1
        except Exception as exc:
            skipped += 1
            logger.warning("Unit tracker sync skipped record %s: %s", record.get("_id"), exc, exc_info=True)
            errors.append({"record_id": str(record.get("_id") or ""), "message": str(exc)})

    return {
        "success": True,
        "scanned": scanned,
        "updated": updated,
        "skipped": skipped,
        "errors": errors[:50],
    }


def sync_record(record: dict[str, Any]) -> dict[str, Any]:
    record_id = str(record.get("_id") or "")
    csv_link = resolve_record_csv_link(record)
    if not record_id or not csv_link:
        return {"updated": False, "reason": "missing csv link"}

    product = resolve_record_product(record)
    test_type = resolve_record_test_type(record)
    if test_type not in SUPPORTED_TESTS:
        return {"updated": False, "reason": f"unsupported test type: {test_type or '-'}"}

    mapping = resolve_analysis_mapping(product, test_type)
    if str(mapping.get("analyzer") or "") != "pipette_assembly_qc":
        return {"updated": False, "reason": f"unsupported analyzer: {mapping.get('analyzer') or '-'}"}

    csv_path = save_record_sheet_csv(record, product=product, test_type=test_type, mapping=mapping, csv_link=csv_link)
    standard_row = build_assembly_qc_standard_row(csv_path=csv_path, csv_link=csv_link)
    standard_columns = standard_columns_from_mapping(mapping)
    now = datetime.now()
    document = {
        "record_id": record_id,
        "upload_record_id": record_id,
        "product": product,
        "test_type": test_type,
        "sn": standard_row.get("sn") or resolve_record_barcode(record),
        "csv_link": csv_link,
        "file_path": csv_path,
        "columns": standard_columns,
        "row": standard_row,
        "updated_at": now,
        "source_request_started_at": record.get("request_started_at"),
    }
    get_unit_tracker_collection().update_one(
        {"record_id": record_id},
        {
            "$set": document,
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    return {"updated": True, "record_id": record_id}


def resolve_record_csv_link(record: dict[str, Any]) -> str:
    return normalize_link((record.get("result") or {}).get("csv_link") or (record.get("upload_result") or {}).get("csv_link"))


def resolve_record_product(record: dict[str, Any]) -> str:
    model = first_text(
        (record.get("file_desc") or {}).get("model"),
        (record.get("result") or {}).get("model"),
        (record.get("upload_result") or {}).get("model"),
    )
    if model and model != "NA":
        return normalize_product_name(model)
    return normalize_product_name(get_model_from_serial_number(resolve_record_barcode(record)))


def resolve_record_test_type(record: dict[str, Any]) -> str:
    return canonical_test_type(
        (record.get("result") or {}).get("test_type")
        or (record.get("file_desc") or {}).get("test_type")
        or (record.get("upload_result") or {}).get("upload_config_key")
    )


def resolve_record_barcode(record: dict[str, Any]) -> str:
    return first_text(
        (record.get("file_desc") or {}).get("sn"),
        (record.get("result") or {}).get("sn"),
        (record.get("upload_result") or {}).get("sn"),
    )


def save_record_sheet_csv(record: dict[str, Any], *, product: str, test_type: str, mapping: dict[str, Any], csv_link: str) -> str:
    sheet_name = str(mapping.get("sheet_name") or "").strip()
    if not sheet_name:
        raise ValueError(f"No sheet name configured for {product}/{test_type}")

    spreadsheet_id = GoogleDriveDriver.parse_drive_file_id(csv_link)
    if not spreadsheet_id:
        raise ValueError("Invalid Google Sheet link")

    rows = read_google_sheet_rows(spreadsheet_id, sheet_name, mapping.get("cols") or [])
    if not rows:
        raise ValueError(f"No data found in sheet {sheet_name}")

    os.makedirs(UNIT_TRACKER_CACHE_DIR, exist_ok=True)
    barcode = resolve_record_barcode(record) or str(record.get("_id") or "unit")
    filename = sanitize_cache_filename(f"{barcode}-{test_type}-{sheet_name}.csv")
    path = os.path.join(UNIT_TRACKER_CACHE_DIR, product, canonical_test_type(test_type), filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write_csv_rows(path, rows)
    return path


def write_csv_rows(path: str, rows: list[list[Any]]) -> None:
    max_columns = max((len(row) for row in rows), default=0)
    with open(path, "w", newline="", encoding="utf-8") as output_file:
        writer = csv.writer(output_file)
        for row in rows:
            writer.writerow(list(row) + [""] * (max_columns - len(row)))


def build_assembly_qc_standard_row(*, csv_path: str, csv_link: str) -> dict[str, Any]:
    analysis = analyze_file(csv_path)
    if analysis.get("channel") != "pipette_assembly_qc":
        raise ValueError(f"Unsupported analysis channel: {analysis.get('channel') or '-'}")

    rows = read_csv_rows(csv_path)
    metadata = extract_meta_data_from_csv(csv_path)
    values = build_key_value_lookup(rows)
    overview = build_result_overview_lookup(rows)
    standard_row: dict[str, Any] = {
        "location": "SZ",
        "firmware": first_text(metadata.get("firmware"), value_at(values, "firmware")),
        "sn": first_text(analysis.get("sn"), metadata.get("test_device_id"), metadata.get("test_tag")),
        "link": csv_link,
        "operator_name": first_text(metadata.get("test_operator"), metadata.get("operator-name"), value_at(values, "test_operator")),
        "current_plunger": overview.get("PLUNGER"),
        "current_jaws": overview.get("JAWS"),
        "capacitance": overview.get("CAPACITANCE"),
        "pressure": overview.get("PRESSURE"),
        "environment_sensor": overview.get("ENVIRONMENT-SENSOR"),
        "tip_sensor": overview.get("TIP-SENSOR"),
        "droplets": overview.get("DROPLETS"),
        "file_path": csv_path,
    }

    plunger_matrix = find_matrix(analysis, "plunger")
    for column_key in [
        "current-0.6-speed-5",
        "current-0.6-speed-15",
        "current-0.6-speed-22",
        "current-0.7-speed-5",
        "current-0.7-speed-15",
        "current-0.7-speed-22",
        "current-0.8-speed-5",
        "current-0.8-speed-15",
        "current-0.8-speed-22",
    ]:
        standard_row[f"plunger_{slug_key(column_key)}"] = matrix_result_status(plunger_matrix, column_key)

    jaws_matrix = find_matrix(analysis, "jaws")
    for column_key in [
        "current-0.7-speed-8",
        "current-0.7-speed-12",
        "current-1.5-speed-8",
        "current-1.5-speed-12",
    ]:
        standard_row[f"jaws_{slug_key(column_key)}"] = matrix_result_status(jaws_matrix, column_key)

    standard_row.update(
        {
            "capacitance_primary_air": value_at(values, "primary-air-pf"),
            "capacitance_primary_attached": value_at(values, "primary-attached-pf"),
            "capacitance_primary_deck": value_at(values, "primary-deck-pf"),
            "capacitance_secondary_air": value_at(values, "secondary-air-pf"),
            "capacitance_secondary_attached": value_at(values, "secondary-attached-pf"),
            "capacitance_secondary_deck": value_at(values, "secondary-deck-pf"),
            "pressure_primary_open": value_at(values, "primary-open-pa"),
            "pressure_primary_sealed": value_at(values, "primary-sealed-pa"),
            "pressure_primary_aspirate": value_at(values, "primary-aspirate-pa"),
            "pressure_primary_dispense": value_at(values, "primary-dispense-pa"),
            "pressure_secondary_open": value_at(values, "secondary-open-pa"),
            "pressure_secondary_sealed": value_at(values, "secondary-sealed-pa"),
            "pressure_secondary_aspirate": value_at(values, "secondary-aspirate-pa"),
            "pressure_secondary_dispense": value_at(values, "secondary-dispense-pa"),
        }
    )
    standard_row.update(parse_environment(values))
    standard_row.update(
        {
            "tip_empty": value_at(values, "tip-sensor-empty"),
            "tip_with_tip": value_at(values, "tip-sensor-with-tips"),
            "droplets_96_tips": row_status_at(values, "droplets-96-tips"),
        }
    )
    return standard_row


def build_key_value_lookup(rows: list[list[str]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = get_cell(row, 1)
        if not key:
            continue
        lookup[key] = {
            "value": parse_cell(get_cell(row, 2)),
            "extra": parse_cell(get_cell(row, 3)),
            "status": parse_status_cells(row[2:]),
            "row": row,
        }
    return lookup


def build_result_overview_lookup(rows: list[list[str]]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for row in rows:
        key = get_cell(row, 1)
        if not key.startswith("RESULT_"):
            continue
        results[key.removeprefix("RESULT_")] = normalize_display_value(get_cell(row, 2))
    return results


def parse_environment(values: dict[str, dict[str, Any]]) -> dict[str, Any]:
    s0 = values.get("environment-S0-celsius-humidity") or {}
    s1 = values.get("environment-S1-celsius-humidity") or {}
    return {
        "environment_s0_celsius": s0.get("value"),
        "environment_s0_humidity": s0.get("extra"),
        "environment_s1_celsius": s1.get("value"),
        "environment_s1_humidity": s1.get("extra"),
    }


def find_matrix(analysis: dict[str, Any], key: str) -> dict[str, Any] | None:
    return next((matrix for matrix in analysis.get("test_matrices") or [] if matrix.get("key") == key), None)


def matrix_result_status(matrix: dict[str, Any] | None, column_key: str) -> Any:
    if not matrix:
        return None
    columns = matrix.get("columns") or []
    column_index = next((index for index, column in enumerate(columns) if column.get("key") == column_key), -1)
    if column_index < 0:
        return None
    result_row = next((row for row in matrix.get("rows") or [] if row.get("key") == "results"), None)
    values = (result_row or {}).get("values") or []
    if column_index >= len(values):
        return None
    return values[column_index].get("status")


def value_at(values: dict[str, dict[str, Any]], key: str) -> Any:
    return (values.get(key) or {}).get("value")


def row_status_at(values: dict[str, dict[str, Any]], key: str) -> Any:
    item = values.get(key) or {}
    return item.get("status") or item.get("value")


def parse_status_cells(cells: list[Any]) -> str | None:
    for cell in cells:
        text = str(cell or "").strip().upper()
        if text in {"PASS", "PASSED"}:
            return "PASS"
        if text in {"FAIL", "FAILED"}:
            return "FAIL"
    return None


def normalize_display_value(value: Any) -> Any:
    text = str(value or "").strip()
    if text == "":
        return None
    if text.lower() == "none":
        return "None"
    if text.upper() == "PASS":
        return "PASS"
    if text.upper() == "FAIL":
        return "FAIL"
    return parse_cell(text)


def parse_cell(value: Any) -> Any:
    text = str(value or "").strip()
    if text == "":
        return None
    if text.lower() == "none":
        return None
    try:
        number = float(text)
    except ValueError:
        return text
    return int(number) if number.is_integer() else number


def normalize_product_name(value: Any) -> str:
    text = str(value or "").strip()
    if text == "P200-96":
        return "P2HH"
    if text == "P1000-96":
        return "P1KH"
    return text


def first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text and text.upper() not in {"NA", "N/A", "NONE", "NULL"}:
            return text
    return ""


def normalize_link(value: Any) -> str:
    text = first_text(value)
    return text if text.startswith("http") else ""


def get_cell(row: list[Any], index: int) -> str:
    if index >= len(row):
        return ""
    return str(row[index]).strip()


def slug_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def sanitize_cache_filename(value: str) -> str:
    text = re.sub(r"[^\w.\- %()]+", "-", value).strip(".- ")
    return text or "unit-tracker.csv"
