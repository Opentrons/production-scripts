"""Upload workflow for the 96-channel pressure fixture reports.

The legacy desktop tool uploaded a CSV into a copied Google Sheet and then
copied the ``Pressure Test-*`` blocks into a type/model summary sheet.  This
module keeps that behaviour server-side while using the backend's shared
Google credentials and durable upload records.
"""

from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from core.logging import get_logger
from modules.uploads.handler.drivers.google_drive import GoogleDriveDriver
from modules.uploads.handler.parsers.csv_common import extract_meta_data_from_csv

logger = get_logger(__name__)

REPORT_TYPES = ("QC", "GRAVIMETRIC", "LIFETIME")
PRESSURE_TEST_SOURCE_SHEETS = tuple(f"Pressure Test-{index}" for index in range(1, 11))
PRESSURE_TEST_SOURCE_RANGE = "A4:AR12"
CSV_TARGET_SHEET = "CSV test results"

CSV_TEMPLATE_TARGETS: dict[str, dict[str, Any]] = {
    "QC": {
        "P200H": {
            "template_spreadsheet_id": "1wKgmD9QEiuSxmK9dqFn6uObsZwNbRYXrCEStYApflo4",
            "checking_spreadsheet_id": "13_RrTw-6GzSsNkvqv3EJLmxTN1l-g90WObFCDvmg5-g",
            "checking_sheet_name": "P200H fixturePressure Test checking sheet  qc",
        },
        "P1KH": {
            "template_spreadsheet_id": "1PF0FBb3FA7ZIOa5W7V8iMtZUsOyI95T4Gbzz-5TJ-fg",
            "checking_spreadsheet_id": "14qVA8F_f3Z2D6mZ5f0HJfPLLfKwlaB8Z_dDU-aYsZ7Q",
            "checking_sheet_name": "P1000H fixturePressure Test checking sheet qc",
        },
    },
    "GRAVIMETRIC": {
        "P200H": {
            "template_spreadsheet_id": "1wKgmD9QEiuSxmK9dqFn6uObsZwNbRYXrCEStYApflo4",
            "checking_spreadsheet_id": "13_RrTw-6GzSsNkvqv3EJLmxTN1l-g90WObFCDvmg5-g",
            "checking_sheet_name": "P200H fixturePressure Test checking sheet gravimetric",
        },
        "P1KH": {
            "template_spreadsheet_id": "1PF0FBb3FA7ZIOa5W7V8iMtZUsOyI95T4Gbzz-5TJ-fg",
            "checking_spreadsheet_id": "14qVA8F_f3Z2D6mZ5f0HJfPLLfKwlaB8Z_dDU-aYsZ7Q",
            "checking_sheet_name": "P1000H fixturePressure Test checking sheet gravimetric",
        },
    },
    "LIFETIME": {
        "P200H": {
            "template_spreadsheet_id": "18Ty_rI1C7CT19aB0WcvsnuDcs6w7hYyc36tAMWpvcqA",
            "checking_spreadsheet_id": "1-uT4eS5LzR-MYszjmuRw5IkRa3MN-8oDLbuY_9GdIgs",
            "checking_sheet_name": "P200H fixturePressure Test checking sheet lifetime",
        },
        "P1000H": {
            "template_spreadsheet_id": "1VdnsdALAs66MdI7s6gUmX8cTMNcCtRzhgPBETCcbZCw",
            "checking_spreadsheet_id": "1-uT4eS5LzR-MYszjmuRw5IkRa3MN-8oDLbuY_9GdIgs",
            "checking_sheet_name": "P1000H fixturePressure Test checking sheet lifetime",
        },
    },
}

