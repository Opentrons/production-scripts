from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest
import yaml

from modules.uploads.handler.parsers.registry import extract_csv
from modules.uploads.handler.product_catalog import get_upload_handler_config
from modules.uploads.handler.upload import UploadData
from modules.uploads.handler.uploaders.common import UploadCommonMixin


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


def test_flex_leveling_upload_reaches_unit_tracker_and_cleans_test_row(
    pytestconfig,
    monkeypatch,
) -> None:
    if not pytestconfig.getoption("--upload"):
        pytest.skip("live Google upload test; run this test explicitly with --upload")

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
