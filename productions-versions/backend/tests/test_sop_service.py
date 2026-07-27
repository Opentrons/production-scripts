from __future__ import annotations

import io
import threading
import time

from pypdf import PdfWriter

from google_driver import GoogleDriveFile, GoogleSheetCell, GoogleSheetData
from sop.service import SopService


class FakeGoogleDriver:
    def __init__(self) -> None:
        self.sheet_read_count = 0

    def read_sheet_by_gid(self, spreadsheet_id: str, sheet_gid: int) -> GoogleSheetData:
        self.sheet_read_count += 1
        return GoogleSheetData(
            spreadsheet_id=spreadsheet_id,
            sheet_id=sheet_gid,
            title="All Project SOP",
            cells=[
                [
                    GoogleSheetCell("All project SOP"),
                    GoogleSheetCell("Process"),
                    GoogleSheetCell("SOP Issue Date"),
                    GoogleSheetCell("Link"),
                    GoogleSheetCell("Status"),
                    GoogleSheetCell("Note"),
                ],
                [
                    GoogleSheetCell("Flex Robot"),
                    GoogleSheetCell("Assembly"),
                    GoogleSheetCell("20260331"),
                    GoogleSheetCell(
                        "Link",
                        hyperlink="https://drive.google.com/file/d/1vDVuW4YlbAKDGVohoa3rHHMcF00HUYrL/view",
                    ),
                    GoogleSheetCell("MP"),
                    GoogleSheetCell(""),
                ],
                [
                    GoogleSheetCell(""),
                    GoogleSheetCell("Z stage QC"),
                    GoogleSheetCell("20240724"),
                    GoogleSheetCell(
                        "Link",
                        hyperlink="https://drive.google.com/file/d/1b6EF0VwBQFFK6nfHkTmYLoZceQaIYk-R/view",
                    ),
                    GoogleSheetCell("MP"),
                    GoogleSheetCell(""),
                ],
            ],
        )

    def parse_drive_file_id(self, value: str) -> str | None:
        from google_driver import GoogleDriver

        return GoogleDriver.parse_drive_file_id(value)

    def download_file_bytes(self, _: str) -> tuple[GoogleDriveFile, bytes]:
        output = io.BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        writer.add_metadata({"/Title": "SOP Example"})
        writer.write(output)
        return (
            GoogleDriveFile(
                id="pdf-file-id",
                name="SOP.pdf",
                mime_type="application/pdf",
                size=len(output.getvalue()),
            ),
            output.getvalue(),
        )


def test_master_sheet_normalizes_links_and_merged_project_cells() -> None:
    driver = FakeGoogleDriver()
    service = SopService(driver, spreadsheet_id="sheet-id", sheet_gid=991624078, cache_seconds=300)  # type: ignore[arg-type]

    response = service.get_master_sheet()

    assert response.sheet_title == "All Project SOP"
    assert response.total_rows == 2
    assert response.linked_file_count == 2
    assert response.entries[1].project == "Flex Robot"
    assert response.entries[0].drive_file_id == "1vDVuW4YlbAKDGVohoa3rHHMcF00HUYrL"
    assert response.status_counts == {"MP": 2}

    cached = service.get_master_sheet()
    assert cached.cached is True
    assert driver.sheet_read_count == 1


def test_pdf_analysis_reads_drive_pdf() -> None:
    service = SopService(FakeGoogleDriver(), spreadsheet_id="sheet-id", sheet_gid=1)  # type: ignore[arg-type]

    response = service.analyze_pdf("pdf-file-id")

    assert response.filename == "SOP.pdf"
    assert response.page_count == 1
    assert response.metadata["Title"] == "SOP Example"


def test_concurrent_master_sheet_requests_share_one_google_read() -> None:
    driver = FakeGoogleDriver()
    original_read = driver.read_sheet_by_gid

    def delayed_read(spreadsheet_id: str, sheet_gid: int) -> GoogleSheetData:
        time.sleep(0.05)
        return original_read(spreadsheet_id, sheet_gid)

    driver.read_sheet_by_gid = delayed_read  # type: ignore[method-assign]
    service = SopService(driver, spreadsheet_id="sheet-id", sheet_gid=1, cache_seconds=300)  # type: ignore[arg-type]
    results = []
    threads = [threading.Thread(target=lambda: results.append(service.get_master_sheet())) for _ in range(4)]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(results) == 4
    assert driver.sheet_read_count == 1


def test_refresh_returns_cached_sheet_while_background_update_runs() -> None:
    driver = FakeGoogleDriver()
    service = SopService(driver, spreadsheet_id="sheet-id", sheet_gid=1, cache_seconds=300)  # type: ignore[arg-type]
    service.get_master_sheet()

    refreshed = service.get_master_sheet(refresh=True)

    assert refreshed.cached is True
    assert refreshed.total_rows == 2
