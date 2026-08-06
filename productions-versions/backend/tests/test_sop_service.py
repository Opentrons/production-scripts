from __future__ import annotations

import io
import threading
import time

from pypdf import PdfWriter

from google_driver import GoogleDriveFile, GoogleSheetCell, GoogleSheetData
from llm.models import SopSemanticDecision, SopTextMaterial
from sop.service import SopService, llm_service


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


def test_refresh_fetches_and_replaces_sheet_cache() -> None:
    driver = FakeGoogleDriver()
    service = SopService(driver, spreadsheet_id="sheet-id", sheet_gid=1, cache_seconds=300)  # type: ignore[arg-type]
    service.get_master_sheet()

    refreshed = service.get_master_sheet(refresh=True)

    assert refreshed.cached is False
    assert refreshed.total_rows == 2
    assert driver.sheet_read_count == 2


def test_master_sheet_cache_survives_service_restart(tmp_path) -> None:
    cache_path = tmp_path / "sop-cache.sqlite3"
    first_driver = FakeGoogleDriver()
    first_service = SopService(first_driver, spreadsheet_id="sheet-id", sheet_gid=1, cache_path=cache_path)  # type: ignore[arg-type]
    first_service.get_master_sheet()

    second_driver = FakeGoogleDriver()
    second_service = SopService(second_driver, spreadsheet_id="sheet-id", sheet_gid=1, cache_path=cache_path)  # type: ignore[arg-type]
    cached = second_service.get_master_sheet()

    assert cached.cached is True
    assert second_driver.sheet_read_count == 0


def test_pdf_analysis_cache_survives_service_restart(tmp_path) -> None:
    cache_path = tmp_path / "sop-cache.sqlite3"
    first_driver = FakeGoogleDriver()
    first_service = SopService(first_driver, cache_path=cache_path)  # type: ignore[arg-type]
    first_service.analyze_pdf("pdf-file-id")

    second_driver = FakeGoogleDriver()
    second_service = SopService(second_driver, cache_path=cache_path)  # type: ignore[arg-type]
    cached = second_service.analyze_pdf("pdf-file-id")

    assert cached.cached is True
    assert cached.filename == "SOP.pdf"


def test_quantity_refinement_uses_names_only_for_requested_mismatches(monkeypatch) -> None:
    service = SopService(FakeGoogleDriver(), spreadsheet_id="sheet-id", sheet_gid=1)  # type: ignore[arg-type]
    service._instruction_pages_cache["pdf-file-id"] = [
        (14, "Install 1×242-00052 around the harness"),
        (15, "Use two zip-tie to secure the harness"),
        (20, "Install 1×242-00059 around the cable"),
    ]
    captured: dict[str, object] = {}

    def fake_extract(pages, material_names=None, target_part_numbers=None):
        captured["pages"] = pages
        captured["material_names"] = material_names
        captured["target_part_numbers"] = target_part_numbers
        return [
            SopTextMaterial(
                part_number="242-00052",
                name="扎带/zip-tie",
                quantity=3,
                confidence=0.98,
                quantity_explanation="料号页 1 个，名称页新增 2 个",
                quantity_decisions=[
                    SopSemanticDecision(
                        event_id="E2",
                        page_numbers=[15],
                        action="固定",
                        quantity_delta=2,
                        accumulate=True,
                        evidence="Use two zip-tie",
                    )
                ],
            )
        ]

    monkeypatch.setattr(llm_service, "api_key", "test-key")
    monkeypatch.setattr(llm_service, "extract_sop_semantic_references", fake_extract)

    refined = service.refine_semantic_quantities_with_names(
        "pdf-file-id",
        {
            "242-00052": "扎带/zip-tie",
            "242-00059": "磁环/magnetic ring",
        },
        {"242-00052"},
    )

    assert captured["target_part_numbers"] == {"242-00052"}
    assert len(refined) == 1
    assert refined[0].quantity == 3
    assert refined[0].occurrences == 2
    assert refined[0].pages == [14, 15]
    assert "二次复核" in refined[0].quantity_explanation


def test_quantity_refinement_keeps_first_pass_when_no_name_only_evidence(monkeypatch) -> None:
    service = SopService(FakeGoogleDriver(), spreadsheet_id="sheet-id", sheet_gid=1)  # type: ignore[arg-type]
    service._instruction_pages_cache["pdf-file-id"] = [
        (14, "Install 1×242-00052 around the harness"),
        (15, "Inspect unrelated cable routing"),
    ]

    def unexpected_extract(*args, **kwargs):
        raise AssertionError("semantic refinement should not run without new name evidence")

    monkeypatch.setattr(llm_service, "api_key", "test-key")
    monkeypatch.setattr(llm_service, "extract_sop_semantic_references", unexpected_extract)

    refined = service.refine_semantic_quantities_with_names(
        "pdf-file-id",
        {"242-00052": "扎带/zip-tie"},
        {"242-00052"},
    )

    assert refined == []
