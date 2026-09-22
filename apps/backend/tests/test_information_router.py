import asyncio
import sqlite3
import threading

import pytest

import api.routers.information as information_module
from api.models import InformationFile, InformationFilesResponse
from api.routers.information import (
    InformationService,
    _belongs_to_year,
    _information_refresh_scheduler,
    _number_sort_key,
    _parse_file,
    _quality_issues,
    _select_source_sheet,
)
from core.google import (
    GoogleDriveFile,
    GoogleDriverError,
    GoogleSheetCell,
    GoogleSheetData,
)


class FakeInformationDriver:
    def __init__(self) -> None:
        self.files: dict[str, list[GoogleDriveFile]] = {
            information_module.FOLDERS["ecn"][0]: [],
            information_module.FOLDERS["contact"][0]: [],
        }
        self.sheets: dict[str, GoogleSheetData | list[GoogleSheetData]] = {}
        self.list_error: Exception | None = None
        self.preview_calls: list[str] = []

    def list_files_in_folder(self, folder_id: str) -> list[GoogleDriveFile]:
        if self.list_error is not None:
            raise self.list_error
        return list(self.files[folder_id])

    def read_spreadsheet_previews(self, spreadsheet_id: str) -> list[GoogleSheetData]:
        self.preview_calls.append(spreadsheet_id)
        sheet = self.sheets[spreadsheet_id]
        return sheet if isinstance(sheet, list) else [sheet]


def _sheet(spreadsheet_id: str, gid: int, rows: list[list[str]]) -> GoogleSheetData:
    return GoogleSheetData(
        spreadsheet_id=spreadsheet_id,
        sheet_id=gid,
        title="Sheet1",
        cells=[
            [GoogleSheetCell(value=value) for value in row]
            for row in rows
        ],
    )


def _source_file(file_id: str, name: str, parent_path: str | None = None) -> GoogleDriveFile:
    if parent_path is None:
        parent_path = "2026 ECN" if name.startswith("ECN-") else "2026"
    return GoogleDriveFile(
        id=file_id,
        name=name,
        mime_type="application/vnd.google-apps.spreadsheet",
        modified_time="2026-08-24T08:00:00Z",
        parent_path=parent_path,
    )


def test_parse_contact_letter_fields_from_sheet_values() -> None:
    file = GoogleDriveFile(
        id="sheet-id",
        name="ENG-2026001 联络函",
        mime_type="application/vnd.google-apps.spreadsheet",
        created_time="2026-01-25T08:00:00Z",
        web_view_link="https://docs.google.com/spreadsheets/d/sheet-id/edit?resourcekey=drive-resource-key",
    )

    parsed = _parse_file(
        "contact",
        file,
        [
            ["编号", "ENG-2026001"],
            ["主题", "关于 HS 基板415-00138与导向轮组417-00140/435-00012 配合使用的方法通知"],
            ["生效日期：2026-1-26"],
        ],
    )

    assert parsed.number == "ENG-2026001"
    assert parsed.subject.startswith("关于 HS 基板415-00138")
    assert parsed.product_model is None
    assert parsed.effective_date == "2026-01-26"
    assert parsed.web_view_link == (
        "https://docs.google.com/spreadsheets/d/sheet-id/edit?resourcekey=drive-resource-key"
    )


def test_parse_file_uses_filename_and_created_date_as_fallbacks() -> None:
    file = GoogleDriveFile(
        id="sheet-id",
        name="ECN-2026012 - Heater Shaker bracket update",
        mime_type="application/vnd.google-apps.spreadsheet",
        created_time="2026-03-07T08:00:00Z",
        modified_time="2026-03-09T08:00:00Z",
    )

    parsed = _parse_file("ecn", file, [])

    assert parsed.number == "ECN-2026012"
    assert parsed.subject == "ECN-2026012 - Heater Shaker bracket update"
    assert parsed.effective_date == "2026-03-09"
    assert parsed.web_view_link == "https://docs.google.com/spreadsheets/d/sheet-id/edit"


