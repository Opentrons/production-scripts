from __future__ import annotations

import io
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pydantic import BaseModel

from google_driver import GoogleDriveFile, GoogleDriver, GoogleDriverError, GoogleSheetData
from settings import (
    SOP_MASTER_SHEET_GID,
    SOP_MASTER_SPREADSHEET_ID,
    SOP_PDF_MAX_BYTES,
    SOP_PDF_MAX_TEXT_CHARS,
)
from sop.bom_analyzer import (
    analyze_bom_pages,
    analyze_part_references,
    classify_sop_page,
    extract_material_lines,
    SopPageCategory,
)
from sop.models import (
    SopCatalogEntry,
    SopBomMaterial,
    SopMasterSheetResponse,
    SopPartReference,
    SopPdfAnalysisResponse,
    SopPdfPage,
    utc_now,
)
from llm.service import choose_material_name, llm_service


class SopAnalysisError(RuntimeError):
    pass


def _merge_bom_materials(
    local_materials: list[SopBomMaterial],
    ai_materials: list[SopBomMaterial],
) -> list[SopBomMaterial]:
    merged = {item.part_number.strip().upper(): item.model_copy(deep=True) for item in local_materials}
    for item in ai_materials:
        key = item.part_number.strip().upper()
        current = merged.get(key)
        if current is None:
            merged[key] = item.model_copy(deep=True)
            continue
        current.name = choose_material_name(current.name, item.name)
        if item.quantity is not None:
            current.quantity = max(current.quantity or 0, item.quantity)
        current.unit = current.unit or item.unit
        current.confidence = min(current.confidence, item.confidence)
        current.pages = list(dict.fromkeys([*current.pages, *item.pages]))
    return list(merged.values())


def _merge_part_references(
    local_references: list[SopPartReference],
    ai_references: list[SopPartReference],
) -> list[SopPartReference]:
    merged = {item.part_number.strip().upper(): item.model_copy(deep=True) for item in local_references}
    for item in ai_references:
        key = item.part_number.strip().upper()
        current = merged.get(key)
        if current is None:
            merged[key] = item.model_copy(deep=True)
            continue
        current.name = choose_material_name(current.name, item.name)
        current.occurrences = max(current.occurrences, item.occurrences)
        current.quantity = max(current.quantity, item.quantity)
        current.pages = list(dict.fromkeys([*current.pages, *item.pages]))
        current.source_lines = list(dict.fromkeys([*current.source_lines, *item.source_lines]))
    return list(merged.values())