PRESSURE_TEST_TARGETS: dict[str, dict[str, dict[str, str]]] = {
    "QC": {
        "P200H": {"spreadsheet_id": "1mnajeBwqWJMYmoxeo1PiJ1MRDrN9F68meW2UudxIQO4", "sheet_name": "诊断测试 production 96ch 200ul"},
        "P1KH": {"spreadsheet_id": "1wzxt0Fx18yct7djzxjJoUycvOd1G2I4mRYaJfL9JGRs", "sheet_name": "诊断测试production 96ch 1000ul"},
    },
    "GRAVIMETRIC": {
        "P200H": {"spreadsheet_id": "1mnajeBwqWJMYmoxeo1PiJ1MRDrN9F68meW2UudxIQO4", "sheet_name": "容量测试  production 96ch 200ul"},
        "P1KH": {"spreadsheet_id": "1wzxt0Fx18yct7djzxjJoUycvOd1G2I4mRYaJfL9JGRs", "sheet_name": "容量测试 production 96ch 1000ul"},
    },
    "LIFETIME": {
        "P200H": {"spreadsheet_id": "1gZAkLVAJzMhafPwMyjB8U8f5ycPR0qaRXmGR4ovghyo", "sheet_name": "老化测试 production 96ch 200H"},
        "P1000H": {"spreadsheet_id": "1gZAkLVAJzMhafPwMyjB8U8f5ycPR0qaRXmGR4ovghyo", "sheet_name": "老化测试 production 96ch 1000H"},
    },
}


def normalize_report_type(value: str | None) -> str:
    normalized = str(value or "").strip().upper()
    if normalized not in REPORT_TYPES:
        raise ValueError(f"不支持的 report_type: {value}，仅支持 QC、GRAVIMETRIC 或 LIFETIME")
    return normalized


def resolve_model_key(serial_number: str, report_type: str) -> str:
    """Map the serial prefix to the keys used by the legacy summary tables."""
    sn = str(serial_number or "").strip().upper()
    report = normalize_report_type(report_type)
    if sn.startswith(("P2HH", "P200H")):
        return "P200H"
    if sn.startswith(("P1KH", "P1000H")):
        return "P1000H" if report == "LIFETIME" else "P1KH"
    raise ValueError(f"无法从序列号识别 96 通道型号: {serial_number}")


def is_nonzero_number(value: Any) -> bool:
    text = str(value or "").strip().replace(",", "")
    if text.endswith("%"):
        text = text[:-1]
    if not text:
        return False
    try:
        return float(text) != 0
    except (TypeError, ValueError):
        return False


def normalize_pressure_rows(rows: list[list[Any]]) -> list[list[str]]:
    """Keep non-empty rows and skip a whole sheet when all measurements are zero."""
    candidate_rows: list[list[str]] = []
    for row in rows:
        normalized = [str(cell) for cell in list(row[:44])]
        normalized.extend([""] * (44 - len(normalized)))
        if any(cell.strip() for cell in normalized):
            candidate_rows.append(normalized)
    if not candidate_rows or not any(is_nonzero_number(cell) for row in candidate_rows for cell in row):
        return []
    return candidate_rows


def first_blank_row(values: list[list[Any]], start_row: int = 1) -> int:
    for offset, row in enumerate(values):
        if not any(str(cell).strip() for cell in row):
            return start_row + offset
    return start_row + len(values)


def extract_serial_number(csv_path: str) -> str:
    metadata = extract_meta_data_from_csv(csv_path)
    for key in ("test_tag", "test_device_id", "test_device", "serial_number"):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value.replace("-qc", "")
    match = re.search(r"(P(?:1KH|2HH|1000H|200H)[A-Za-z0-9]+)", Path(csv_path).stem, re.IGNORECASE)
    if match:
        return match.group(1)
    raise ValueError("CSV 中未找到 96 通道移液器序列号")


def _quoted_sheet(sheet_name: str, cell_range: str) -> str:
    return f"'{sheet_name.replace(chr(39), chr(39) + chr(39))}'!{cell_range}"


def _column_name(number: int) -> str:
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _read_rows(driver: Any, spreadsheet_id: str, sheet_name: str, cell_range: str) -> list[list[Any]]:
    values = driver.get_excel_sheet(
        spreadsheet_id,
        _quoted_sheet(sheet_name, cell_range),
        majorDimensionval="ROWS",
        raise_on_error=True,
    )
    return values or []


def _write_rows(driver: Any, spreadsheet_id: str, sheet_name: str, cell_range: str, values: list[list[Any]]) -> None:
    driver.sheet_service_client.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=_quoted_sheet(sheet_name, cell_range),
        valueInputOption="USER_ENTERED",
        body={"values": values},
    ).execute()


