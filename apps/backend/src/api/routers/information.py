from __future__ import annotations

import asyncio
import json
import re
import sqlite3
import threading
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qs, urlencode, urlparse
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from api.models import InformationFile, InformationFilesResponse
from core.config import INFORMATION_CACHE_PATH, INFORMATION_REFRESH_SECONDS
from core.google import GoogleDriveFile, GoogleDriver, GoogleDriverError
from core.logging import get_logger


router = APIRouter(prefix="/information", tags=["information"])
logger = get_logger(__name__)

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
NUMBER_LABELS = (
    "编号",
    "ECN编号",
    "ECN单号",
    "联络编号",
    "联络函编号",
    "工程变更编号",
    "ECN No.",
)
SUBJECT_LABELS = ("主题", "标题", "变更主题", "联络函主题", "Subject")
PRODUCT_MODEL_LABELS = ("产品型号", "产品机型", "Product number", "Product model")
DATE_LABELS = (
    "生效日期",
    "下发日期",
    "下发时间",
    "发布日期",
    "发布时间",
    "发行日期",
    "发出日期",
    "Send Date",
    "Effective Date",
)
ALL_FIELD_LABELS = NUMBER_LABELS + SUBJECT_LABELS + PRODUCT_MODEL_LABELS + DATE_LABELS
DIRECT_SHEET_PATH_PATTERN = re.compile(r"^/spreadsheets/d/([A-Za-z0-9_-]+)/edit$")
EMPTY_FIELD_VALUES = {"", "-", "/", "n/a", "na", "none", "null", "无", "不适用"}


class InformationDataError(GoogleDriverError):
    pass


