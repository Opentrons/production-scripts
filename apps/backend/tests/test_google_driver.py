from core.google.client import GoogleDriver


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
