from __future__ import annotations

import csv
import re
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import yaml

from modules.uploads.handler.parsers.registry import extract_csv
from modules.uploads.handler.product_catalog import get_upload_handler_config
from modules.uploads.handler.upload import UploadData
from modules.uploads.handler.uploaders.common import UploadCommonMixin
from modules.uploads.handler.drivers.csv_driver import CsvDriver
from modules.uploads.handler.repositories.config_repository import ConfigRepository
from modules.uploads.handler.uploaders.robot_parallelism import extract_parallelism_rows
from modules.uploads.handler.uploaders.spreadsheet_uploader import SpreadsheetUploader


FLEX_DATA_DIR = Path(__file__).resolve().parents[3] / "csv-samples" / "opentrons" / "Flex"
PRODUCTION_CONFIG = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "modules"
    / "uploads"
    / "handler"
    / "configs"
    / "upload_production.yaml"
)
FLEX_LEVELING_SN = "FLXU3020260601004"
FLEX_LEVELING_REPORT = FLEX_DATA_DIR / f"{FLEX_LEVELING_SN}-leveling-report-2026-07-22.csv"
EXPECTED_LEVELING_TESTS = {
    "gantry_leveling_test",
    "z_leveling_test",
    "ch8_leveling_test",
    "ch96_leveling_test",
    "gripper_leveling_test",
}


def _leveling_section_serials(report: Path) -> dict[str, str]:
    with report.open(encoding="utf-8-sig", newline="") as report_file:
        rows = list(csv.reader(report_file))

    section_serials = {}
    for row_index, row in enumerate(rows[:-2]):
        if len(row) < 3 or row[1:3] == ["TEST", ""] or row[1] != "TEST":
            continue
        test_name = row[2].strip()
        if test_name not in EXPECTED_LEVELING_TESTS:
            continue
        header = [cell.strip().upper() for cell in rows[row_index + 1]]
        assert "ROBOT_SN" in header, f"{test_name} is missing ROBOT_SN"
        serial_index = header.index("ROBOT_SN")
        section_serials[test_name] = rows[row_index + 2][serial_index].strip()
    return section_serials


def test_leveling_report_parses_five_sections_with_one_robot_serial_number() -> None:
    section_serials = _leveling_section_serials(FLEX_LEVELING_REPORT)

    result = extract_csv(str(FLEX_LEVELING_REPORT))

    assert result is not None
    assert result["upload_config_key"] == "robot_update_leveling"
    assert result["sn"] == FLEX_LEVELING_SN
    assert result["model"] == "Robot"
    assert result["finished"] is True
    assert result["error"] == "False"
    assert set(section_serials) == EXPECTED_LEVELING_TESTS
    assert set(section_serials.values()) == {FLEX_LEVELING_SN}


def test_robot_uploads_target_the_ot3_unit_tracker_tabs() -> None:
    robot_config_keys = (
        "robot_update_diagnostic",
        "robot_update_xy_belt_calibration",
        "robot_update_gantry_stress",
        "robot_update_leveling",
        "robot_update_z_stage",
    )

    for config_key in robot_config_keys:
        config = get_upload_handler_config(config_key)
        assert config.tracker_sheet_name_template == "{oem} OT3"


def test_leveling_report_with_matching_serial_numbers_parses(tmp_path: Path) -> None:
    report = tmp_path / "leveling.csv"
    report.write_text(
        "0,RESULTS,\n"
        "0,overall-result,PASS\n"
        "0,--------,\n"
        "0,METADATA,\n"
        "0,test-name,hardware-leveling\n"
        "0,operator-name,andy\n"
        "0,session-id,FLXU3020260601004\n"
        "0,robot,FLXU3020260601004\n"
        "0,-------------------,\n"
        "START_TIME,ROBOT_SN,RESULT_STATUS\n"
        "2026-07-23,FLXU3020260601004,PASS\n",
        encoding="utf-8",
    )

    result = extract_csv(str(report))

    assert result is not None
    assert result["upload_config_key"] == "robot_update_leveling"
    assert result["finished"] is True
    assert result["error"] == "False"


def test_gantry_stress_range_covers_all_nonempty_sample_columns() -> None:
    config = yaml.safe_load(PRODUCTION_CONFIG.read_text(encoding="utf-8"))
    configured_range = config["robot_update_gantry_stress"][0]["Range"]
    columns = UploadCommonMixin.normalize_csv_columns(configured_range)
    report = FLEX_DATA_DIR / "stress-test-qc-ot3_run-26-06-03-11-01-58.csv"
    with report.open(encoding="utf-8-sig", newline="") as csv_file:
        rows = list(csv.reader(csv_file))
    last_nonempty_column = max(
        max((index + 1 for index, value in enumerate(row) if value.strip()), default=0)
        for row in rows
    )

    assert columns[0] == "A"
    assert columns[-1] == "N"
    assert len(columns) >= last_nonempty_column


