from __future__ import annotations

import pytest

from modules.test_failures.report_link_source import (
    DEFAULT_SINGLE_CHANNEL_SPREADSHEET_ID, DEFAULT_SPREADSHEET_ID,
    GoogleReportLinkSource, cell_urls, grid_rows, metadata_identity, report_target,
)


URL = "https://docs.google.com/spreadsheets/d/synthetic-report-001/edit#gid=8"


def cell(value="", **kwargs):
    return {"formattedValue": value, **kwargs}


def block(gid, rows, start_row=0, start_col=0):
    return {"properties": {"sheetId": gid, "title": "QC"}, "data": [{
        "startRow": start_row, "startColumn": start_col,
        "rowData": [{"values": [value if isinstance(value, dict) else cell(value) for value in row]} for row in rows],
    }]}


@pytest.mark.parametrize("entry", [cell(URL), cell("report", hyperlink=URL),
    cell("report", userEnteredValue={"formulaValue": f'=HYPERLINK("{URL}","report")'}),
    cell("report", textFormatRuns=[{"format": {"link": {"uri": URL}}}]),
    cell("report", userEnteredFormat={"textFormat": {"link": {"uri": URL}}}),
])
def test_extracts_supported_report_links(entry):
    assert cell_urls(entry) == [URL]


@pytest.mark.parametrize("url", ["javascript:alert(1)", "https://docs.google.com.evil.invalid/spreadsheets/d/a",
    "https://name@docs.google.com/spreadsheets/d/a", "http://docs.google.com/spreadsheets/d/a",
    "https://docs.google.com:444/spreadsheets/d/a", URL + "&gid=9", URL.replace("#gid=8", "?gid=9#gid=8")])
def test_rejects_unsafe_or_conflicting_link(url):
    with pytest.raises(ValueError):
        report_target(url)
    assert cell_urls(cell(url)) == []


def test_merges_disjoint_ranges_using_google_offsets():
    rows = grid_rows([block(7, [["SN-1"], ["SN-2"]], 7, 4), block(7, [[URL]], 8, 3)])
    assert rows[7][8][4]["formattedValue"] == "SN-2"
    assert rows[7][8][3]["formattedValue"] == URL
    assert 3 not in rows[7][7]


@pytest.mark.parametrize("rows", [
    [["0", "METADATA"], ["0", "date", "run-26-01-02-08-41-03"], ["0", "pipette", "P50M-TEST"], ["0", "-------------------"]],
    [["0", "META_DATA_START"], ["0", "test_device_id", "P50M-TEST"], ["0", "test_run_id", "run-26-01-02-08-41-03"], ["0", "META_DATA_END"]],
])
def test_supports_old_and_new_metadata_without_timestamp_guessing(rows):
    assert metadata_identity(grid_rows([block(8, rows)])[8]) == {"sn": "P50M-TEST", "report_run_id": "run-26-01-02-08-41-03"}


@pytest.mark.parametrize("rows", [
    [["0", "pipette", "SN"], ["0", "date", "run"]],
    [["0", "METADATA"], ["0", "pipette", "SN"], ["0", "date", "run"]],
    [["0", "METADATA"], ["0", "pipette", "SN"], ["0", "test_time_utc", "2026-01-02"], ["0", "-------------------"]],
    [["0", "METADATA"], ["0", "pipette", "SN"], ["0", "date", "run"], ["0", "test_run_id", "other-run"], ["0", "-------------------"]],
])
def test_missing_incomplete_conflicting_metadata_is_unverifiable(rows):
    with pytest.raises(ValueError):
        metadata_identity(grid_rows([block(8, rows)])[8])


class Driver:
    def __init__(self):
        self.calls = []

    def get_sheet_metadata(self, spreadsheet_id):
        return [{"sheetId": 7, "title": "Model's QC", "gridProperties": {"columnCount": 120}}]

    def read_sheet_grid_ranges(self, spreadsheet_id, ranges):
        self.calls.append(ranges)
        if len(self.calls) == 1:
            return [block(7, [["Ignore", "Retest", "Notes", "Description", "Pipette", "report_run_id"]], 6)]
        return [block(7, [[URL], [URL]], 7, 3), block(7, [["SN-A"], ["SN-B"]], 7, 4), block(7, [["run-A"], ["run-B"]], 7, 5)]