def test_parse_file_keeps_shortcut_target_resource_key() -> None:
    file = GoogleDriveFile(
        id="shortcut-target-sheet-id",
        name="ECN-0571 Drawing Update",
        mime_type="application/vnd.google-apps.shortcut",
        target_mime_type="application/vnd.google-apps.spreadsheet",
        target_resource_key="shortcut-resource-key",
    )

    parsed = _parse_file("ecn", file, [])

    assert parsed.web_view_link == (
        "https://docs.google.com/spreadsheets/d/shortcut-target-sheet-id/edit"
        "?resourcekey=shortcut-resource-key"
    )


def test_parse_ecn_uses_file_title_product_model_and_sheet_gid() -> None:
    file = GoogleDriveFile(
        id="1jhby4yUmWvMuAyx0UB8adcrXRsvnwFdJiT53l-7FbRo",
        name="ECN-0571",
        mime_type="application/vnd.google-apps.shortcut",
        target_mime_type="application/vnd.google-apps.spreadsheet",
    )

    parsed = _parse_file(
        "ecn",
        file,
        [
            ["产品型号\nProduct number", "", "Heater shaker"],
            ["ECN 单号\nECN No.", "", "ECN-0571"],
            ["发出日期\nSend Date", "", "7/21/2026"],
        ],
        sheet_gid=104681895,
        document_title="ECN-0571 436-00159 Drawing Update",
    )

    assert parsed.number == "ECN-0571"
    assert parsed.subject == "ECN-0571 436-00159 Drawing Update"
    assert parsed.product_model == "Heater shaker"
    assert parsed.effective_date == "2026-07-21"
    assert parsed.web_view_link == (
        "https://docs.google.com/spreadsheets/d/"
        "1jhby4yUmWvMuAyx0UB8adcrXRsvnwFdJiT53l-7FbRo/"
        "edit?gid=104681895#gid=104681895"
    )


def test_parse_ecn_uses_source_product_name_when_model_is_unfilled() -> None:
    parsed = _parse_file(
        "ecn",
        _source_file("sheet-id", "ECN-0561 436-00286 Drawing Update"),
        [
            ["产品型号\nProduct number", "-"],
            ["物料名称\nProduct Name", "FLEX REPLACMENT Z STAGE - FOAM, TOP"],
            ["ECN 单号\nECN No.", "ECN-0561"],
        ],
        sheet_gid=1,
        document_title="ECN-0561 436-00286 Drawing Update",
    )

    assert parsed.product_model == "FLEX REPLACMENT Z STAGE - FOAM, TOP"


def test_parse_ecn_prefers_drive_filename_number_over_sheet_typo() -> None:
    parsed = _parse_file(
        "ecn",
        _source_file("sheet-id", "ECN-0568 999-00241 BOM Update"),
        [
            ["产品型号", "999-00241"],
            ["ECN编号", "ECN-05648"],
        ],
        sheet_gid=1,
        document_title="ECN-0568 999-00241 BOM Update",
    )

    assert parsed.number == "ECN-0568"


def test_parse_contact_letter_reads_subject_beyond_column_z() -> None:
    file = GoogleDriveFile(
        id="1usLK_UEgirWxi7MWm3cI0D_zsUvgZebzgpfiun_Y02s",
        name="ENG-2026013",
        mime_type="application/vnd.google-apps.spreadsheet",
    )
    subject_row = ["主题", *([""] * 35), "关于Stacker图纸变更通知"]

    parsed = _parse_file(
        "contact",
        file,
        [
            ["联络编号", "ENG-2026013"],
            ["生效日期", "2026/8/24"],
            subject_row,
        ],
        sheet_gid=0,
    )

    assert parsed.number == "ENG-2026013"
    assert parsed.subject == "关于Stacker图纸变更通知"
    assert parsed.product_model is None
    assert parsed.effective_date == "2026-08-24"
    assert parsed.web_view_link == (
        "https://docs.google.com/spreadsheets/d/"
        "1usLK_UEgirWxi7MWm3cI0D_zsUvgZebzgpfiun_Y02s/edit?gid=0#gid=0"
    )


