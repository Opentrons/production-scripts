from __future__ import annotations

import re
from typing import Any

from modules.uploads.handler.drivers.google_drive import GoogleDriveDriver


SPREADSHEET_ID_PATTERN = re.compile(r"/spreadsheets/d/([a-zA-Z0-9_-]+)")


def _spreadsheet_id(value: str) -> str:
    normalized = str(value or "").strip()
    match = SPREADSHEET_ID_PATTERN.search(normalized)
    spreadsheet_id = match.group(1) if match else normalized
    if not re.fullmatch(r"[a-zA-Z0-9_-]{10,}", spreadsheet_id):
        raise ValueError("Google Sheet ID 或 URL 无效")
    return spreadsheet_id


def _driver() -> GoogleDriveDriver:
    driver = GoogleDriveDriver()
    if driver.sheet_service_client is None:
        raise RuntimeError("Google Sheets 服务不可用")
    return driver


def _confirmation(confirm: bool, action: str) -> dict[str, Any] | None:
    if confirm:
        return None
    return {
        "status": "confirmation_required",
        "action": action,
        "message": f"该操作会{action}。请向用户确认后，将 confirm 设为 true 再执行。",
    }


def _validate_values(values: list[list[Any]]) -> list[list[Any]]:
    if not isinstance(values, list) or any(not isinstance(row, list) for row in values):
        raise ValueError("values 必须是二维数组")
    if len(values) > 1000:
        raise ValueError("单次最多写入 1000 行")
    cell_count = sum(len(row) for row in values)
    if cell_count > 10000:
        raise ValueError("单次最多写入 10000 个单元格")
    return values


