from api.models import InformationFile
from api.routers.information import _number_sort_key, _parse_file
from core.google import GoogleDriveFile


def test_parse_contact_letter_fields_from_sheet_values() -> None:
    file = GoogleDriveFile(
        id="sheet-id",
        name="ENG-2026001 联络函",
        mime_type="application/vnd.google-apps.spreadsheet",
        created_time="2026-01-25T08:00:00Z",
        web_view_link="https://docs.google.com/spreadsheets/d/sheet-id/edit",
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
    assert parsed.effective_date == "2026-01-26"
    assert parsed.web_view_link == "https://docs.google.com/spreadsheets/d/sheet-id/edit"


def test_parse_file_uses_filename_and_created_date_as_fallbacks() -> None:
    file = GoogleDriveFile(
        id="sheet-id",
        name="ECN-2026012 - Heater Shaker bracket update",
        mime_type="application/vnd.google-apps.spreadsheet",
        created_time="2026-03-07T08:00:00Z",
    )

    parsed = _parse_file("ecn", file, [])

    assert parsed.number == "ECN-2026012"
    assert parsed.subject == "Heater Shaker bracket update"
    assert parsed.effective_date == "2026-03-07"
    assert parsed.web_view_link == "https://docs.google.com/spreadsheets/d/sheet-id/edit"


def test_information_files_sort_by_number_with_latest_first() -> None:
    files = [
        InformationFile(id="1", number="ENG-2026002", subject="Second", web_view_link="https://example.com/1"),
        InformationFile(id="2", number="ENG-2026010", subject="Tenth", web_view_link="https://example.com/2"),
        InformationFile(id="3", number="ENG-2026009", subject="Ninth", web_view_link="https://example.com/3"),
    ]

    files.sort(key=_number_sort_key, reverse=True)

    assert [file.number for file in files] == ["ENG-2026010", "ENG-2026009", "ENG-2026002"]