@pytest.mark.parametrize(
    ("kind", "required_row", "expected_gid"),
    [
        ("ecn", ["产品型号", "Flex 8-Channel Pipette"], 22),
        ("contact", ["主题", "关于Pipette装配方法变更通知"], 23),
    ],
)
def test_select_source_sheet_scans_past_blank_first_tab(
    kind: str,
    required_row: list[str],
    expected_gid: int,
) -> None:
    previews = [
        _sheet("sheet-id", 1, [["说明", "归档页"]]),
        _sheet("sheet-id", expected_gid, [["编号", "0572"], required_row, ["生效日期", "2026/8/24"]]),
    ]

    selected = _select_source_sheet(kind, previews)  # type: ignore[arg-type]

    assert selected.sheet_id == expected_gid


def test_information_files_sort_by_number_with_latest_first() -> None:
    files = [
        InformationFile(id="1", number="ENG-2026002", subject="Second", web_view_link="https://example.com/1"),
        InformationFile(id="2", number="ENG-2026010", subject="Tenth", web_view_link="https://example.com/2"),
        InformationFile(id="3", number="ENG-2026009", subject="Ninth", web_view_link="https://example.com/3"),
    ]

    files.sort(key=_number_sort_key, reverse=True)

    assert [file.number for file in files] == ["ENG-2026010", "ENG-2026009", "ENG-2026002"]


def test_parse_file_ignores_records_with_the_other_document_prefix() -> None:
    file = GoogleDriveFile(
        id="template-id",
        name="QR-ENG-0000 Contact letter template",
        mime_type="application/vnd.google-apps.spreadsheet",
    )

    parsed = _parse_file("ecn", file, [])

    assert parsed.number == "-"


def test_belongs_to_year_matches_year_folder_names_before_dates() -> None:
    file = GoogleDriveFile(
        id="sheet-id",
        name="ECN-0522",
        mime_type="application/vnd.google-apps.spreadsheet",
        parent_path="2026 ECN / ECN-0522",
        modified_time="2026-01-06T00:00:00Z",
    )

    assert _belongs_to_year(file, 2026)
    assert not _belongs_to_year(file, 2025)

    old_file = file.__class__(
        **{
            **file.__dict__,
            "parent_path": "2025 ECN / ECN-0522",
            "modified_time": "2026-08-24T00:00:00Z",
        }
    )
    assert not _belongs_to_year(old_file, 2026, "ecn")