class SopService:
    def __init__(
        self,
        google_driver: GoogleDriver,
        spreadsheet_id: str = SOP_MASTER_SPREADSHEET_ID,
        sheet_gid: int = SOP_MASTER_SHEET_GID,
        cache_seconds: int = 0,
        cache_path: Path | None = None,
    ) -> None:
        self.google_driver = google_driver
        self.spreadsheet_id = spreadsheet_id
        self.sheet_gid = sheet_gid
        # Kept for constructor compatibility; cache entries are intentionally
        # persistent and are replaced only by an explicit refresh.
        self.cache_seconds = max(0, cache_seconds)
        self.cache_path = cache_path
        self._cache_lock = threading.RLock()
        self._cache_condition = threading.Condition(self._cache_lock)
        self._cached_master_sheet: SopMasterSheetResponse | None = None
        self._master_refreshing = False
        self._pdf_cache: dict[str, SopPdfAnalysisResponse] = {}
        if self.cache_path is not None:
            self._initialize_disk_cache()

    def get_master_sheet(self, refresh: bool = False) -> SopMasterSheetResponse:
        with self._cache_lock:
            if not refresh:
                if self._cached_master_sheet is not None:
                    return self._cached_master_sheet.model_copy(update={"cached": True})
                disk_cached = self._get_disk_cached(
                    f"master:{self.spreadsheet_id}:{self.sheet_gid}", SopMasterSheetResponse
                )
                if disk_cached is not None:
                    self._cached_master_sheet = disk_cached
                    return disk_cached.model_copy(update={"cached": True})

            if self._master_refreshing:
                while self._master_refreshing:
                    self._cache_condition.wait()
                if self._cached_master_sheet is not None:
                    return self._cached_master_sheet.model_copy(update={"cached": True})

            self._master_refreshing = True

        try:
            response = self._read_master_sheet()
            with self._cache_lock:
                self._cached_master_sheet = response
                self._set_disk_cached(f"master:{self.spreadsheet_id}:{self.sheet_gid}", response)
            return response
        finally:
            with self._cache_lock:
                self._master_refreshing = False
                self._cache_condition.notify_all()

    def _read_master_sheet(self) -> SopMasterSheetResponse:
        sheet_data = self.google_driver.read_sheet_by_gid(self.spreadsheet_id, self.sheet_gid)
        return self._build_master_sheet_response(sheet_data)

    def analyze_pdf(self, file_id_or_url: str, refresh: bool = False) -> SopPdfAnalysisResponse:
        cache_key = self.google_driver.parse_drive_file_id(file_id_or_url) or file_id_or_url
        with self._cache_lock:
            if not refresh:
                cached_pdf = self._pdf_cache.get(cache_key)
                if cached_pdf is not None:
                    return cached_pdf.model_copy(update={"cached": True})
                disk_cached = self._get_disk_cached(f"pdf:{cache_key}", SopPdfAnalysisResponse)
                if disk_cached is not None:
                    self._pdf_cache[cache_key] = disk_cached
                    return disk_cached.model_copy(update={"cached": True})

        metadata, content = self.google_driver.download_file_bytes(file_id_or_url)
        self._validate_pdf(metadata, content)
        try:
            reader = PdfReader(io.BytesIO(content))
            if reader.is_encrypted:
                reader.decrypt("")
        except Exception as exc:
            raise SopAnalysisError(f"PDF 无法解析: {exc}") from exc

        extracted_text_pages: list[tuple[int, str]] = []
        bom_layout_pages: list[tuple[int, str]] = []
        reference_text_pages: list[tuple[int, str]] = []
        page_categories: dict[int, SopPageCategory] = {}
        previous_category: SopPageCategory = "instruction"
        total_text_length = 0
        truncated = False
        for page_number, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text() or ""
            except Exception as exc:
                page_text = f"[页面文本提取失败: {exc}]"
            page_category = classify_sop_page(page_text, previous_category)
            page_categories[page_number] = page_category
            previous_category = page_category
            if page_category == "material_list":
                try:
                    bom_layout_pages.append(
                        (page_number, page.extract_text(extraction_mode="layout") or page_text)
                    )
                except Exception:
                    bom_layout_pages.append((page_number, page_text))
            elif page_category == "instruction":
                reference_text_pages.append((page_number, page_text))

            extracted_text_pages.append((page_number, page_text))

            remaining = SOP_PDF_MAX_TEXT_CHARS - total_text_length
            if remaining <= 0:
                truncated = True
                page_text = ""
            elif len(page_text) > remaining:
                page_text = page_text[:remaining]
                truncated = True
            total_text_length += len(page_text)

        bom_sections, bom_materials = analyze_bom_pages(bom_layout_pages)
        full_text_references = analyze_part_references(reference_text_pages, bom_materials)
        ai_enabled = bool(llm_service.api_key)
        ai_used = False
        ai_fallback = False
        ai_error: str | None = None
        if ai_enabled:
            try:
                ai_material_pages = extract_material_lines(extracted_text_pages)
                ai_materials = llm_service.extract_sop_pages(ai_material_pages)
                if ai_materials:
                    ai_used = True
                    ai_bom_materials = [
                        SopBomMaterial(
                            part_number=item.part_number,
                            name=item.name,
                            quantity=item.quantity,
                            unit=item.unit,
                            pages=[item.page_number] if item.page_number else [],
                            occurrences=1,
                            confidence=item.confidence,
                            source_lines=[],
                        )
                        for item in ai_materials
                    ]
                    bom_materials = _merge_bom_materials(bom_materials, ai_bom_materials)
                    ai_reference_pages = extract_material_lines(reference_text_pages)
                    ai_references = llm_service.extract_sop_pages(ai_reference_pages) if ai_reference_pages else []
                    ai_part_references = [
                        SopPartReference(
                            part_number=item.part_number,
                            name=item.name,
                            occurrences=1,
                            quantity=int(item.quantity or 0),
                            pages=[item.page_number] if item.page_number else [],
                            source_lines=[],
                        )
                        for item in ai_references
                    ]
                    full_text_references = _merge_part_references(full_text_references, ai_part_references)
                else:
                    ai_fallback = True
                    ai_error = "AI 未识别到物料，使用本地规则解析"
            except Exception as exc:
                ai_fallback = True
                ai_error = str(exc)[:500]
        elif not ai_enabled:
            ai_error = "未配置 LLM_API_KEY，使用本地规则解析"
        pages = [
            SopPdfPage(
                page_number=page_number,
                text=text,
                text_length=len(text),
                category=page_categories.get(page_number, "instruction"),
            )
            for page_number, text in extract_material_lines(extracted_text_pages)
        ]
        pdf_metadata = {
            str(key).lstrip("/"): str(value)
            for key, value in (reader.metadata or {}).items()
            if value is not None
        }
        response = SopPdfAnalysisResponse(
            file_id=metadata.id,
            filename=metadata.name,
            mime_type=metadata.mime_type,
            size=len(content),
            modified_time=metadata.modified_time,
            page_count=len(reader.pages),
            text_length=total_text_length,
            text_truncated=truncated,
            metadata=pdf_metadata,
            pages=pages,
            bom_detected=bool(bom_sections or bom_materials),
            bom_material_count=len(bom_materials),
            bom_occurrence_count=(
                len(bom_materials)
                if ai_used
                else sum(len(section.materials) for section in bom_sections)
            ),
            bom_sections=bom_sections,
            bom_materials=bom_materials,
            full_text_material_count=len(full_text_references),
            full_text_occurrence_count=sum(item.occurrences for item in full_text_references),
            full_text_references=full_text_references,
            ai_enabled=ai_enabled,
            ai_used=ai_used,
            ai_fallback=ai_fallback,
            ai_error=ai_error,
            analyzed_at=utc_now(),
        )
        with self._cache_lock:
            self._pdf_cache[cache_key] = response
            self._set_disk_cached(f"pdf:{cache_key}", response)
        return response

    def _initialize_disk_cache(self) -> None:
        assert self.cache_path is not None
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.cache_path, timeout=10) as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sop_cache (
                    cache_key TEXT PRIMARY KEY,
                    updated_at REAL NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )

    def _get_disk_cached(self, key: str, model_type: type[BaseModel]) -> Any | None:
        if self.cache_path is None:
            return None
        with self._cache_lock, sqlite3.connect(self.cache_path, timeout=10) as connection:
            row = connection.execute(
                "SELECT payload FROM sop_cache WHERE cache_key = ?", (key,)
            ).fetchone()
        if row is None:
            return None
        try:
            return model_type.model_validate_json(row[0])
        except ValueError:
            with self._cache_lock, sqlite3.connect(self.cache_path, timeout=10) as connection:
                connection.execute("DELETE FROM sop_cache WHERE cache_key = ?", (key,))
            return None

    def _set_disk_cached(self, key: str, value: BaseModel) -> None:
        if self.cache_path is None:
            return
        with self._cache_lock, sqlite3.connect(self.cache_path, timeout=10) as connection:
            connection.execute(
                """
                INSERT INTO sop_cache (cache_key, updated_at, payload) VALUES (?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    updated_at = excluded.updated_at,
                    payload = excluded.payload
                """,
                (key, time.time(), value.model_dump_json()),
            )

    def _build_master_sheet_response(self, sheet_data: GoogleSheetData) -> SopMasterSheetResponse:
        if not sheet_data.cells:
            return SopMasterSheetResponse(
                spreadsheet_id=self.spreadsheet_id,
                sheet_gid=self.sheet_gid,
                sheet_title=sheet_data.title,
                source_url=self._source_url(),
            )

        headers = [cell.value.strip() for cell in sheet_data.cells[0]]
        entries: list[SopCatalogEntry] = []
        current_project = ""
        status_counts: dict[str, int] = {}

        for row_number, row in enumerate(sheet_data.cells[1:], start=2):
            values = [cell.value.strip() for cell in row]
            values.extend([""] * max(0, 6 - len(values)))
            if not any(values):
                continue

            if values[0]:
                current_project = values[0]
            link_cell = row[3] if len(row) > 3 else None
            link_url = link_cell.hyperlink if link_cell else None
            drive_file_id = self.google_driver.parse_drive_file_id(link_url or "")
            status = values[4]
            if status:
                status_counts[status] = status_counts.get(status, 0) + 1
            entries.append(
                SopCatalogEntry(
                    row_number=row_number,
                    project=current_project,
                    process=values[1],
                    issue_date=values[2],
                    link_label=values[3],
                    link_url=link_url,
                    drive_file_id=drive_file_id,
                    status=status,
                    note=values[5],
                    raw_values=values,
                )
            )

        return SopMasterSheetResponse(
            spreadsheet_id=self.spreadsheet_id,
            sheet_gid=self.sheet_gid,
            sheet_title=sheet_data.title,
            source_url=self._source_url(),
            headers=headers,
            total_rows=len(entries),
            linked_file_count=sum(1 for entry in entries if entry.drive_file_id),
            status_counts=status_counts,
            entries=entries,
            fetched_at=utc_now(),
        )

    def _validate_pdf(self, metadata: GoogleDriveFile, content: bytes) -> None:
        if len(content) > SOP_PDF_MAX_BYTES:
            raise SopAnalysisError(
                f"PDF 大小超过限制: {len(content)} > {SOP_PDF_MAX_BYTES} bytes"
            )
        if not content.startswith(b"%PDF"):
            raise SopAnalysisError(f"Drive 文件不是可识别的 PDF: {metadata.name}")

    def _source_url(self) -> str:
        return (
            f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/edit"
            f"?gid={self.sheet_gid}#gid={self.sheet_gid}"
        )