def test_all_flex_reports_share_robot_barcode_and_are_finished() -> None:
    reports = list(FLEX_DATA_DIR.glob("*.csv"))
    assert len(reports) == 5
    for report in reports:
        parsed = extract_csv(str(report))
        assert parsed["sn"] == FLEX_LEVELING_SN, report.name
        assert parsed["finished"] is True, report.name
        assert parsed["error"] == "False", report.name


def test_padded_flex_leveling_extracts_four_sections_without_changing_source() -> None:
    before = FLEX_LEVELING_REPORT.read_bytes()
    sections = extract_parallelism_rows(str(FLEX_LEVELING_REPORT), FLEX_LEVELING_SN)
    assert {name: len(rows[0]) for name, rows in sections.items()} == {
        "z_leveling_test": 40, "ch8_leveling_test": 13,
        "ch96_leveling_test": 39, "gripper_leveling_test": 10,
    }
    assert FLEX_LEVELING_REPORT.read_bytes() == before


def test_z_stage_prefers_robot_id_to_component_barcode(tmp_path: Path) -> None:
    source = FLEX_DATA_DIR / "z-stage-test-qc-ot3_run-26-06-02-07-49-43.csv"
    contents = source.read_text().replace(FLEX_LEVELING_SN, "ZS102026060105")
    contents = contents.replace("test_robot_id,ZS102026060105", f"test_robot_id,{FLEX_LEVELING_SN}")
    report = tmp_path / "z-stage.csv"
    report.write_text(contents)
    assert extract_csv(str(report))["sn"] == FLEX_LEVELING_SN


class _WorkflowCollection:
    """In-memory storage; the production code still builds queries and merges flags."""

    def __init__(self):
        self.rows = []

    @classmethod
    def matches(cls, row, query):
        for key, value in query.items():
            if key in {"$and", "$or"}:
                combine = all if key == "$and" else any
                if not combine(cls.matches(row, child) for child in value):
                    return False
            elif isinstance(value, dict):
                if "$exists" in value and (key in row) != value["$exists"]:
                    return False
                if "$ne" in value and row.get(key) == value["$ne"]:
                    return False
            elif row.get(key) != value:
                return False
        return True

    def find(self, query):
        class Cursor(list):
            def sort(self, key, direction):
                return sorted(self, key=lambda row: row[key], reverse=direction < 0)
        return Cursor(deepcopy(row) for row in self.rows if self.matches(row, query))

    def find_one(self, query, sort=None):
        rows = self.find(query)
        if sort:
            rows = rows.sort(*sort[0])
        return rows[0] if rows else None

    def insert_one(self, row):
        self.rows.append({**deepcopy(row), "_id": len(self.rows) + 1})
        return SimpleNamespace(inserted_id=self.rows[-1]["_id"])

    def update_one(self, query, update):
        for row in self.rows:
            if self.matches(row, query):
                row.update(deepcopy(update["$set"]))
                return SimpleNamespace(matched_count=1)
        return SimpleNamespace(matched_count=0)

    def delete_many(self, query):
        old_count = len(self.rows)
        self.rows = [row for row in self.rows if not self.matches(row, query)]
        return SimpleNamespace(deleted_count=old_count - len(self.rows))