def test_service_reads_and_qa_checks_every_source_record(tmp_path) -> None:
    driver = FakeInformationDriver()
    ecn_files = [
        _source_file("ecn-sheet-571", "ECN-0571 436-00159 Drawing Update"),
        _source_file("ecn-sheet-572", "ECN-0572 Pipette Drawing Update"),
    ]
    contact_files = [
        _source_file("contact-sheet-13", "ENG-2026013"),
        _source_file("contact-sheet-14", "ENG-2026014"),
    ]
    driver.files[information_module.FOLDERS["ecn"][0]] = ecn_files
    driver.files[information_module.FOLDERS["contact"][0]] = contact_files
    driver.sheets = {
        "ecn-sheet-571": _sheet(
            "ecn-sheet-571",
            104681895,
            [
                ["产品型号\nProduct number", "", "Heater shaker"],
                ["ECN 单号\nECN No.", "", "ECN-0571"],
            ],
        ),
        "ecn-sheet-572": _sheet(
            "ecn-sheet-572",
            22,
            [
                ["产品型号", "Flex 8-Channel Pipette"],
                ["ECN编号", "ECN-0572"],
            ],
        ),
        "contact-sheet-13": _sheet(
            "contact-sheet-13",
            0,
            [["联络编号", "ENG-2026013"], ["主题", "关于Stacker图纸变更通知"]],
        ),
        "contact-sheet-14": _sheet(
            "contact-sheet-14",
            14,
            [["联络编号", "ENG-2026014"], ["主题", "关于Pipette装配方法变更通知"]],
        ),
    }
    service = InformationService(
        driver,  # type: ignore[arg-type]
        cache_path=tmp_path / "information.sqlite3",
    )

    ecn = service.refresh_files("ecn")
    contacts = service.refresh_files("contact")

    assert [item.product_model for item in ecn.files] == [
        "Flex 8-Channel Pipette",
        "Heater shaker",
    ]
    assert [item.subject for item in contacts.files] == [
        "关于Pipette装配方法变更通知",
        "关于Stacker图纸变更通知",
    ]
    assert all(item.id in item.web_view_link for item in [*ecn.files, *contacts.files])
    assert all("?gid=" in item.web_view_link for item in [*ecn.files, *contacts.files])
    assert _quality_issues(ecn) == []
    assert _quality_issues(contacts) == []
    assert ecn.quality_checked is True
    assert contacts.quality_checked is True
    assert driver.preview_calls == [
        "ecn-sheet-571",
        "ecn-sheet-572",
        "contact-sheet-13",
        "contact-sheet-14",
    ]

    driver.preview_calls.clear()
    driver.sheets.clear()
    assert service.refresh_files("ecn").total == 2
    assert service.refresh_files("contact").total == 2
    assert driver.preview_calls == []


def test_quality_gate_rejects_missing_subject_product_model_and_wrong_links() -> None:
    contacts = InformationFilesResponse(
        kind="contact",
        year=2026,
        source_url="https://drive.google.com/folder",
        files=[
            InformationFile(
                id="contact-sheet",
                number="ENG-2026001",
                subject="ENG-2026001",
                effective_date="2026-01-01",
                web_view_link="https://drive.google.com/open?id=contact-sheet",
                source_parent_path="2026",
            )
        ],
    )
    ecn = InformationFilesResponse(
        kind="ecn",
        year=2026,
        source_url="https://drive.google.com/folder",
        files=[
            InformationFile(
                id="ecn-sheet",
                number="ECN-0571",
                subject="ECN-0571 Drawing Update",
                product_model=None,
                effective_date="2026-01-01",
                web_view_link=(
                    "https://docs.google.com/spreadsheets/d/other-sheet/edit?gid=1#gid=1"
                ),
                source_parent_path="2026 ECN",
            )
        ],
    )

    assert _quality_issues(contacts) == [
        "ENG-2026001: 缺少源文件主题",
        "ENG-2026001: 不是 Google Sheet 直接链接",
    ]
    assert _quality_issues(ecn) == [
        "ECN-0571: 缺少产品型号",
        "ECN-0571: 链接文件 ID 与列表文件 ID 不一致",
    ]


def test_forced_refresh_discovers_new_records_and_persists_qa_cache(tmp_path) -> None:
    driver = FakeInformationDriver()
    first = _source_file("contact-sheet-13", "ENG-2026013")
    second = _source_file("contact-sheet-14", "ENG-2026014")
    folder_id = information_module.FOLDERS["contact"][0]
    driver.files[folder_id] = [first]
    driver.sheets["contact-sheet-13"] = _sheet(
        "contact-sheet-13",
        0,
        [["联络编号", "ENG-2026013"], ["主题", "关于Stacker图纸变更通知"]],
    )
    cache_path = tmp_path / "information.sqlite3"
    service = InformationService(driver, cache_path=cache_path)  # type: ignore[arg-type]

    assert service.refresh_files("contact").total == 1
    assert driver.preview_calls == ["contact-sheet-13"]
    with sqlite3.connect(cache_path) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert table_names == {
        "engineering_information_index",
        "engineering_information_progress",
    }

    driver.sheets.pop("contact-sheet-13")
    driver.files[folder_id] = [first, second]
    driver.sheets["contact-sheet-14"] = _sheet(
        "contact-sheet-14",
        14,
        [["联络编号", "ENG-2026014"], ["主题", "关于Pipette装配方法变更通知"]],
    )
    refreshed = service.refresh_files("contact")

    assert refreshed.total == 2
    assert [item.number for item in refreshed.files] == ["ENG-2026014", "ENG-2026013"]
    assert driver.preview_calls == ["contact-sheet-13", "contact-sheet-14"]

    restarted_driver = FakeInformationDriver()
    restarted_driver.files[folder_id] = [first, second]
    restarted = InformationService(
        restarted_driver,  # type: ignore[arg-type]
        cache_path=cache_path,
    )
    persisted = restarted.refresh_files("contact")
    assert persisted.total == 2
    assert restarted_driver.preview_calls == []

    failing_driver = FakeInformationDriver()
    failing_driver.list_error = GoogleDriverError("Drive unavailable")
    restarted = InformationService(
        failing_driver,  # type: ignore[arg-type]
        cache_path=cache_path,
    )
    fallback = restarted.refresh_files("contact")
    assert fallback.total == 2
    assert fallback.cached is True
    assert fallback.quality_checked is True
    assert "已保留上次完整数据" in str(fallback.error)


