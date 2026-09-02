from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from api.models import InformationFile, InformationFilesResponse
from core.google import GoogleDriveFile, GoogleDriver, GoogleDriverError


router = APIRouter(prefix="/information", tags=["information"])

FolderKind = Literal["ecn", "contact"]

FOLDERS: dict[str, tuple[str, str]] = {
    "ecn": (
        "1cAlMjAWMnk47cvvxSPEtG4_xn6O3xmMB",
        "https://drive.google.com/drive/folders/1cAlMjAWMnk47cvvxSPEtG4_xn6O3xmMB",
    ),
    "contact": (
        "1rC0Q2FtayNKkO3gY4_39CuaQdYA_wVtF",
        "https://drive.google.com/drive/folders/1rC0Q2FtayNKkO3gY4_39CuaQdYA_wVtF",
    ),
}

google_driver = GoogleDriver()

GOOGLE_SHEET_MIME_TYPE = "application/vnd.google-apps.spreadsheet"
NUMBER_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?:ENG|ECN)[\s\-_－—]*\d{3,}(?:[\-_－—]\d+)*",
    re.IGNORECASE,
)
NUMBER_PATTERNS: dict[str, re.Pattern[str]] = {
    "ecn": re.compile(r"(?<![A-Za-z0-9])ECN[\s\-_－—]*\d{3,}(?:[\-_－—]\d+)*", re.IGNORECASE),
    "contact": re.compile(r"(?<![A-Za-z0-9])ENG[\s\-_－—]*\d{3,}(?:[\-_－—]\d+)*", re.IGNORECASE),
}
DATE_PATTERN = re.compile(r"(20\d{2})\s*[年./-]\s*(\d{1,2})\s*[月./-]\s*(\d{1,2})\s*日?")
US_DATE_PATTERN = re.compile(r"(?<!\d)(\d{1,2})/(\d{1,2})/(20\d{2})(?!\d)")
NUMBER_LABELS = ("编号", "ECN编号", "联络函编号", "工程变更编号")
SUBJECT_LABELS = ("主题", "标题", "变更主题", "联络函主题")
DATE_LABELS = ("生效日期", "下发日期", "下发时间", "发布日期", "发布时间", "发行日期")


