from modules.uploads.pressure_upload import (
    PRESSURE_TEST_SOURCE_SHEETS,
    append_pressure_summary,
    first_blank_row,
    normalize_pressure_rows,
    normalize_report_type,
    resolve_model_key,
)


def test_pressure_report_type_and_model_mapping() -> None:
    assert normalize_report_type("gravimetric") == "GRAVIMETRIC"
    assert resolve_model_key("P2HHV3220260509A02", "QC") == "P200H"
    assert resolve_model_key("P1KHV3620260603A01", "LIFETIME") == "P1000H"


def test_pressure_rows_skip_blank_and_all_zero_groups() -> None:
    assert normalize_pressure_rows([["", ""], ["0", "0"]]) == []
    rows = normalize_pressure_rows([["", "1"], ["0", "0"]])
    assert len(rows) == 2
    assert len(rows[0]) == 44


def test_first_blank_row_preserves_header_offset() -> None:
    assert first_blank_row([["header"], ["value"], []], start_row=1) == 3
    assert first_blank_row([["header"], ["value"]], start_row=2) == 4


class _Request:
    def __init__(self, result=None):
        self.result = result or {}

    def execute(self):
        return self.result


class _Values:
    def __init__(self, captured):
        self.captured = captured

    def update(self, **kwargs):
        self.captured.append(kwargs)
        return _Request()


class _Sheets:
    def __init__(self, captured):
        self.captured = captured

    def values(self):
        return _Values(self.captured)


class _Service:
    def __init__(self, captured):
        self.captured = captured

    def spreadsheets(self):
        return _Sheets(self.captured)


class _FakeDriver:
    def __init__(self, existing_target=None):
        self.captured = []
        self.sheet_service_client = _Service(self.captured)
        self.existing_target = existing_target or []

    def get_sheet_gid_map(self, spreadsheet_id):
        return {PRESSURE_TEST_SOURCE_SHEETS[0]: 123}

    def get_excel_sheet(self, spreadsheet_id, range_name, **kwargs):
        if spreadsheet_id == "source":
            return [["0", "1"] + [""] * 42]
        return self.existing_target


def test_append_pressure_summary_writes_source_link_and_44_columns() -> None:
    driver = _FakeDriver(existing_target=[["header"]])
    result = append_pressure_summary(
        driver,
        source_spreadsheet_id="source",
        model_key="P200H",
        report_type="QC",
    )
    assert result["updated"] is True
    assert result["target_range"].startswith("A2:AS")
    assert driver.captured
    payload = driver.captured[0]["body"]["values"]
    assert payload[0][0].endswith("gid=123")
    assert len(payload[0]) == 45


def test_append_pressure_summary_is_idempotent_for_existing_source_link() -> None:
    source_link = "https://docs.google.com/spreadsheets/d/source/edit#gid=123"
    driver = _FakeDriver(existing_target=[[source_link]])
    result = append_pressure_summary(
        driver,
        source_spreadsheet_id="source",
        model_key="P200H",
        report_type="QC",
    )
    assert result["deduplicated"] is True
    assert not driver.captured