def test_catalog_detects_shifted_headers_and_reads_only_identity_link_columns():
    driver = Driver()
    source = GoogleReportLinkSource(driver, spreadsheet_id="synthetic-catalog", sheet_gids=[7])
    rows = source.read_catalog()
    assert driver.calls[1] == ["'Model''s QC'!D8:D", "'Model''s QC'!E8:E", "'Model''s QC'!F8:F"]
    assert [(row["sn"], row["report_run_id"], row["row"]) for row in rows] == [("SN-A", "run-A", 8), ("SN-B", "run-B", 9)]
    assert rows[1]["source_url"].endswith("#gid=7&range=D9")


def test_requested_missing_tab_does_not_silently_fall_back():
    with pytest.raises(ValueError):
        GoogleReportLinkSource(Driver(), spreadsheet_id="synthetic-catalog", sheet_gids=[8]).read_catalog()


def test_report_gid_must_exist_and_never_uses_another_tab():
    with pytest.raises(ValueError):
        GoogleReportLinkSource(Driver(), spreadsheet_id="synthetic-catalog").read_identity(URL)


def test_changed_report_tab_headers_cannot_be_silently_skipped():
    class ChangedDriver(Driver):
        def read_sheet_grid_ranges(self, *_args):
            return [block(7, [["Pipette", "Unknown column"], ["SN", URL]])]
    with pytest.raises(ValueError):
        GoogleReportLinkSource(ChangedDriver(), spreadsheet_id="synthetic-catalog").read_catalog()


def test_nonempty_invalid_link_retains_unverifiable_candidate_but_blank_is_absent():
    class InvalidDriver(Driver):
        def read_sheet_grid_ranges(self, spreadsheet_id, ranges):
            if not self.calls:
                self.calls.append(ranges)
                return [block(7, [["QC Link", "Pipette"]])]
            return [block(7, [["https://example.invalid/report", "SN-bad"], ["", "SN-empty"]], 1)]
    rows = GoogleReportLinkSource(InvalidDriver(), spreadsheet_id="synthetic-catalog").read_catalog()
    assert len(rows) == 1
    assert rows[0]["sn"] == "SN-bad"
    assert rows[0]["url"] == ""
    assert rows[0]["error_code"] == "invalid_link"


def test_channel_defaults_and_configuration_are_isolated(monkeypatch):
    for prefix in ("PRODUCTION_PLATFORM_TEST_FAILURE_REPORT", "PRODUCTION_PLATFORM_TEST_FAILURE_REPORT_1CH"):
        monkeypatch.delenv(f"{prefix}_SHEET_ID", raising=False)
        monkeypatch.delenv(f"{prefix}_SHEET_GIDS", raising=False)
    single = GoogleReportLinkSource(Driver(), channel="1ch")
    multi = GoogleReportLinkSource(Driver())
    assert (single.spreadsheet_id, single.sheet_gids) == (DEFAULT_SINGLE_CHANNEL_SPREADSHEET_ID, [])
    assert (multi.spreadsheet_id, multi.sheet_gids) == (DEFAULT_SPREADSHEET_ID, [])
    monkeypatch.setenv("PRODUCTION_PLATFORM_TEST_FAILURE_REPORT_SHEET_ID", "multi-channel-custom")
    monkeypatch.setenv("PRODUCTION_PLATFORM_TEST_FAILURE_REPORT_SHEET_GIDS", "7,9")
    single = GoogleReportLinkSource(Driver(), channel="1ch")
    multi = GoogleReportLinkSource(Driver())
    assert (single.spreadsheet_id, single.sheet_gids) == (DEFAULT_SINGLE_CHANNEL_SPREADSHEET_ID, [])
    assert (multi.spreadsheet_id, multi.sheet_gids) == ("multi-channel-custom", [7, 9])
    monkeypatch.setenv("PRODUCTION_PLATFORM_TEST_FAILURE_REPORT_1CH_SHEET_ID", "single-channel-custom")
    monkeypatch.setenv("PRODUCTION_PLATFORM_TEST_FAILURE_REPORT_1CH_SHEET_GIDS", "11, 13")
    single = GoogleReportLinkSource(Driver(), channel="1ch")
    multi = GoogleReportLinkSource(Driver())
    assert (single.spreadsheet_id, single.sheet_gids) == ("single-channel-custom", [11, 13])
    assert (multi.spreadsheet_id, multi.sheet_gids) == ("multi-channel-custom", [7, 9])