def test_scan_filters_old_year_root_templates_and_scrap_duplicates(tmp_path) -> None:
    driver = FakeInformationDriver()
    folder_id = information_module.FOLDERS["ecn"][0]
    allowed = _source_file("allowed", "ECN-0576 Update", "2026 ECN / ECN-0576 Update")
    scrap = _source_file("scrap", "ECN-0576 Update Scrap", "2026 ECN / ECN-0576 Update")
    old = _source_file("old", "ECN-0521 Old", "2025 ECN / ECN-0521 Old")
    root_template = _source_file("template", "QR-ENG-0000 工程变更通知单 A3模板", "")
    driver.files[folder_id] = [allowed, scrap, old, root_template]
    driver.sheets["allowed"] = _sheet(
        "allowed",
        1,
        [["产品型号", "Flex"], ["ECN编号", "ECN-0576"]],
    )

    response = InformationService(
        driver,  # type: ignore[arg-type]
        cache_path=tmp_path / "information.sqlite3",
    ).refresh_files("ecn")

    assert response.total == 1
    assert [item.number for item in response.files] == ["ECN-0576"]
    assert driver.preview_calls == ["allowed"]


def test_scan_rejects_duplicate_non_scrap_ecn_numbers(tmp_path) -> None:
    driver = FakeInformationDriver()
    folder_id = information_module.FOLDERS["ecn"][0]
    first = _source_file("first", "ECN-0576 First", "2026 ECN / ECN-0576 First")
    duplicate = _source_file("duplicate", "ECN-0576 Duplicate", "2026 ECN / ECN-0576 Duplicate")
    driver.files[folder_id] = [first, duplicate]
    driver.sheets["first"] = _sheet(
        "first", 1, [["产品型号", "Flex"], ["ECN编号", "ECN-0576"]]
    )
    driver.sheets["duplicate"] = _sheet(
        "duplicate", 2, [["产品型号", "Flex"], ["ECN编号", "ECN-0576"]]
    )

    with pytest.raises(Exception, match="ECN-0576: 编号重复"):
        InformationService(
            driver,  # type: ignore[arg-type]
            cache_path=tmp_path / "information.sqlite3",
        ).refresh_files("ecn")


def test_quality_gate_rejects_wrong_contact_year_and_source_directory() -> None:
    response = InformationFilesResponse(
        kind="contact",
        year=2026,
        source_url="https://drive.google.com/folder",
        files=[
            InformationFile(
                id="contact-sheet",
                number="ENG-2024015",
                subject="关于历史文件",
                effective_date="2026-01-01",
                web_view_link="https://docs.google.com/spreadsheets/d/contact-sheet/edit?gid=0#gid=0",
                source_parent_path="2025",
            )
        ],
    )

    assert _quality_issues(response) == [
        "ENG-2024015: 联络函编号年份与列表年份不一致",
        "ENG-2024015: 来源目录不是 2026 年目录",
    ]


