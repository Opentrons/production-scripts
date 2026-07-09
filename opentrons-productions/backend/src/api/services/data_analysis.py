from __future__ import annotations

import asyncio
import csv
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles
from fastapi import HTTPException, UploadFile
import yaml

import settings as setting
from data_analysis.service import analyze_file_paths
from data_analysis.spec_store import list_gravimetric_specs, save_gravimetric_spec
from api.services.test_names import canonical_test_type
from upload_handler.drivers.google_drive import GoogleDriveDriver


ANALYSIS_MAPPING_FILE = os.path.join(setting.PROJECT_ROOT, "configs", "data_analysis_mapping.yaml")


def build_analysis_upload_dir() -> str:
    upload_dir = os.path.join(
        setting.DOWNLOAD_DIR,
        "data_analysis",
        datetime.now().strftime("%Y%m%d_%H%M%S_%f"),
    )
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def sanitize_filename(filename: str | None, index: int) -> str:
    base_name = os.path.basename(filename or "") or f"analysis-{index}.csv"
    base_name = re.sub(r"[^\w.\- %()]+", "-", base_name).strip(".- ")
    if not base_name.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail=f"Only CSV files are supported: {filename or index}")
    return base_name or f"analysis-{index}.csv"


async def save_analysis_uploads(files: list[UploadFile]) -> list[str]:
    if not files:
        raise HTTPException(status_code=400, detail="No CSV files uploaded")

    upload_dir = build_analysis_upload_dir()
    saved_paths: list[str] = []

    for index, upload_file in enumerate(files, start=1):
        filename = sanitize_filename(upload_file.filename, index)
        path = os.path.join(upload_dir, filename)
        async with aiofiles.open(path, "wb") as output_file:
            content = await upload_file.read()
            await output_file.write(content)
        saved_paths.append(path)

    return saved_paths


async def analyze_uploaded_files(files: list[UploadFile]) -> dict:
    paths = await save_analysis_uploads(files)
    return await asyncio.to_thread(analyze_file_paths, paths)


def analyze_paths(file_paths: list[str]) -> dict:
    if not file_paths:
        raise HTTPException(status_code=400, detail="No CSV paths provided")
    return analyze_file_paths(file_paths)


def analyze_online(payload: dict[str, Any]) -> dict:
    product = str(payload.get("product") or "").strip()
    test_type = canonical_test_type(payload.get("test_type"))
    csv_link = str(payload.get("csv_link") or "").strip()
    barcode = str(payload.get("barcode") or "").strip()
    if not product:
        raise HTTPException(status_code=400, detail="product is required")
    if not test_type:
        raise HTTPException(status_code=400, detail="test_type is required")
    if not csv_link:
        raise HTTPException(status_code=400, detail="csv_link is required")

    mapping = resolve_analysis_mapping(product, test_type)
    sheet_name = str(mapping.get("sheet_name") or "").strip()
    if not sheet_name:
        raise HTTPException(status_code=400, detail=f"No sheet_name configured for {product}/{test_type}")

    spreadsheet_id = GoogleDriveDriver.parse_drive_file_id(csv_link)
    if not spreadsheet_id:
        raise HTTPException(status_code=400, detail="Invalid Google Sheet link")

    rows = read_google_sheet_rows(spreadsheet_id, sheet_name, mapping.get("cols") or [])
    if not rows:
        raise HTTPException(status_code=400, detail=f"No data found in sheet {sheet_name}")

    csv_path = save_online_sheet_csv(rows, product=product, test_type=test_type, barcode=barcode, sheet_name=sheet_name)
    result = analyze_file_paths([csv_path])
    result["online_source"] = {
        "product": product,
        "test_type": test_type,
        "barcode": barcode,
        "csv_link": csv_link,
        "sheet_name": sheet_name,
        "cols": mapping.get("cols") or [],
        "csv_path": csv_path,
    }
    return result


def load_analysis_mapping() -> dict[str, Any]:
    mapping_path = Path(ANALYSIS_MAPPING_FILE)
    if not mapping_path.is_file():
        raise HTTPException(status_code=500, detail=f"Analysis mapping not found: {mapping_path}")
    with mapping_path.open("r", encoding="utf-8") as mapping_file:
        return yaml.safe_load(mapping_file) or {}


def resolve_analysis_mapping(product: str, test_type: str) -> dict[str, Any]:
    config = load_analysis_mapping()
    products = config.get("products") or {}
    product_key = match_mapping_key(product, products) or "default"
    product_config = products.get(product_key) or {}
    tests = product_config.get("tests") or {}
    test_key = match_mapping_key(test_type, tests)
    if test_key is None and product_key != "default":
        tests = (products.get("default") or {}).get("tests") or {}
        test_key = match_mapping_key(test_type, tests)
    if test_key is None:
        raise HTTPException(status_code=400, detail=f"No analysis mapping configured for {product}/{test_type}")
    return tests.get(test_key) or {}


def match_mapping_key(value: str, mapping: dict[str, Any]) -> str | None:
    normalized = normalize_mapping_text(value)
    for key in mapping:
        key_text = str(key)
        normalized_key = normalize_mapping_text(key_text)
        if normalized == normalized_key or normalized.startswith(normalized_key) or normalized_key in normalized:
            return key_text
    return None


def normalize_mapping_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def read_google_sheet_rows(spreadsheet_id: str, sheet_name: str, cols: list[str]) -> list[list[Any]]:
    driver = GoogleDriveDriver()
    if driver.sheet_service_client is None:
        raise HTTPException(status_code=500, detail="Google Sheet service is unavailable")
    range_name = build_sheet_range(sheet_name, cols)
    result = driver.sheet_service_client.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        majorDimension="ROWS",
    ).execute()
    return result.get("values", [])


def build_sheet_range(sheet_name: str, cols: list[str]) -> str:
    quoted_sheet_name = quote_sheet_name(sheet_name)
    normalized_cols = [str(col).strip().upper() for col in cols if str(col).strip()]
    if not normalized_cols:
        return quoted_sheet_name
    return f"{quoted_sheet_name}!{normalized_cols[0]}:{normalized_cols[-1]}"


def quote_sheet_name(sheet_name: str) -> str:
    escaped = sheet_name.replace("'", "''")
    return f"'{escaped}'"


def save_online_sheet_csv(rows: list[list[Any]], *, product: str, test_type: str, barcode: str, sheet_name: str) -> str:
    upload_dir = build_analysis_upload_dir()
    file_name = sanitize_filename(
        f"{barcode or product}-{test_type}-{sheet_name}.csv",
        1,
    )
    path = os.path.join(upload_dir, file_name)
    max_columns = max((len(row) for row in rows), default=0)
    with open(path, "w", newline="", encoding="utf-8") as output_file:
        writer = csv.writer(output_file)
        for row in rows:
            writer.writerow(list(row) + [""] * (max_columns - len(row)))
    return path


def get_specs() -> dict:
    return list_gravimetric_specs()


def update_gravimetric_spec(payload: dict) -> dict:
    try:
        return save_gravimetric_spec(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
