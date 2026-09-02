from pathlib import Path

from core.config import GOOGLE_TOKEN_PATH, TOKEN_PATH
from core.google.client import GoogleDriver


def test_information_google_client_reuses_upload_account_token() -> None:
    assert GOOGLE_TOKEN_PATH == Path(TOKEN_PATH)


def test_parse_drive_file_id_from_supported_urls() -> None:
    file_id = "1vDVuW4YlbAKDGVohoa3rHHMcF00HUYrL"

    assert GoogleDriver.parse_drive_file_id(file_id) == file_id
    assert GoogleDriver.parse_drive_file_id(f"https://drive.google.com/file/d/{file_id}/view") == file_id
    assert GoogleDriver.parse_drive_file_id(f"https://drive.google.com/open?id={file_id}") == file_id


def test_google_sheet_column_name() -> None:
    assert GoogleDriver.column_name(1) == "A"
    assert GoogleDriver.column_name(26) == "Z"
    assert GoogleDriver.column_name(27) == "AA"
    assert GoogleDriver.column_name(52) == "AZ"


class _FakeRequest:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def execute(self) -> dict:
        return self.payload


class _FakeSpreadsheets:
    def get(self, **kwargs):
        assert kwargs["ranges"] == ["A1:CC200"]
        assert kwargs["includeGridData"] is True
        assert "properties(title)" in kwargs["fields"]
        return _FakeRequest(
            {
                "properties": {"title": "ECN-0571 436-00159 Drawing Update"},
                "sheets": [
                    {
                        "properties": {
                            "sheetId": 104681895,
                            "title": "ECN",
                            "index": 0,
                        },
                        "data": [
                            {
                                "rowData": [
                                    {
                                        "values": [
                                            {"formattedValue": "产品型号"},
                                            {},
                                            {"formattedValue": "Heater shaker"},
                                        ]
                                    }
                                ]
                            }
                        ],
                    }
                ]
            }
        )


class _FakeSheetsService:
    def spreadsheets(self) -> _FakeSpreadsheets:
        return _FakeSpreadsheets()


def test_read_spreadsheet_preview_returns_values_and_gid() -> None:
    driver = GoogleDriver(allow_interactive_auth=False)
    driver._sheets_service = _FakeSheetsService()
    driver._execute = lambda factory: factory().execute()  # type: ignore[method-assign]

    preview = driver.read_spreadsheet_preview("sheet-id")

    assert preview.sheet_id == 104681895
    assert preview.title == "ECN"
    assert preview.document_title == "ECN-0571 436-00159 Drawing Update"
    assert preview.values == [["产品型号", "", "Heater shaker"]]


class _FakeDriveFiles:
    def list(self, **kwargs):
        folder_id = kwargs["q"].split("'")[1]
        page_token = kwargs.get("pageToken")
        if folder_id == "root" and page_token is None:
            return _FakeRequest(
                {
                    "files": [
                        {
                            "id": "archive",
                            "name": "Archive",
                            "mimeType": "application/vnd.google-apps.folder",
                            "createdTime": "2025-01-01T00:00:00Z",
                        },
                        {
                            "id": "old",
                            "name": "old.pdf",
                            "mimeType": "application/pdf",
                            "createdTime": "2025-12-31T00:00:00Z",
                        },
                    ],
                    "nextPageToken": "next",
                }
            )
        if folder_id == "root" and page_token == "next":
            return _FakeRequest(
                {
                    "files": [
                        {
                            "id": "current",
                            "name": "current.pdf",
                            "mimeType": "application/pdf",
                            "createdTime": "2026-08-01T00:00:00Z",
                        }
                    ]
                }
            )
        if folder_id == "archive":
            return _FakeRequest(
                {
                    "files": [
                        {
                            "id": "nested",
                            "name": "nested.doc",
                            "mimeType": "application/vnd.google-apps.document",
                            "createdTime": "2026-02-02T00:00:00Z",
                        }
                    ]
                }
            )
        return _FakeRequest({"files": []})


class _FakeDriveService:
    def __init__(self) -> None:
        self.files_api = _FakeDriveFiles()

    def files(self) -> _FakeDriveFiles:
        return self.files_api


def test_list_files_in_folder_filters_year_and_traverses_nested_folders() -> None:
    driver = GoogleDriver(allow_interactive_auth=False)
    driver._drive_service = _FakeDriveService()
    driver._execute = lambda factory: factory().execute()  # type: ignore[method-assign]

    files = driver.list_files_in_folder("https://drive.google.com/drive/folders/root", year=2026)

    assert [file.name for file in files] == ["current.pdf", "nested.doc"]
    assert files[1].parent_path == "Archive"


def test_list_files_in_folder_without_year_returns_all_files() -> None:
    driver = GoogleDriver(allow_interactive_auth=False)
    driver._drive_service = _FakeDriveService()
    driver._execute = lambda factory: factory().execute()  # type: ignore[method-assign]

    files = driver.list_files_in_folder("https://drive.google.com/drive/folders/root")

    assert [file.name for file in files] == ["current.pdf", "nested.doc", "old.pdf"]


class _ShortcutDriveFiles:
    def list(self, **kwargs):
        folder_id = kwargs["q"].split("'")[1]
        if folder_id == "root":
            return _FakeRequest(
                {
                    "files": [
                        {
                            "id": "folder-shortcut",
                            "name": "2026",
                            "mimeType": "application/vnd.google-apps.shortcut",
                            "shortcutDetails": {
                                "targetId": "nested-folder",
                                "targetMimeType": "application/vnd.google-apps.folder",
                            },
                        }
                    ]
                }
            )
        if folder_id == "nested-folder":
            return _FakeRequest(
                {
                    "files": [
                        {
                            "id": "sheet-shortcut",
                            "name": "ENG-2026001",
                            "mimeType": "application/vnd.google-apps.shortcut",
                            "createdTime": "2026-01-26T00:00:00Z",
                            "shortcutDetails": {
                                "targetId": "real-sheet",
                                "targetMimeType": "application/vnd.google-apps.spreadsheet",
                                "targetResourceKey": "sheet-resource-key",
                            },
                        }
                    ]
                }
            )
        return _FakeRequest({"files": []})


class _ShortcutDriveService:
    def __init__(self) -> None:
        self.files_api = _ShortcutDriveFiles()

    def files(self) -> _ShortcutDriveFiles:
        return self.files_api


def test_list_files_in_folder_resolves_shortcut_folders_and_sheets() -> None:
    driver = GoogleDriver(allow_interactive_auth=False)
    driver._drive_service = _ShortcutDriveService()
    driver._execute = lambda factory: factory().execute()  # type: ignore[method-assign]

    files = driver.list_files_in_folder("https://drive.google.com/drive/folders/root")

    assert len(files) == 1
    assert files[0].id == "real-sheet"
    assert files[0].shortcut_id == "sheet-shortcut"
    assert files[0].target_mime_type == "application/vnd.google-apps.spreadsheet"
    assert files[0].target_resource_key == "sheet-resource-key"
