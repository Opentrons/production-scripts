from __future__ import annotations

import io
import threading
import time

from pypdf import PdfReader

from google_driver import GoogleDriveFile, GoogleDriver, GoogleDriverError, GoogleSheetData
from settings import (
    SOP_MASTER_CACHE_SECONDS,
    SOP_MASTER_SHEET_GID,
    SOP_MASTER_SPREADSHEET_ID,
    SOP_PDF_CACHE_SECONDS,
    SOP_PDF_MAX_BYTES,
    SOP_PDF_MAX_TEXT_CHARS,
)
from sop.bom_analyzer import analyze_bom_pages, analyze_part_references, is_bom_page
from sop.models import (
    SopCatalogEntry,
    SopMasterSheetResponse,
    SopPdfAnalysisResponse,
    SopPdfPage,
    utc_now,
)


class SopAnalysisError(RuntimeError):
    pass


class SopService:
    def __init__(
        self,
        google_driver: GoogleDriver,
        spreadsheet_id: str = SOP_MASTER_SPREADSHEET_ID,
        sheet_gid: int = SOP_MASTER_SHEET_GID,
        cache_seconds: int = SOP_MASTER_CACHE_SECONDS,
    ) -> None:
        self.google_driver = google_driver
        self.spreadsheet_id = spreadsheet_id
        self.sheet_gid = sheet_gid
        self.cache_seconds = max(0, cache_seconds)
        self._cache_lock = threading.RLock()
        self._cached_master_sheet: SopMasterSheetResponse | None = None
        self._cached_at_monotonic = 0.0
        self._pdf_cache: dict[str, tuple[float, SopPdfAnalysisResponse]] = {}

    def get_master_sheet(self, refresh: bool = False) -> SopMasterSheetResponse:
        with self._cache_lock:
            if not refresh and self._cache_is_valid():
                assert self._cached_master_sheet is not None
                return self._cached_master_sheet.model_copy(update={"cached": True})

        sheet_data = self.google_driver.read_sheet_by_gid(self.spreadsheet_id, self.sheet_gid)
        response = self._build_master_sheet_response(sheet_data)
        with self._cache_lock:
            self._cached_master_sheet = response
            self._cached_at_monotonic = time.monotonic()
        return response

    def analyze_pdf(self, file_id_or_url: str) -> SopPdfAnalysisResponse:
        cache_key = self.google_driver.parse_drive_file_id(file_id_or_url) or file_id_or_url
        with self._cache_lock:
            cached_pdf = self._pdf_cache.get(cache_key)
            if cached_pdf and time.monotonic() - cached_pdf[0] < SOP_PDF_CACHE_SECONDS:
                return cached_pdf[1].model_copy(update={"cached": True})

        metadata, content = self.google_driver.download_file_bytes(file_id_or_url)
        self._validate_pdf(metadata, content)
        try:
            reader = PdfReader(io.BytesIO(content))
            if reader.is_encrypted:
                reader.decrypt("")
        except Exception as exc:
            raise SopAnalysisError(f"PDF 无法解析: {exc}") from exc

        pages: list[SopPdfPage] = []
        bom_layout_pages: list[tuple[int, str]] = []
        reference_text_pages: list[tuple[int, str]] = []
        total_text_length = 0
        truncated = False
        for page_number, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text() or ""
            except Exception as exc:
                page_text = f"[页面文本提取失败: {exc}]"
            if is_bom_page(page_text):
                try:
                    bom_layout_pages.append(
                        (page_number, page.extract_text(extraction_mode="layout") or page_text)
                    )
                except Exception:
                    bom_layout_pages.append((page_number, page_text))
            else:
                reference_text_pages.append((page_number, page_text))

            remaining = SOP_PDF_MAX_TEXT_CHARS - total_text_length
            if remaining <= 0:
                truncated = True
                page_text = ""
            elif len(page_text) > remaining:
                page_text = page_text[:remaining]
                truncated = True
            total_text_length += len(page_text)
            pages.append(
                SopPdfPage(
                    page_number=page_number,
                    text=page_text,
                    text_length=len(page_text),
                )
            )

        bom_sections, bom_materials = analyze_bom_pages(bom_layout_pages)
        full_text_references = analyze_part_references(reference_text_pages, bom_materials)
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
            bom_detected=bool(bom_sections),
            bom_material_count=len(bom_materials),
            bom_occurrence_count=sum(len(section.materials) for section in bom_sections),
            bom_sections=bom_sections,
            bom_materials=bom_materials,
            full_text_material_count=len(full_text_references),
            full_text_occurrence_count=sum(item.occurrences for item in full_text_references),
            full_text_references=full_text_references,
            analyzed_at=utc_now(),
        )
        with self._cache_lock:
            self._pdf_cache[cache_key] = (time.monotonic(), response)
        return response

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

    def _cache_is_valid(self) -> bool:
        return (
            self._cached_master_sheet is not None
            and time.monotonic() - self._cached_at_monotonic < self.cache_seconds
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