def _append_rows_with_group_merges(
    driver: Any,
    spreadsheet_id: str,
    sheet_name: str,
    cell_range: str,
    values: list[list[Any]],
    group_ranges: list[dict[str, Any]],
) -> None:
    """Write rows while preserving the summary sheet's existing merged cells."""
    service = getattr(driver, "sheet_service_client", None)
    spreadsheets = service.spreadsheets() if service is not None else None
    if spreadsheets is None or not hasattr(spreadsheets, "get"):
        _write_rows(driver, spreadsheet_id, sheet_name, cell_range, values)
        return

    metadata = spreadsheets.get(
        spreadsheetId=spreadsheet_id,
        fields="sheets(properties(sheetId,title),merges)",
    ).execute()
    sheet = next(
        (
            item for item in metadata.get("sheets", [])
            if item.get("properties", {}).get("title") == sheet_name
        ),
        None,
    )
    if not sheet:
        raise RuntimeError(f"未找到目标总表 sheet: {sheet_name}")
    sheet_id = int(sheet["properties"]["sheetId"])
    start_row = int(re.search(r"A(\d+):", cell_range).group(1))
    end_row = int(re.search(r":AS(\d+)$", cell_range).group(1))
    existing_merges = []
    for merge in sheet.get("merges", []) or []:
        if merge.get("sheetId") != sheet_id:
            continue
        if int(merge.get("startRowIndex", 0)) < end_row and int(merge.get("endRowIndex", 0)) > start_row - 1:
            if int(merge.get("startColumnIndex", 0)) < 45 and int(merge.get("endColumnIndex", 0)) > 0:
                existing_merges.append(dict(merge))
    if existing_merges:
        spreadsheets.batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"unmergeCells": {"range": merge}} for merge in existing_merges]},
        ).execute()
    try:
        _write_rows(driver, spreadsheet_id, sheet_name, cell_range, values)
        merge_requests = [{"mergeCells": {"range": merge, "mergeType": "MERGE_ALL"}} for merge in existing_merges]
        for group in group_ranges:
            if int(group["end_row"]) <= int(group["start_row"]):
                continue
            for start_column, end_column in ((0, 1), (1, 2)):
                merge_requests.append({
                    "mergeCells": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": int(group["start_row"]) - 1,
                            "endRowIndex": int(group["end_row"]),
                            "startColumnIndex": start_column,
                            "endColumnIndex": end_column,
                        },
                        "mergeType": "MERGE_ALL",
                    }
                })
        if merge_requests:
            spreadsheets.batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": merge_requests},
            ).execute()
    except Exception:
        # Restore the pre-existing merge layout if the write fails midway.
        if existing_merges:
            spreadsheets.batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": [{"mergeCells": {"range": merge, "mergeType": "MERGE_ALL"}} for merge in existing_merges]},
            ).execute()
        raise


def append_pressure_summary(
    driver: Any,
    *,
    source_spreadsheet_id: str,
    model_key: str,
    report_type: str,
) -> dict[str, Any]:
    report = normalize_report_type(report_type)
    target = PRESSURE_TEST_TARGETS[report][model_key]
    source_gid_map = driver.get_sheet_gid_map(source_spreadsheet_id) or {}
    groups: list[dict[str, Any]] = []
    for sheet_name in PRESSURE_TEST_SOURCE_SHEETS:
        if sheet_name not in source_gid_map:
            continue
        rows = normalize_pressure_rows(_read_rows(driver, source_spreadsheet_id, sheet_name, PRESSURE_TEST_SOURCE_RANGE))
        if rows:
            groups.append({
                "sheet_name": sheet_name,
                "sheet_link": f"https://docs.google.com/spreadsheets/d/{source_spreadsheet_id}/edit#gid={source_gid_map[sheet_name]}",
                "rows": rows,
            })
    if not groups:
        return {"updated": False, "reason": "未读取到非零 Pressure Test 数据", **target, "row_count": 0}

    existing = _read_rows(driver, target["spreadsheet_id"], target["sheet_name"], "A:AS")
    existing_links = {str(row[0]).strip() for row in existing if row and str(row[0]).strip()}
    groups = [group for group in groups if group["sheet_link"] not in existing_links]
    if not groups:
        return {"updated": False, "deduplicated": True, "reason": "Pressure Test 总表已存在该报告链接", **target, "row_count": 0}

    row_number = first_blank_row(existing, start_row=1)
    payload: list[list[str]] = []
    group_ranges: list[dict[str, Any]] = []
    for group in groups:
        start = row_number + len(payload)
        for index, row in enumerate(group["rows"]):
            payload.append(([group["sheet_link"]] if index == 0 else [""]) + row)
        group_ranges.append({"sheet_name": group["sheet_name"], "start_row": start, "end_row": start + len(group["rows"]) - 1})
    end_row = row_number + len(payload) - 1
    _append_rows_with_group_merges(
        driver,
        target["spreadsheet_id"],
        target["sheet_name"],
        f"A{row_number}:AS{end_row}",
        payload,
        group_ranges,
    )
    return {
        "updated": True,
        "report_type": report,
        "spreadsheet_id": target["spreadsheet_id"],
        "sheet_name": target["sheet_name"],
        "target_range": f"A{row_number}:AS{end_row}",
        "row_count": len(payload),
        "groups": group_ranges,
    }


