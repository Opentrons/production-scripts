from __future__ import annotations

import csv
import math
from threading import Lock


# Each destination starts with Robot, followed by the measurements.
# START_TIME and RESULT_STATUS remain in the full template CSV only.
PARALLELISM_TARGETS = {
    "z_leveling_test": ("Z Stage Parallelism", "C", "AP", 40),
    "ch8_leveling_test": ("Pipette To Deck Parallelism", "B", "N", 13),
    "ch96_leveling_test": ("Pipette To Deck Parallelism", "P", "BB", 39),
    "gripper_leveling_test": ("Gripper Parallelism", "B", "K", 10),
}
_APPEND_LOCK = Lock()


def extract_parallelism_rows(csv_path: str, robot_sn: str) -> dict[str, list[list]]:
    """Read named TEST blocks, validating every row before any remote writes."""
    with open(csv_path, encoding="utf-8-sig", newline="") as csv_file:
        rows = [[cell.strip() for cell in row] for row in csv.reader(csv_file)]
    sections: dict[str, list[list]] = {}
    active = None
    header = None
    for row in rows:
        # Reports exported as rectangular CSVs pad shorter sections with empty
        # cells. Ignore only trailing padding in this extracted summary view.
        while row and row[-1] == "":
            row.pop()
        if not any(row):
            continue
        if len(row) >= 2 and row[1] == "TEST":
            name = row[2] if len(row) > 2 else ""
            active = name if name in PARALLELISM_TARGETS else None
            header = None
            if active:
                if active in sections:
                    raise ValueError(f"平行度 CSV 包含重复测试段: {active}")
                sections[active] = []
            continue
        if active is None:
            continue
        width = PARALLELISM_TARGETS[active][3]
        if header is None:
            header = [cell.upper() for cell in row]
            if (
                header[:2] != ["START_TIME", "ROBOT_SN"]
                or header[-1] != "RESULT_STATUS"
                or len(header) != width + 2
            ):
                raise ValueError(f"平行度 CSV 表头或列数不正确: {active}")
            continue
        if len(row) != len(header) or not row[0] or row[1] != robot_sn:
            raise ValueError(f"平行度 CSV 数据列数、时间或 Robot SN 不正确: {active}")
        if row[-1].upper() not in {"PASS", "FAIL"}:
            raise ValueError(f"平行度 CSV 缺少有效 RESULT_STATUS: {active}")
        try:
            measurements = [float(value) for value in row[2:-1]]
        except ValueError as exc:
            raise ValueError(f"平行度 CSV 包含空白或无效测量值: {active}") from exc
        if not all(math.isfinite(value) for value in measurements):
            raise ValueError(f"平行度 CSV 包含无效测量值: {active}")
        sections[active].append([robot_sn, *measurements])
    missing = [name for name in PARALLELISM_TARGETS if not sections.get(name)]
    if missing:
        raise ValueError(f"平行度 CSV 缺少测试数据: {', '.join(missing)}")
    return sections


def upload_parallelism_results(
    uploader, spreadsheet_id: str, sections: dict[str, list[list]],
    *, last_row_range: str = "F:I",
) -> None:
    """Keep append positions in the upload checkpoint so retries reuse their rows."""
    if not spreadsheet_id:
        raise ValueError("请先在数据上传设置中配置平行度测试总表链接 ID")
    with _APPEND_LOCK:
        checkpoint = uploader.get_upload_checkpoint().get("parallelism_upload") or {}
        if checkpoint and checkpoint.get("spreadsheet_id") != spreadsheet_id:
            raise ValueError("平行度测试总表配置已改变，请恢复原 ID 后重试此上传任务")
        if checkpoint.get("complete"):
            return
        values_api = uploader.gdrive.sheet_service_client.spreadsheets().values()
        writes = checkpoint.get("writes")
        if writes is None:
            writes = []
            for name, (sheet, start, end, _) in PARALLELISM_TARGETS.items():
                # Use the same configured empty-row search and destination
                # protection as Unit Tracker, including the row 11 start.
                check_range = uploader.tracker_check_range(last_row_range, start, end)
                first_row = uploader.get_first_blank_tracker_row(
                    spreadsheet_id, sheet, check_range,
                    required_rows=len(sections[name]),
                )
                if first_row is None:
                    raise RuntimeError(f"无法定位平行度测试总表空行: {sheet}")
                final_row = first_row + len(sections[name]) - 1
                if not uploader.ensure_tracker_row_capacity(spreadsheet_id, sheet, final_row):
                    raise RuntimeError(f"无法扩展平行度测试总表行数: {sheet}")
                writes.append({
                    "range": f"{uploader.quote_sheet_name(sheet)}!{start}{first_row}:{end}{final_row}",
                    "values": sections[name],
                })
            checkpoint = {"spreadsheet_id": spreadsheet_id, "writes": writes, "complete": False}
            uploader.report_progress("parallelism", "正在写入平行度测试总表", {"parallelism_upload": checkpoint})
        else:
            # A timeout may follow a successful remote write. Only retry empty or
            # identical cells; never overwrite a row now occupied by another upload.
            for write in writes:
                actual = values_api.get(
                    spreadsheetId=spreadsheet_id,
                    range=write["range"],
                    valueRenderOption="FORMULA",
                ).execute().get("values", [])
                for row_index, row in enumerate(actual):
                    for column_index, value in enumerate(row):
                        expected = write["values"][row_index][column_index]
                        if value not in (None, "") and value != expected:
                            raise RuntimeError(f"平行度测试总表重试位置已被修改: {write['range']}")
        values_api.batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"valueInputOption": "RAW", "data": writes},
        ).execute()
        uploader.report_progress(
            "parallelism", "平行度测试总表写入完成",
            {"parallelism_upload": {**checkpoint, "complete": True}},
        )