@pytest.mark.parametrize("leveling_last", [False, True])
def test_five_flex_reports_complete_one_workflow_and_append_both_trackers(leveling_last):
    collection = _WorkflowCollection()
    context = UploadData.__new__(UploadData)
    context.mongo = SimpleNamespace(get_database=lambda _name: {"robot_diagnostic": collection})
    context.upload_session_repo = None
    context.upload_record_id = None
    context.upload_checkpoint = {}
    context._progress_callback = lambda *_args: None
    context.config_repo = ConfigRepository.from_environment("production")
    context.csv_driver = CsvDriver()
    context.gdrive = MagicMock()
    context.gdrive.copy_file.return_value = [True, "working-sheet"]
    sheets = ["Leveling", "XY-Calibration", "DiagnosticWithCosmeticPanel", "Gantry-Stress", "Z-Stage",
              "Z Stage Parallelism", "Pipette To Deck Parallelism", "Gripper Parallelism", "Opentrons OT3"]
    context.gdrive.get_sheet_info.return_value = [
        {"title": title, "sheet_id": index, "grid_properties": {"rowCount": 1000, "columnCount": 60}}
        for index, title in enumerate(sheets)
    ]
    context.gdrive.get_sheet_gid_map.return_value = dict(zip(sheets, range(len(sheets))))
    # F:I stay blank on existing rows; the actual J:AI destinations must be inspected.
    tracker_rows = [["header"]] * 10 + [["", "", "", "", '=IF(TRUE,"","")']]

    def read_tracker(**kwargs):
        assert kwargs["raise_on_error"] is True
        assert kwargs["value_render_option"] == "FORMULA"
        if kwargs["range"] != "'Opentrons OT3'!F:AI":
            assert kwargs["range"] in {
                "'Z Stage Parallelism'!C:AP", "'Pipette To Deck Parallelism'!B:N",
                "'Pipette To Deck Parallelism'!F:BB", "'Gripper Parallelism'!B:K",
            }
            return [["header"]] * 3
        return deepcopy(tracker_rows)

    context.gdrive.get_excel_sheet.side_effect = read_tracker
    raw_writes, tracker_writes = {}, []

    def write_rows(**kwargs):
        if kwargs["sheet_name"] == "Opentrons OT3":
            tracker_writes.append(deepcopy(kwargs))
            tracker_rows.append(["", "", "", "", *kwargs["new_values"][0]])
        else:
            raw_writes[kwargs["sheet_name"]] = deepcopy(kwargs)
        return True

    context.gdrive.update_excel_sheet_page_batch.side_effect = write_rows
    values_api = context.gdrive.sheet_service_client.spreadsheets.return_value.values.return_value
    values_api.get.return_value.execute.return_value = {"values": [["header"]] * 3}
    uploader = SpreadsheetUploader(context)
    # Google formula calculation and Drive archival are external to this regression.
    uploader.get_sheet_cell_value = lambda *_args, **_kwargs: "PASS"
    uploader.copy_summary_ranges = lambda *_args, **_kwargs: [[[[FLEX_LEVELING_SN, *range(24)]]]]
    uploader.move_spreadsheet_to_month = lambda *_args, **_kwargs: True
    uploader.upload_raw_data = lambda *_args, **_kwargs: {"url": "N/A"}
    uploader.log_upload_links = lambda *_args: None
    reports = sorted(FLEX_DATA_DIR.glob("*.csv"), key=lambda path: (path == FLEX_LEVELING_REPORT) == leveling_last)
    for index, report in enumerate(reports):
        context.upload_checkpoint = {}
        parsed = extract_csv(str(report))
        parsed["file_path"] = str(report)
        result = uploader.upload(parsed)
        assert result["database_saved"] is True, result
        assert not result.get("error"), result
        assert len(tracker_writes) == (1 if index == 4 else 0)
        if report == FLEX_LEVELING_REPORT:
            values_api.batchUpdate.assert_called_once()

    assert result["unit_tracker_status"] == "Uploaded to Unit Tracker"
    assert len(collection.rows) == 1
    assert collection.rows[0]["unit_tracker_uploaded"] is True
    context.gdrive.copy_file.assert_called_once()
    writes = values_api.batchUpdate.call_args.kwargs["body"]["data"]
    assert [write["range"] for write in writes] == [
        "'Z Stage Parallelism'!C11:AP11", "'Pipette To Deck Parallelism'!B11:N11",
        "'Pipette To Deck Parallelism'!P11:BB11", "'Gripper Parallelism'!B11:K11",
    ]
    with FLEX_LEVELING_REPORT.open(newline="", encoding="utf-8-sig") as source:
        source_rows = list(csv.reader(source))
    assert [row for batch in raw_writes["Leveling"]["new_values"] for row in batch] == source_rows
    assert raw_writes["Leveling"]["ranges"] == ["!A1:AP35"]
    stress = raw_writes["Gantry-Stress"]
    assert sum(len(batch) for batch in stress["new_values"]) == 11450
    assert stress["ranges"][-1] == "!A11001:N11450"
    expansions = context.gdrive.sheet_service_client.spreadsheets.return_value.batchUpdate.call_args_list
    assert any({"appendDimension": {"sheetId": 3, "dimension": "ROWS", "length": 10450}}
               in call.kwargs["body"]["requests"] for call in expansions)
    assert tracker_writes[0]["ranges"] == "!J12:AI12"

    # The next append observes J:AI written above, despite F:I still being blank.
    plan = SimpleNamespace(
        yaml_cfg=uploader.apply_oem_config(context.config_repo.get_upload_config("robot_update_leveling"), "Opentrons"),
        result=MagicMock(total_result="PASS"), require_total_result_for_tracker=True,
        tracker_sheet_name="Opentrons OT3", is_ultima=False, paste_file_resolver=None,
        sheet_link_index=0, sheet_link_mode="insert",
    )
    uploader.spreadsheet_workflow._paste_to_tracker(plan, [[[["next robot", *range(24)]]]], "next-link")
    assert tracker_writes[1]["ranges"] == "!J13:AI13"