def _clean_cell(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


@lru_cache(maxsize=None)
def _normalized_labels(labels: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(re.sub(r"\s+", "", label).rstrip("：:") for label in labels)


def _is_label_cell(cell: str, labels: tuple[str, ...]) -> bool:
    compact_value = re.sub(r"\s+", "", _clean_cell(cell)).rstrip("：:")
    normalized_labels = _normalized_labels(labels)
    return any(
        compact_value == label
        or any(
            compact_value == f"{label}{other_label}"
            for other_label in normalized_labels
            if other_label != label
        )
        for label in normalized_labels
    )


def _labeled_value(rows: list[list[str]], labels: tuple[str, ...]) -> str:
    for row_index, row in enumerate(rows):
        for column_index, raw_cell in enumerate(row):
            cell = _clean_cell(raw_cell)
            compact_cell = re.sub(r"\s+", "", cell)
            for label in labels:
                match = re.match(rf"^{re.escape(label)}\s*[:：]\s*(.+)$", cell)
                if match:
                    return _clean_cell(match.group(1))
            if not _is_label_cell(compact_cell, labels):
                continue
            for candidate in row[column_index + 1 :]:
                cleaned = _clean_cell(candidate)
                if cleaned:
                    if _is_label_cell(cleaned, ALL_FIELD_LABELS):
                        break
                    return cleaned
            for next_row in rows[row_index + 1 : row_index + 3]:
                if column_index < len(next_row):
                    cleaned = _clean_cell(next_row[column_index])
                    if cleaned:
                        if _is_label_cell(cleaned, ALL_FIELD_LABELS):
                            break
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
    sheet_gid: int | None = None,
    document_title: str = "",
) -> InformationFile:
    flattened = "\n".join(_clean_cell(cell) for row in sheet_values for cell in row if _clean_cell(cell))
    labeled_number = _labeled_value(sheet_values, NUMBER_LABELS)
    number = _normalize_number(labeled_number, kind, allow_bare=True)
    if not number:
        number = _normalize_number(f"{file.name}\n{flattened}", kind)

    if kind == "ecn":
        subject = _clean_cell(document_title) or Path(file.name).stem.strip()
    else:
        subject = _labeled_value(sheet_values, SUBJECT_LABELS)
        if not subject:
            subject = _clean_cell(file.description)
        if not subject:
            subject = Path(file.name).stem
            subject = NUMBER_PATTERN.sub("", subject, count=1)
            subject = re.sub(r"^[\s\-_:：－—]+", "", subject).strip()
    if not subject:
        subject = file.name

    product_model = _labeled_value(sheet_values, PRODUCT_MODEL_LABELS) if kind == "ecn" else ""

    raw_date = _labeled_value(sheet_values, DATE_LABELS)
    effective_date = _normalize_date(raw_date) if raw_date else ""
    if not effective_date:
        effective_date = str(file.modified_time or file.created_time or "")[:10]

    file_id = file.id
    is_google_sheet = file.mime_type == GOOGLE_SHEET_MIME_TYPE or file.target_mime_type == GOOGLE_SHEET_MIME_TYPE
    if is_google_sheet:
        if sheet_gid is None and file.web_view_link:
            web_view_link = file.web_view_link
        else:
            resource_key = file.target_resource_key or file.resource_key
            if not resource_key and file.web_view_link:
                resource_key = parse_qs(urlparse(file.web_view_link).query).get("resourcekey", [None])[0]
            query: list[tuple[str, str]] = []
            if resource_key:
                query.append(("resourcekey", resource_key))
            if sheet_gid is not None:
                query.append(("gid", str(sheet_gid)))
            suffix = f"?{urlencode(query)}" if query else ""
            fragment = f"#gid={sheet_gid}" if sheet_gid is not None else ""
            web_view_link = f"https://docs.google.com/spreadsheets/d/{file_id}/edit{suffix}{fragment}"
    else:
        web_view_link = file.web_view_link or f"https://drive.google.com/open?id={file_id}"
    return InformationFile(
        id=file_id,
        number=number or "-",
        subject=subject,
        product_model=product_model or None,
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


def _is_google_sheet(file: GoogleDriveFile) -> bool:
    return (
        file.mime_type == GOOGLE_SHEET_MIME_TYPE
        or file.target_mime_type == GOOGLE_SHEET_MIME_TYPE
    )


def _direct_sheet_link_issue(file: InformationFile) -> str:
    parsed = urlparse(file.web_view_link)
    path_match = DIRECT_SHEET_PATH_PATTERN.fullmatch(parsed.path)
    if parsed.scheme != "https" or parsed.netloc != "docs.google.com" or not path_match:
        return "不是 Google Sheet 直接链接"
    if path_match.group(1) != file.id:
        return "链接文件 ID 与列表文件 ID 不一致"
    gid = parse_qs(parsed.query).get("gid", [])
    fragment_gid = parse_qs(parsed.fragment).get("gid", [])
    if len(gid) != 1 or not gid[0].isdigit():
        return "链接缺少有效 gid"
    if fragment_gid != gid:
        return "链接 query gid 与 fragment gid 不一致"
    return ""


def _quality_issues(response: InformationFilesResponse) -> list[str]:
    issues: list[str] = []
    if not response.files:
        issues.append(f"{response.kind}: 当前年度列表为空")
        return issues

    seen_numbers: set[str] = set()
    seen_ids: set[str] = set()
    expected_prefix = "ECN-" if response.kind == "ecn" else "ENG-"
    for file in response.files:
        if not file.number.startswith(expected_prefix):
            issues.append(f"{file.number}: 编号格式错误")
        if file.number in seen_numbers:
            issues.append(f"{file.number}: 编号重复")
        if file.id in seen_ids:
            issues.append(f"{file.number}: 文件 ID 重复")
        seen_numbers.add(file.number)
        seen_ids.add(file.id)

        subject = _clean_cell(file.subject)
        if subject.casefold() in EMPTY_FIELD_VALUES or subject.casefold() == file.number.casefold():
            issues.append(f"{file.number}: 缺少源文件主题")
        if not file.effective_date:
            issues.append(f"{file.number}: 缺少下发或生效日期")
        if response.kind == "ecn":
            product_model = _clean_cell(file.product_model).casefold()
            if product_model in EMPTY_FIELD_VALUES:
                issues.append(f"{file.number}: 缺少产品型号")

        link_issue = _direct_sheet_link_issue(file)
        if link_issue:
            issues.append(f"{file.number}: {link_issue}")
    return issues


def _list_information(
    kind: FolderKind,
    year: int | None = None,
    driver: GoogleDriver | None = None,
) -> InformationFilesResponse:
    folder_id, source_url = FOLDERS[kind]
    selected_year = year or datetime.now(ZoneInfo("Asia/Shanghai")).year
    active_driver = driver or google_driver
    files = active_driver.list_files_in_folder(folder_id)
    serialized: list[InformationFile] = []
    for file in files:
        if not _belongs_to_year(file, selected_year):
            continue
        if not _is_google_sheet(file):
            continue
        sheet_values: list[list[str]] = []
        sheet_gid: int | None = None
        document_title = ""
        try:
            sheet_preview = active_driver.read_spreadsheet_preview(file.id)
            sheet_values = sheet_preview.values
            sheet_gid = sheet_preview.sheet_id
            document_title = sheet_preview.document_title
        except GoogleDriverError as exc:
            filename_number = _normalize_number(file.name, kind)
            if not filename_number:
                continue
            raise InformationDataError(f"{filename_number}: 无法读取源文件: {exc}") from exc
        parsed = _parse_file(kind, file, sheet_values, sheet_gid, document_title)
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


class InformationService:
    def __init__(
        self,
        driver: GoogleDriver,
        cache_path: Path | None = INFORMATION_CACHE_PATH,
        refresh_seconds: int = INFORMATION_REFRESH_SECONDS,
    ) -> None:
        self.driver = driver
        self.cache_path = Path(cache_path) if cache_path is not None else None
        self.refresh_seconds = max(60, int(refresh_seconds))
        self._condition = threading.Condition(threading.RLock())
        self._driver_lock = threading.Lock()
        self._refreshing: set[FolderKind] = set()
        self._cache: dict[FolderKind, InformationFilesResponse] = {}
        if self.cache_path is not None:
            self._initialize_disk_cache()

    def get_files(
        self,
        kind: FolderKind,
        *,
        refresh: bool = False,
    ) -> InformationFilesResponse:
        with self._condition:
            cached = self._get_cached_locked(kind)
            if not refresh and cached is not None and self._is_fresh(cached):
                return cached.model_copy(update={"cached": True, "error": None})

            if kind in self._refreshing:
                while kind in self._refreshing:
                    self._condition.wait()
                latest = self._get_cached_locked(kind)
                if latest is not None:
                    return latest.model_copy(update={"cached": True})
            self._refreshing.add(kind)

        try:
            refreshed_at = datetime.now(timezone.utc)
            with self._driver_lock:
                live_response = _list_information(kind, driver=self.driver)
            response = live_response.model_copy(
                update={
                    "refreshed_at": refreshed_at,
                    "cached": False,
                    "quality_checked": True,
                    "error": None,
                }
            )
            issues = _quality_issues(response)
            if issues:
                raise InformationDataError("全量数据 QA 未通过: " + "; ".join(issues))
            with self._condition:
                self._cache[kind] = response
                self._write_disk_cache_locked(kind, response)
            logger.info(
                "Information refresh passed QA: kind=%s year=%s total=%s",
                kind,
                response.year,
                response.total,
            )
            return response
        except Exception as exc:
            with self._condition:
                fallback = self._get_cached_locked(kind)
            if fallback is not None:
                logger.exception(
                    "Information refresh failed; serving last QA-passed cache: kind=%s",
                    kind,
                )
                return fallback.model_copy(
                    update={"cached": True, "error": f"本次刷新失败，已保留上次完整数据: {exc}"}
                )
            raise
        finally:
            with self._condition:
                self._refreshing.discard(kind)
                self._condition.notify_all()

    def refresh_all(self) -> dict[FolderKind, InformationFilesResponse]:
        responses: dict[FolderKind, InformationFilesResponse] = {}
        errors: list[str] = []
        for kind in ("ecn", "contact"):
            try:
                response = self.get_files(kind, refresh=True)
                responses[kind] = response
                if response.error:
                    errors.append(f"{kind}: {response.error}")
            except Exception as exc:
                errors.append(f"{kind}: {exc}")
        if errors:
            raise InformationDataError("; ".join(errors))
        return responses

    def _is_fresh(self, response: InformationFilesResponse) -> bool:
        if response.refreshed_at is None:
            return False
        if response.year != datetime.now(ZoneInfo("Asia/Shanghai")).year:
            return False
        refreshed_at = response.refreshed_at
        if refreshed_at.tzinfo is None:
            refreshed_at = refreshed_at.replace(tzinfo=timezone.utc)
        age_seconds = (datetime.now(timezone.utc) - refreshed_at).total_seconds()
        return age_seconds < self.refresh_seconds

    def _initialize_disk_cache(self) -> None:
        assert self.cache_path is not None
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.cache_path, timeout=10) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS information_cache (
                    kind TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                )
                """
            )

    def _get_cached_locked(self, kind: FolderKind) -> InformationFilesResponse | None:
        cached = self._cache.get(kind)
        if cached is not None or self.cache_path is None:
            return cached
        try:
            with sqlite3.connect(self.cache_path, timeout=10) as connection:
                row = connection.execute(
                    "SELECT payload FROM information_cache WHERE kind = ?",
                    (kind,),
                ).fetchone()
            if row is None:
                return None
            cached = InformationFilesResponse.model_validate(json.loads(str(row[0])))
            if _quality_issues(cached):
                logger.error("Discarding invalid information cache: kind=%s", kind)
                return None
            cached = cached.model_copy(update={"quality_checked": True})
            self._cache[kind] = cached
            return cached
        except (OSError, sqlite3.Error, ValueError, TypeError):
            logger.exception("Failed to read information cache: kind=%s", kind)
            return None

    def _write_disk_cache_locked(
        self,
        kind: FolderKind,
        response: InformationFilesResponse,
    ) -> None:
        if self.cache_path is None:
            return
        with sqlite3.connect(self.cache_path, timeout=10) as connection:
            connection.execute(
                """
                INSERT INTO information_cache (kind, payload) VALUES (?, ?)
                ON CONFLICT(kind) DO UPDATE SET payload = excluded.payload
                """,
                (kind, response.model_dump_json()),
            )


information_service = InformationService(google_driver)
_information_scheduler_task: asyncio.Task[None] | None = None


async def _information_refresh_scheduler() -> None:
    while True:
        try:
            await asyncio.to_thread(information_service.refresh_all)
        except Exception:
            logger.exception("Scheduled information refresh failed")
        await asyncio.sleep(INFORMATION_REFRESH_SECONDS)


def start_information_refresh_scheduler() -> None:
    global _information_scheduler_task
    if _information_scheduler_task is not None and not _information_scheduler_task.done():
        return
    _information_scheduler_task = asyncio.create_task(
        _information_refresh_scheduler(),
        name="information-refresh-scheduler",
    )
    logger.info(
        "Information refresh scheduler started, interval=%ss",
        INFORMATION_REFRESH_SECONDS,
    )


def stop_information_refresh_scheduler() -> None:
    global _information_scheduler_task
    if _information_scheduler_task is not None:
        _information_scheduler_task.cancel()
        _information_scheduler_task = None


@router.get("/{kind}", response_model=InformationFilesResponse)
async def list_information(
    kind: FolderKind,
    refresh: bool = Query(default=False),
):
    try:
        return await run_in_threadpool(
            information_service.get_files,
            kind,
            refresh=refresh,
        )
    except GoogleDriverError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"读取 Google Drive 信息失败: {exc}") from exc
