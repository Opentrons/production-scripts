from api.models import InformationFile
from api.routers.information import _belongs_to_year, _number_sort_key, _parse_file
from core.google import GoogleDriveFile


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
        name="ECN-0571 436-00159 Drawing Update",
        mime_type="application/vnd.google-apps.spreadsheet",
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