def test_source_parameters_override_environment_and_namespace_includes_channel(monkeypatch):
    monkeypatch.setenv("PRODUCTION_PLATFORM_TEST_FAILURE_REPORT_1CH_SHEET_ID", "configured-single")
    monkeypatch.setenv("PRODUCTION_PLATFORM_TEST_FAILURE_REPORT_1CH_SHEET_GIDS", "99")
    single = GoogleReportLinkSource(Driver(), "explicit-catalog", [9, 7], channel="1ch")
    same = GoogleReportLinkSource(Driver(), "explicit-catalog", [7, 9], channel="1ch")
    other = GoogleReportLinkSource(Driver(), "explicit-catalog", [9, 7])
    assert (single.spreadsheet_id, single.sheet_gids) == ("explicit-catalog", [9, 7])
    assert single.cache_namespace == same.cache_namespace
    assert single.cache_namespace != other.cache_namespace


def test_channel_configuration_failure_does_not_fall_back_to_other_tracker(monkeypatch):
    monkeypatch.setenv("PRODUCTION_PLATFORM_TEST_FAILURE_REPORT_SHEET_ID", "valid-multi-catalog")
    monkeypatch.setenv("PRODUCTION_PLATFORM_TEST_FAILURE_REPORT_1CH_SHEET_ID", "invalid value")
    with pytest.raises(ValueError):
        GoogleReportLinkSource(Driver(), channel="1ch")
    assert GoogleReportLinkSource(Driver()).spreadsheet_id == "valid-multi-catalog"
    with pytest.raises(ValueError):
        GoogleReportLinkSource(Driver(), channel="96ch")


def test_single_channel_catalog_reads_all_report_tabs_and_skips_statistics():
    class SingleChannelDriver(Driver):
        def get_sheet_metadata(self, _spreadsheet_id):
            return [{"sheetId": gid, "title": f"Single QC {gid}", "gridProperties": {"columnCount": 16}}
                    for gid in range(1, 7)] + [{"sheetId": 7, "title": "P50S Assembly Analysis", "gridProperties": {"columnCount": 8}}]

        def read_sheet_grid_ranges(self, _spreadsheet_id, ranges):
            self.calls.append(ranges)
            if len(self.calls) == 1:
                return [block(gid, [["Notes", "Description" if gid % 2 else "QC Link", "Pipette"]], 6)
                        for gid in range(1, 7)] + [block(7, [["Month", "Pass", "Fail"]], 0)]
            return [block(gid, [[URL, f"P50S-TEST-{gid}"]], 7, 1) for gid in range(1, 7)]

    driver = SingleChannelDriver()
    rows = GoogleReportLinkSource(driver, "single-channel-catalog", channel="1ch").read_catalog()
    assert len(rows) == 6
    assert {row["sheet_id"] for row in rows} == set(range(1, 7))
    assert all(row["row"] == 8 and row["report_run_id"] == "" for row in rows)
    assert all("P50S Assembly Analysis" not in value for value in driver.calls[1])
    assert all("/single-channel-catalog/" in row["source_url"] for row in rows)