def test_refresh_resumes_from_persisted_record_progress(tmp_path) -> None:
    class FailingPreviewDriver(FakeInformationDriver):
        def __init__(self) -> None:
            super().__init__()
            self.fail_ids: set[str] = set()

        def read_spreadsheet_previews(self, spreadsheet_id: str) -> list[GoogleSheetData]:
            self.preview_calls.append(spreadsheet_id)
            if spreadsheet_id in self.fail_ids:
                raise GoogleDriverError("temporary Sheets failure")
            sheet = self.sheets[spreadsheet_id]
            return sheet if isinstance(sheet, list) else [sheet]

    driver = FailingPreviewDriver()
    folder_id = information_module.FOLDERS["contact"][0]
    first = _source_file("first", "ENG-2026013")
    second = _source_file("second", "ENG-2026014")
    driver.files[folder_id] = [first, second]
    driver.sheets["first"] = _sheet(
        "first", 0, [["联络编号", "ENG-2026013"], ["主题", "第一条"]]
    )
    driver.sheets["second"] = _sheet(
        "second", 0, [["联络编号", "ENG-2026014"], ["主题", "第二条"]]
    )
    driver.fail_ids.add("second")
    cache_path = tmp_path / "information.sqlite3"
    service = InformationService(driver, cache_path=cache_path)  # type: ignore[arg-type]

    with pytest.raises(Exception, match="ENG-2026014"):
        service.refresh_files("contact")

    with sqlite3.connect(cache_path) as connection:
        progress_payload = connection.execute(
            "SELECT payload FROM engineering_information_progress WHERE kind = 'contact'"
        ).fetchone()
    assert progress_payload is not None
    assert "ENG-2026013" in progress_payload[0]
    assert "ENG-2026014" not in progress_payload[0]

    driver.fail_ids.clear()
    driver.preview_calls.clear()
    response = service.refresh_files("contact")
    assert response.total == 2
    assert driver.preview_calls == ["second"]


def test_resume_reloads_invalid_progress_records_but_skips_valid_ones(tmp_path) -> None:
    class FailingPreviewDriver(FakeInformationDriver):
        def __init__(self) -> None:
            super().__init__()
            self.fail_ids: set[str] = set()

        def read_spreadsheet_previews(self, spreadsheet_id: str) -> list[GoogleSheetData]:
            self.preview_calls.append(spreadsheet_id)
            if spreadsheet_id in self.fail_ids:
                raise GoogleDriverError("temporary Sheets failure")
            sheet = self.sheets[spreadsheet_id]
            return sheet if isinstance(sheet, list) else [sheet]

    driver = FailingPreviewDriver()
    folder_id = information_module.FOLDERS["ecn"][0]
    files = [
        _source_file("valid", "ECN-0574 Valid"),
        _source_file("invalid", "ECN-0575 Invalid"),
        _source_file("blocked", "ECN-0576 Blocked"),
    ]
    driver.files[folder_id] = files
    driver.sheets["valid"] = _sheet(
        "valid", 1, [["产品型号", "Flex"], ["ECN编号", "ECN-0574"]]
    )
    driver.sheets["invalid"] = _sheet(
        "invalid", 1, [["产品型号", "-"], ["ECN编号", "ECN-0575"]]
    )
    driver.sheets["blocked"] = _sheet(
        "blocked", 1, [["产品型号", "Flex"], ["ECN编号", "ECN-0576"]]
    )
    driver.fail_ids.add("blocked")
    cache_path = tmp_path / "information.sqlite3"
    service = InformationService(driver, cache_path=cache_path)  # type: ignore[arg-type]

    with pytest.raises(Exception, match="ECN-0576"):
        service.refresh_files("ecn")

    with sqlite3.connect(cache_path) as connection:
        progress_count = connection.execute(
            "SELECT json_array_length(payload, '$.files') "
            "FROM engineering_information_progress WHERE kind = 'ecn'"
        ).fetchone()
    assert progress_count == (2,)

    driver.sheets["invalid"] = _sheet(
        "invalid", 1, [["产品型号", "Flex"], ["ECN编号", "ECN-0575"]]
    )
    driver.fail_ids.clear()
    driver.preview_calls.clear()
    response = service.refresh_files("ecn")

    assert response.total == 3
    assert driver.preview_calls == ["invalid", "blocked"]