def _range_name(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized or len(normalized) > 300:
        raise ValueError("range_name 不能为空且不能超过 300 字符")
    return normalized


def get_spreadsheet_info(spreadsheet_id: str) -> dict[str, Any]:
    normalized_id = _spreadsheet_id(spreadsheet_id)
    driver = _driver()
    response = driver.sheet_service_client.spreadsheets().get(
        spreadsheetId=normalized_id,
        fields="spreadsheetId,properties(title,locale,timeZone),sheets.properties(sheetId,title,index,sheetType,gridProperties)",
    ).execute()
    return {
        "spreadsheet_id": normalized_id,
        "url": f"https://docs.google.com/spreadsheets/d/{normalized_id}/edit",
        "properties": response.get("properties") or {},
        "sheets": [item.get("properties") or {} for item in response.get("sheets") or []],
    }


def read_sheet_range(
    spreadsheet_id: str,
    range_name: str,
    major_dimension: str = "ROWS",
    max_rows: int = 300,
) -> dict[str, Any]:
    normalized_id = _spreadsheet_id(spreadsheet_id)
    normalized_range = _range_name(range_name)
    dimension = str(major_dimension or "ROWS").upper()
    if dimension not in {"ROWS", "COLUMNS"}:
        raise ValueError("major_dimension 只能是 ROWS 或 COLUMNS")
    row_limit = max(1, min(int(max_rows), 1000))
    driver = _driver()
    response = driver.sheet_service_client.spreadsheets().values().get(
        spreadsheetId=normalized_id,
        range=normalized_range,
        majorDimension=dimension,
    ).execute()
    values = response.get("values") or []
    return {
        "spreadsheet_id": normalized_id,
        "range": response.get("range") or normalized_range,
        "major_dimension": response.get("majorDimension") or dimension,
        "values": values[:row_limit],
        "returned_rows": min(len(values), row_limit),
        "truncated": len(values) > row_limit,
    }


def create_spreadsheet(
    title: str,
    sheet_title: str = "Sheet1",
    folder_id: str = "",
    confirm: bool = False,
) -> dict[str, Any]:
    confirmation = _confirmation(confirm, f"新建 Google 表格《{str(title).strip()}》")
    if confirmation:
        return confirmation
    normalized_title = str(title or "").strip()
    normalized_sheet_title = str(sheet_title or "Sheet1").strip()
    if not normalized_title:
        raise ValueError("表格标题不能为空")
    driver = _driver()
    response = driver.sheet_service_client.spreadsheets().create(
        body={
            "properties": {"title": normalized_title},
            "sheets": [{"properties": {"title": normalized_sheet_title}}],
        },
        fields="spreadsheetId,spreadsheetUrl,properties.title,sheets.properties",
    ).execute()
    spreadsheet_id = response["spreadsheetId"]
    normalized_folder_id = str(folder_id or "").strip()
    if normalized_folder_id:
        metadata = driver.google_service.files().get(
            fileId=spreadsheet_id,
            fields="parents",
        ).execute()
        parents = ",".join(metadata.get("parents") or [])
        move_arguments: dict[str, Any] = {
            "fileId": spreadsheet_id,
            "addParents": normalized_folder_id,
            "fields": "id,parents",
        }
        if parents:
            move_arguments["removeParents"] = parents
        driver.google_service.files().update(
            **move_arguments,
        ).execute()
    return {
        "status": "created",
        "spreadsheet_id": spreadsheet_id,
        "url": response.get("spreadsheetUrl") or f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit",
        "title": normalized_title,
        "sheet_title": normalized_sheet_title,
        "folder_id": normalized_folder_id or None,
    }


def add_sheet(spreadsheet_id: str, title: str, confirm: bool = False) -> dict[str, Any]:
    normalized_id = _spreadsheet_id(spreadsheet_id)
    normalized_title = str(title or "").strip()
    confirmation = _confirmation(confirm, f"在表格 {normalized_id} 中新增工作表《{normalized_title}》")
    if confirmation:
        return confirmation
    if not normalized_title:
        raise ValueError("工作表名称不能为空")
    driver = _driver()
    response = driver.sheet_service_client.spreadsheets().batchUpdate(
        spreadsheetId=normalized_id,
        body={"requests": [{"addSheet": {"properties": {"title": normalized_title}}}]},
    ).execute()
    properties = ((response.get("replies") or [{}])[0].get("addSheet") or {}).get("properties") or {}
    return {"status": "created", "spreadsheet_id": normalized_id, "sheet": properties}


def update_sheet_range(
    spreadsheet_id: str,
    range_name: str,
    values: list[list[Any]],
    value_input_option: str = "USER_ENTERED",
    confirm: bool = False,
) -> dict[str, Any]:
    normalized_id = _spreadsheet_id(spreadsheet_id)
    normalized_range = _range_name(range_name)
    confirmation = _confirmation(confirm, f"更新表格 {normalized_id} 的区域 {normalized_range}")
    if confirmation:
        return confirmation
    normalized_values = _validate_values(values)
    option = str(value_input_option or "USER_ENTERED").upper()
    if option not in {"RAW", "USER_ENTERED"}:
        raise ValueError("value_input_option 只能是 RAW 或 USER_ENTERED")
    driver = _driver()
    response = driver.sheet_service_client.spreadsheets().values().update(
        spreadsheetId=normalized_id,
        range=normalized_range,
        valueInputOption=option,
        body={"values": normalized_values},
    ).execute()
    return {"status": "updated", **response}


def append_sheet_rows(
    spreadsheet_id: str,
    range_name: str,
    values: list[list[Any]],
    value_input_option: str = "USER_ENTERED",
    confirm: bool = False,
) -> dict[str, Any]:
    normalized_id = _spreadsheet_id(spreadsheet_id)
    normalized_range = _range_name(range_name)
    confirmation = _confirmation(confirm, f"向表格 {normalized_id} 的 {normalized_range} 追加数据")
    if confirmation:
        return confirmation
    normalized_values = _validate_values(values)
    option = str(value_input_option or "USER_ENTERED").upper()
    if option not in {"RAW", "USER_ENTERED"}:
        raise ValueError("value_input_option 只能是 RAW 或 USER_ENTERED")
    driver = _driver()
    response = driver.sheet_service_client.spreadsheets().values().append(
        spreadsheetId=normalized_id,
        range=normalized_range,
        valueInputOption=option,
        insertDataOption="INSERT_ROWS",
        body={"values": normalized_values},
    ).execute()
    return {"status": "appended", **response}


def clear_sheet_range(spreadsheet_id: str, range_name: str, confirm: bool = False) -> dict[str, Any]:
    normalized_id = _spreadsheet_id(spreadsheet_id)
    normalized_range = _range_name(range_name)
    confirmation = _confirmation(confirm, f"清空表格 {normalized_id} 的区域 {normalized_range}")
    if confirmation:
        return confirmation
    driver = _driver()
    response = driver.sheet_service_client.spreadsheets().values().clear(
        spreadsheetId=normalized_id,
        range=normalized_range,
        body={},
    ).execute()
    return {"status": "cleared", **response}


def copy_sheet(
    source_spreadsheet_id: str,
    sheet_id: int,
    destination_spreadsheet_id: str,
    confirm: bool = False,
) -> dict[str, Any]:
    source_id = _spreadsheet_id(source_spreadsheet_id)
    destination_id = _spreadsheet_id(destination_spreadsheet_id)
    confirmation = _confirmation(confirm, f"复制工作表 {sheet_id} 到表格 {destination_id}")
    if confirmation:
        return confirmation
    driver = _driver()
    response = driver.sheet_service_client.spreadsheets().sheets().copyTo(
        spreadsheetId=source_id,
        sheetId=int(sheet_id),
        body={"destinationSpreadsheetId": destination_id},
    ).execute()
    return {"status": "copied", "source_spreadsheet_id": source_id, "destination_spreadsheet_id": destination_id, "sheet": response}