class IdentityDriver(Driver):
    def __init__(self, sheets, rows=None):
        super().__init__()
        self.sheets = sheets
        self.rows = rows if rows is not None else [
            ["0", "METADATA"], ["0", "pipette", "P50S-TEST"],
            ["0", "date", "run-26-01-02-08-41-03"], ["0", "-------------------"],
        ]

    def get_sheet_metadata(self, _spreadsheet_id):
        return self.sheets

    def read_sheet_grid_ranges(self, _spreadsheet_id, ranges):
        self.calls.append(ranges)
        return [block(sheet["sheetId"], self.rows) for sheet in self.sheets]


def test_legacy_missing_default_gid_uses_only_unique_assembly_qc_and_returns_resolved_url():
    driver = IdentityDriver([{"sheetId": 27, "title": "Assembly QC"}, {"sheetId": 31, "title": "Current/Speed Test"}])
    source = GoogleReportLinkSource(driver, "single-channel-catalog", channel="1ch")
    identity = source.read_identity(URL.replace("#gid=8", "#gid=0"))
    assert identity == {"sn": "P50S-TEST", "report_run_id": "run-26-01-02-08-41-03",
                        "resolved_url": URL.replace("#gid=8", "#gid=27")}
    assert driver.calls == [["'Assembly QC'!A1:D120"]]


def test_existing_default_gid_remains_authoritative_instead_of_named_qc_tab():
    driver = IdentityDriver([{"sheetId": 0, "title": "Original Report"}, {"sheetId": 27, "title": "Assembly QC"}])
    identity = GoogleReportLinkSource(driver, "single-channel-catalog").read_identity(URL.replace("#gid=8", "#gid=0"))
    assert identity == {"sn": "P50S-TEST", "report_run_id": "run-26-01-02-08-41-03"}
    assert driver.calls == [["'Original Report'!A1:D120"]]


@pytest.mark.parametrize("gid,sheets", [
    (8, [{"sheetId": 27, "title": "Assembly QC"}]),
    (0, [{"sheetId": 27, "title": "Current/Speed Test"}]),
    (0, [{"sheetId": 27, "title": "Assembly QC"}, {"sheetId": 28, "title": "Assembly_QC"}]),
    (0, [{"sheetId": 27, "title": "Assembly QC", "sheetType": "OBJECT"}]),
])
def test_wrong_nondefault_gid_or_missing_ambiguous_qc_cannot_be_repaired(gid, sheets):
    driver = IdentityDriver(sheets)
    with pytest.raises(ValueError):
        GoogleReportLinkSource(driver, "single-channel-catalog").read_identity(URL.replace("#gid=8", f"#gid={gid}"))
    assert driver.calls == []


@pytest.mark.parametrize("rows", [
    [["0", "METADATA"], ["0", "pipette", "P50S-TEST"], ["0", "-------------------"]],
    [["0", "METADATA"], ["0", "pipette", "P50S-TEST"], ["0", "date", "run-one"],
     ["0", "test_run_id", "run-other"], ["0", "-------------------"]],
])
def test_legacy_gid_repair_still_rejects_incomplete_or_conflicting_identity(rows):
    driver = IdentityDriver([{"sheetId": 27, "title": "Assembly QC"}], rows)
    with pytest.raises(ValueError):
        GoogleReportLinkSource(driver, "single-channel-catalog").read_identity(URL.replace("#gid=8", "#gid=0"))


def test_existing_default_gid_with_bad_metadata_cannot_fall_back_to_valid_qc():
    class BadDefaultDriver(IdentityDriver):
        def read_sheet_grid_ranges(self, spreadsheet_id, ranges):
            super().read_sheet_grid_ranges(spreadsheet_id, ranges)
            return [block(0, [["0", "no metadata"]]), block(27, self.rows)]

    driver = BadDefaultDriver([{"sheetId": 0, "title": "Original Report"}, {"sheetId": 27, "title": "Assembly QC"}])
    with pytest.raises(ValueError):
        GoogleReportLinkSource(driver, "single-channel-catalog").read_identity(URL.replace("#gid=8", "#gid=0"))
    assert driver.calls == [["'Original Report'!A1:D120"]]