def test_page_reads_return_while_google_refresh_is_still_running(tmp_path) -> None:
    class BlockingInformationDriver(FakeInformationDriver):
        def __init__(self) -> None:
            super().__init__()
            self.list_started = threading.Event()
            self.release_list = threading.Event()

        def list_files_in_folder(self, folder_id: str) -> list[GoogleDriveFile]:
            self.list_started.set()
            if not self.release_list.wait(timeout=2):
                raise GoogleDriverError("test scan was not released")
            return super().list_files_in_folder(folder_id)

    driver = BlockingInformationDriver()
    folder_id = information_module.FOLDERS["contact"][0]
    driver.files[folder_id] = [_source_file("contact-sheet-13", "ENG-2026013")]
    driver.sheets["contact-sheet-13"] = _sheet(
        "contact-sheet-13",
        0,
        [["联络编号", "ENG-2026013"], ["主题", "关于Stacker图纸变更通知"]],
    )
    service = InformationService(
        driver,  # type: ignore[arg-type]
        cache_path=tmp_path / "engineering_information.sqlite3",
    )

    assert service.request_refresh("contact") is True
    assert driver.list_started.wait(timeout=1)

    while_scanning = service.get_files("contact", refresh=True)
    assert while_scanning.total == 0
    assert while_scanning.refreshing is True

    driver.release_list.set()
    with service._condition:
        assert service._condition.wait_for(
            lambda: "contact" not in service._refreshing,
            timeout=2,
        )

    completed = service.get_files("contact")
    assert completed.total == 1
    assert completed.files[0].subject == "关于Stacker图纸变更通知"
    assert completed.refreshing is False


def test_empty_index_queues_background_initialization_without_google_wait(
    tmp_path,
    monkeypatch,
) -> None:
    service = InformationService(
        FakeInformationDriver(),  # type: ignore[arg-type]
        cache_path=tmp_path / "engineering_information.sqlite3",
    )
    queued: list[str] = []
    monkeypatch.setattr(
        service,
        "request_refresh",
        lambda kind: queued.append(kind) or True,
    )

    response = service.get_files("ecn")

    assert response.total == 0
    assert response.cached is True
    assert queued == ["ecn"]


def test_daily_scheduler_refreshes_both_lists(monkeypatch) -> None:
    refresh_calls: list[str] = []

    class FakeService:
        def refresh_all(self):
            refresh_calls.extend(["ecn", "contact"])
            return {}

    async def stop_after_first_cycle(seconds: int) -> None:
        assert seconds == 86400
        raise asyncio.CancelledError

    monkeypatch.setattr(information_module, "information_service", FakeService())
    monkeypatch.setattr(information_module, "INFORMATION_REFRESH_SECONDS", 86400)
    monkeypatch.setattr(information_module.asyncio, "sleep", stop_after_first_cycle)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(_information_refresh_scheduler())

    assert refresh_calls == ["ecn", "contact"]


def test_scheduler_retries_failed_google_refresh_after_five_minutes(monkeypatch) -> None:
    class FailingService:
        def refresh_all(self):
            raise GoogleDriverError("proxy is not ready")

    async def stop_after_retry_delay(seconds: int) -> None:
        assert seconds == 300
        raise asyncio.CancelledError

    monkeypatch.setattr(information_module, "information_service", FailingService())
    monkeypatch.setattr(information_module, "INFORMATION_REFRESH_SECONDS", 86400)
    monkeypatch.setattr(information_module.asyncio, "sleep", stop_after_retry_delay)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(_information_refresh_scheduler())