def process_pressure_upload(
    csv_path: str,
    *,
    report_type: str,
    progress_callback: Callable[[str, dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    report = normalize_report_type(report_type)
    if not Path(csv_path).is_file():
        raise FileNotFoundError(csv_path)
    serial_number = extract_serial_number(csv_path)
    model_key = resolve_model_key(serial_number, report)
    target = CSV_TEMPLATE_TARGETS[report][model_key]
    rows: list[list[str]] = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if not rows:
        raise ValueError("CSV 文件没有可上传的数据")

    def stage(name: str, message: str, checkpoint: dict[str, Any] | None = None) -> None:
        if progress_callback:
            progress_callback("stage", {"stage": name, "message": message, "checkpoint": checkpoint or {}})

    stage("pressure_validate", f"已识别 {serial_number} / {report}")
    driver = GoogleDriveDriver()
    stage("prepare_spreadsheet", "正在复制 96 通道模板")
    copied = driver.copy_file(target["template_spreadsheet_id"], f"{serial_number}_{datetime.now():%Y%m%d%H%M%S}")
    if not copied:
        raise RuntimeError(f"复制 96 通道模板失败: {driver.last_error or 'unknown error'}")
    _, spreadsheet_id = copied
    spreadsheet_link = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"

    stage("write_spreadsheet", "正在写入 CSV 数据")
    _write_rows(driver, spreadsheet_id, CSV_TARGET_SHEET, f"A1:{_column_name(max(len(row) for row in rows))}{len(rows)}", rows)
    stage("read_summary", "正在读取 Summary 和 Pressure Test")
    summary_rows = _read_rows(driver, spreadsheet_id, "Summary", "A2:Q2")
    summary_row = summary_rows[0] if summary_rows else []

    checking_values = _read_rows(driver, target["checking_spreadsheet_id"], target["checking_sheet_name"], "B2:R")
    checking_row = first_blank_row(checking_values, start_row=2)
    checking_payload = [[spreadsheet_link] + list(summary_row[:17])]
    checking_payload[0].extend([""] * (18 - len(checking_payload[0])))
    _write_rows(driver, target["checking_spreadsheet_id"], target["checking_sheet_name"], f"A{checking_row}:R{checking_row}", checking_payload)
    stage("append_pressure_summary", "正在追加 Pressure Test 总表")
    pressure_update = append_pressure_summary(
        driver,
        source_spreadsheet_id=spreadsheet_id,
        model_key=model_key,
        report_type=report,
    )
    result = {
        "finished": True,
        "sn": serial_number,
        "model": model_key,
        "test_type": report,
        "csv_link": spreadsheet_link,
        "test_result": summary_row[1] if len(summary_row) > 1 else "",
        "pressure_summary": pressure_update,
        "checking_sheet": {"row": checking_row, "spreadsheet_id": target["checking_spreadsheet_id"], "sheet_name": target["checking_sheet_name"]},
        "pressure_report_type": report,
    }
    if progress_callback:
        progress_callback("file_desc", {"sn": serial_number, "model": model_key, "test_type": report, "file_path": csv_path})
        progress_callback("upload_result", result)
    return result

