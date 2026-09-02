import asyncio

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
        self.sheets: dict[str, GoogleSheetData] = {}
        self.list_error: Exception | None = None

    def list_files_in_folder(self, folder_id: str) -> list[GoogleDriveFile]:
        if self.list_error is not None:
            raise self.list_error
        return list(self.files[folder_id])

    def read_spreadsheet_preview(self, spreadsheet_id: str) -> GoogleSheetData:
        return self.sheets[spreadsheet_id]


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


def _source_file(file_id: str, name: str) -> GoogleDriveFile:
    return GoogleDriveFile(
        id=file_id,
        name=name,
        mime_type="application/vnd.google-apps.spreadsheet",
        modified_time="2026-08-24T08:00:00Z",
        parent_path="2026",
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

    ecn = service.get_files("ecn", refresh=True)
    contacts = service.get_files("contact", refresh=True)

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

    assert service.get_files("contact", refresh=True).total == 1

    driver.files[folder_id].append(second)
    driver.sheets["contact-sheet-14"] = _sheet(
        "contact-sheet-14",
        14,
        [["联络编号", "ENG-2026014"], ["主题", "关于Pipette装配方法变更通知"]],
    )
    refreshed = service.get_files("contact", refresh=True)

    assert refreshed.total == 2
    assert [item.number for item in refreshed.files] == ["ENG-2026014", "ENG-2026013"]

    failing_driver = FakeInformationDriver()
    failing_driver.list_error = GoogleDriverError("Drive unavailable")
    restarted = InformationService(
        failing_driver,  # type: ignore[arg-type]
        cache_path=cache_path,
    )
    fallback = restarted.get_files("contact", refresh=True)
    assert fallback.total == 2
    assert fallback.cached is True
    assert fallback.quality_checked is True
    assert "已保留上次完整数据" in str(fallback.error)


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