def test_flex_leveling_upload_reaches_unit_tracker_and_cleans_test_row(
    pytestconfig,
    monkeypatch,
) -> None:
    if not pytestconfig.getoption("--upload"):
        pytest.skip("live Google upload test; run this test explicitly with --upload")

    # This smoke test cleans up its template and Unit Tracker row only.
    # Parallelism master writes are covered by isolated regression tests above.
    monkeypatch.setattr(
        "modules.uploads.handler.uploaders.spreadsheet_uploader.upload_parallelism_results",
        lambda *_args, **_kwargs: None,
    )

    client = UploadData(mongo=object())
    client.init_upload_handler()
    assert client.gdrive is not None, client.google_init_error

    monkeypatch.setattr(
        "modules.uploads.handler.upload.upload_settings_service.should_require_finished",
        lambda *_args, **_kwargs: True,
    )

    client.cleanup_incomplete_combined_workflow_if_needed = lambda *_args, **_kwargs: {"cleaned": False}
    client.query_reusable_csv_link = lambda *_args, **_kwargs: None
    client.save_upload_result_to_database = lambda *_args, **_kwargs: {
        "saved": True,
        "workflow_complete": True,
        "missing_tests": [],
        "unit_tracker_uploaded": False,
        "unit_tracker_link": "N/A",
        "error": "",
    }
    client.mark_unit_tracker_uploaded = lambda *_args, **_kwargs: True

    uploader = client.upload_repositories[0].uploaders["spreadsheet"]
    original_paste = uploader.paste_row_to_tracker
    original_get_or_copy = uploader.get_or_copy_spreadsheet
    tracker_write: dict = {}
    test_spreadsheet_link = ""
    tracker_row_deleted = False

    def get_or_copy_and_capture(*args, **kwargs):
        nonlocal test_spreadsheet_link
        spreadsheet_id, sheet_link = original_get_or_copy(*args, **kwargs)
        test_spreadsheet_link = sheet_link or ""
        return spreadsheet_id, sheet_link

    def paste_and_capture(
        spreadsheet_id,
        sheet_name,
        paste_range,
        row_data,
        **kwargs,
    ):
        uploaded = original_paste(
            spreadsheet_id,
            sheet_name,
            paste_range,
            row_data,
            **kwargs,
        )
        if uploaded:
            range_match = re.fullmatch(
                r"!([A-Z]+)\d+:([A-Z]+)\d+",
                paste_range,
            )
            assert range_match is not None, paste_range
            tracker_write.update(
                {
                    "spreadsheet_id": spreadsheet_id,
                    "sheet_name": sheet_name,
                    "paste_range": paste_range,
                    "start_column": range_match.group(1),
                    "end_column": range_match.group(2),
                    "expected_row": list(row_data[0]),
                }
            )
        return uploaded

    uploader.get_or_copy_spreadsheet = get_or_copy_and_capture
    uploader.paste_row_to_tracker = paste_and_capture
    try:
        result = client.update_data_to_google_drive(str(FLEX_LEVELING_REPORT))
        test_spreadsheet_link = result.get("csv_link") or test_spreadsheet_link

        assert result["finished"] is True, result
        assert result["sn"] == FLEX_LEVELING_SN
        assert result["test_type"] == "Leveling"
        assert result["unit_tracker_status"] == "Uploaded to Unit Tracker"
        assert tracker_write, "upload did not append a Unit Tracker row"

        row_number, actual_row = uploader.get_last_tracker_row(
            tracker_write["spreadsheet_id"],
            tracker_write["sheet_name"],
            tracker_write["start_column"],
            tracker_write["end_column"],
        )
        assert row_number is not None
        normalized_actual_row = uploader.normalize_tracker_row(actual_row)
        assert test_spreadsheet_link in normalized_actual_row
        assert normalized_actual_row == uploader.normalize_tracker_row(
            tracker_write["expected_row"]
        )

        tracker_row_deleted = uploader.delete_last_tracker_row_if_matches(
            tracker_write["spreadsheet_id"],
            tracker_write["sheet_name"],
            tracker_write["expected_row"],
            tracker_write["start_column"],
            tracker_write["end_column"],
        )
        assert tracker_row_deleted is True
    finally:
        if tracker_write and not tracker_row_deleted:
            uploader.delete_last_tracker_row_if_matches(
                tracker_write["spreadsheet_id"],
                tracker_write["sheet_name"],
                tracker_write["expected_row"],
                tracker_write["start_column"],
                tracker_write["end_column"],
            )
        if test_spreadsheet_link:
            client.gdrive.delete_drive_resource_by_url(test_spreadsheet_link)