def _clean_cell(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _labeled_value(rows: list[list[str]], labels: tuple[str, ...]) -> str:
    normalized_labels = tuple(re.sub(r"\s+", "", label) for label in labels)
    for row_index, row in enumerate(rows):
        for column_index, raw_cell in enumerate(row):
            cell = _clean_cell(raw_cell)
            compact_cell = re.sub(r"\s+", "", cell)
            for label, compact_label in zip(labels, normalized_labels):
                match = re.match(rf"^{re.escape(label)}\s*[:：]\s*(.+)$", cell)
                if match:
                    return _clean_cell(match.group(1))
                if compact_cell.startswith(compact_label) and compact_cell != compact_label:
                    delimiter = re.search(r"[:：]", cell)
                    if delimiter:
                        return _clean_cell(cell[delimiter.end() :])
                    if cell.startswith(label):
                        return _clean_cell(cell[len(label) :])
                if compact_cell.rstrip("：:") != compact_label:
                    continue
                for candidate in row[column_index + 1 :]:
                    cleaned = _clean_cell(candidate)
                    if cleaned:
                        return cleaned
                for next_row in rows[row_index + 1 : row_index + 3]:
                    if column_index < len(next_row):
                        cleaned = _clean_cell(next_row[column_index])
                        if cleaned:
                            return cleaned
    return ""


def _normalize_number(raw_value: str, kind: FolderKind, *, allow_bare: bool = False) -> str:
    match = NUMBER_PATTERNS[kind].search(raw_value)
    if match:
        value = match.group(0).upper()
        value = re.sub(r"[\s_－—-]+", "-", value)
        return value.strip("-")
    if not allow_bare:
        return ""
    digits = re.search(r"(?<!\d)\d{3,}(?:[-_－—]\d+)*(?!\d)", raw_value)
    if not digits:
        return ""
    value = re.sub(r"[_－—]+", "-", digits.group(0))
    prefix = "ENG" if kind == "contact" else "ECN"
    return f"{prefix}-{value}"


def _normalize_date(raw_value: str) -> str:
    value = _clean_cell(raw_value)
    match = DATE_PATTERN.search(value)
    if match:
        year, month, day = (int(part) for part in match.groups())
        return f"{year:04d}-{month:02d}-{day:02d}"
    match = US_DATE_PATTERN.search(value)
    if match:
        month, day, year = (int(part) for part in match.groups())
        return f"{year:04d}-{month:02d}-{day:02d}"
    return value


def _parse_file(
    kind: FolderKind,
    file: GoogleDriveFile,
    sheet_values: list[list[str]],
) -> InformationFile:
    flattened = "\n".join(_clean_cell(cell) for row in sheet_values for cell in row if _clean_cell(cell))
    labeled_number = _labeled_value(sheet_values, NUMBER_LABELS)
    number = _normalize_number(labeled_number, kind, allow_bare=True)
    if not number:
        number = _normalize_number(f"{file.name}\n{flattened}", kind)

    subject = _labeled_value(sheet_values, SUBJECT_LABELS)
    if not subject:
        subject = _clean_cell(file.description)
    if not subject:
        subject = Path(file.name).stem
        subject = NUMBER_PATTERN.sub("", subject, count=1)
        subject = re.sub(r"^[\s\-_:：－—]+", "", subject).strip()
    if not subject:
        subject = file.name

    raw_date = _labeled_value(sheet_values, DATE_LABELS)
    effective_date = _normalize_date(raw_date) if raw_date else ""
    if not effective_date:
        effective_date = str(file.modified_time or file.created_time or "")[:10]

    file_id = file.id
    is_google_sheet = file.mime_type == GOOGLE_SHEET_MIME_TYPE or file.target_mime_type == GOOGLE_SHEET_MIME_TYPE
    if is_google_sheet:
        web_view_link = f"https://docs.google.com/spreadsheets/d/{file_id}/edit"
    else:
        web_view_link = file.web_view_link or f"https://drive.google.com/open?id={file_id}"
    return InformationFile(
        id=file_id,
        number=number or "-",
        subject=subject,
        effective_date=effective_date or None,
        web_view_link=web_view_link,
    )


def _number_sort_key(file: InformationFile) -> tuple[tuple[int, ...], str, str]:
    number_parts = tuple(int(part) for part in re.findall(r"\d+", file.number))
    return number_parts, file.effective_date or "", file.number


def _belongs_to_year(file: GoogleDriveFile, year: int) -> bool:
    for segment in file.parent_path.split(" / "):
        if re.match(rf"^{year}(?:\D|$)", segment.strip()):
            return True
    fallback_date = str(file.modified_time or file.created_time or "")
    return fallback_date.startswith(f"{year}-")


def _list_information(kind: FolderKind, year: int | None = None) -> InformationFilesResponse:
    folder_id, source_url = FOLDERS[kind]
    selected_year = year or datetime.now(timezone.utc).year
    files = google_driver.list_files_in_folder(folder_id)
    serialized: list[InformationFile] = []
    for file in files:
        if not _belongs_to_year(file, selected_year):
            continue
        if file.mime_type == "application/vnd.google-apps.folder":
            continue
        try:
            sheet_values = google_driver.read_spreadsheet_values(file.id)
        except GoogleDriverError:
            sheet_values = []
        parsed = _parse_file(kind, file, sheet_values)
        if parsed.number != "-":
            serialized.append(parsed)
    serialized.sort(key=_number_sort_key, reverse=True)
    return InformationFilesResponse(
        kind=kind,
        year=selected_year,
        source_url=source_url,
        files=serialized,
        total=len(serialized),
    )


@router.get("/{kind}", response_model=InformationFilesResponse)
async def list_information(kind: FolderKind):
    try:
        return await run_in_threadpool(_list_information, kind)
    except GoogleDriverError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"读取 Google Drive 信息失败: {exc}") from exc
