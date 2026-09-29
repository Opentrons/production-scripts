from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from modules.uploads.handler.parsers.registry import extract_csv
from modules.uploads.handler.repositories.config_repository import ConfigRepository
from modules.uploads.handler.uploaders.common import ProductUploaderBase
from modules.uploads.handler.uploaders.robot_parallelism import (
    extract_parallelism_rows,
    upload_parallelism_results,
)
from modules.uploads.handler.uploaders.spreadsheet_uploader import SpreadsheetUploader
from modules.uploads.handler.models import UploadResult
from modules.uploads.handler.uploaders.workflows import SpreadsheetUploadPlan, SpreadsheetUploadWorkflow


SAMPLE = Path(__file__).resolve().parents[3] / "csv-samples/FLXA3020250805002-leveling-report-2026-07-22.csv"
ROBOT_SN = "FLXA3020250805002"


def test_sample_maps_robot_and_measurements_without_time_or_status():
    sections = extract_parallelism_rows(str(SAMPLE), ROBOT_SN)
    assert {name: len(rows[0]) for name, rows in sections.items()} == {
        "ch96_leveling_test": 39, "ch8_leveling_test": 13,
        "z_leveling_test": 40, "gripper_leveling_test": 10,
    }
    assert all(rows[0][0] == ROBOT_SN for rows in sections.values())
    assert sections["ch96_leveling_test"][0][1:4] == [29.888, 29.934, 0.046]
    assert sections["ch8_leveling_test"][0][-3:] == [30.074, 30.11, 0.036]
    assert sections["z_leveling_test"][0][-3:] == [30.026, 29.998, 0.028]
    assert sections["gripper_leveling_test"][0][-3:] == [30.482, 30.658, 0.176]


@pytest.mark.parametrize("damage", ["missing", "truncated", "duplicate", "sn", "nan"])
def test_malformed_sections_fail_before_upload(tmp_path, damage):
    with SAMPLE.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.reader(source))
    if damage == "missing":
        rows = rows[:-3]
    elif damage == "truncated":
        rows[-1].pop()
    elif damage == "duplicate":
        rows += rows[-3:]
    elif damage == "sn":
        rows[-1][1] = "ANOTHER-ROBOT"
    else:
        rows[-1][2] = "nan"
    path = tmp_path / "invalid.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        csv.writer(output).writerows(rows)
    with pytest.raises(ValueError):
        extract_parallelism_rows(str(path), ROBOT_SN)


def make_uploader():
    context = SimpleNamespace(upload_checkpoint={}, gdrive=MagicMock())

    def report(_stage, _message, checkpoint=None):
        context.upload_checkpoint.update(checkpoint or {})

    context.report_upload_progress = report
    uploader = ProductUploaderBase(context)
    uploader.ensure_tracker_row_capacity = MagicMock(return_value=True)
    values = context.gdrive.sheet_service_client.spreadsheets.return_value.values.return_value
    return uploader, values


@pytest.mark.parametrize("last_row_range, expected_checks", [
    ("F:I", ["C:AP", "B:N", "F:BB", "B:K"]),
    ("AQ:AR", ["C:AR", "B:AR", "P:BB", "B:AR"]),
])
def test_uses_configured_first_empty_row_search(last_row_range, expected_checks):
    uploader, values = make_uploader()
    histories = [
        [["header"]] * 10 + [[0], [], ["later data"]],
        [["header"]] * 10 + [[1], ['=IF(TRUE,"","")'], [], [2]],
        [["header"]] * 10 + [[], [3]],
        [],
    ]
    uploader.gdrive.get_excel_sheet.side_effect = histories
    sections = extract_parallelism_rows(str(SAMPLE), ROBOT_SN)
    upload_parallelism_results(uploader, "master-id", sections, last_row_range=last_row_range)
    body = values.batchUpdate.call_args.kwargs["body"]
    assert body["valueInputOption"] == "RAW"
    assert [write["range"] for write in body["data"]] == [
        "'Z Stage Parallelism'!C12:AP12",
        "'Pipette To Deck Parallelism'!B13:N13",
        "'Pipette To Deck Parallelism'!P11:BB11",
        "'Gripper Parallelism'!B11:K11",
    ]
    read_calls = uploader.gdrive.get_excel_sheet.call_args_list
    assert [call.kwargs["range"].split("!")[1] for call in read_calls] == expected_checks
    assert all(call.kwargs["raise_on_error"] is True for call in read_calls)
    assert all(call.kwargs["value_render_option"] == "FORMULA" for call in read_calls)
    assert uploader.get_upload_checkpoint()["parallelism_upload"]["complete"] is True
    assert uploader.ensure_tracker_row_capacity.call_count == 4
    # A later database/Unit Tracker retry must not append these rows again.
    upload_parallelism_results(uploader, "master-id", sections)
    assert values.batchUpdate.call_count == 1


def test_failed_read_never_writes_as_if_sheet_were_empty():
    uploader, values = make_uploader()
    uploader.gdrive.get_excel_sheet.side_effect = RuntimeError("read denied")
    with pytest.raises(RuntimeError, match="read denied"):
        upload_parallelism_results(uploader, "master-id", extract_parallelism_rows(str(SAMPLE), ROBOT_SN))
    values.batchUpdate.assert_not_called()


def test_multiple_measurement_rows_require_a_contiguous_empty_block():
    uploader, values = make_uploader()
    uploader.gdrive.get_excel_sheet.return_value = [["header"]] * 10 + [[], ["occupied"], [], [], ["later data"]]
    sections = extract_parallelism_rows(str(SAMPLE), ROBOT_SN)
    sections = {name: rows * 2 for name, rows in sections.items()}
    upload_parallelism_results(uploader, "master-id", sections)
    assert [write["range"] for write in values.batchUpdate.call_args.kwargs["body"]["data"]] == [
        "'Z Stage Parallelism'!C13:AP14", "'Pipette To Deck Parallelism'!B13:N14",
        "'Pipette To Deck Parallelism'!P13:BB14", "'Gripper Parallelism'!B13:K14",
    ]


@pytest.mark.parametrize("occupied", [False, True])
def test_retry_reuses_reserved_ranges_and_refuses_conflicting_cells(occupied):
    uploader, values = make_uploader()
    sections = extract_parallelism_rows(str(SAMPLE), ROBOT_SN)
    uploader.gdrive.get_excel_sheet.return_value = [["header"]]
    values.batchUpdate.return_value.execute.side_effect = TimeoutError("write timeout")
    with pytest.raises(TimeoutError):
        upload_parallelism_results(uploader, "master-id", sections)
    checkpoint = uploader.get_upload_checkpoint()["parallelism_upload"]
    assert checkpoint["complete"] is False
    reserved = checkpoint["writes"]
    values.batchUpdate.return_value.execute.side_effect = None
    # Simulate the server having written data even though its response timed out.
    actual = [write["values"] for write in reserved]
    if occupied:
        actual = [[["another upload"]]]
    values.get.return_value.execute.side_effect = [{"values": rows} for rows in actual]
    if occupied:
        with pytest.raises(RuntimeError, match="重试位置已被修改"):
            upload_parallelism_results(uploader, "master-id", sections)
        assert values.batchUpdate.call_count == 1
    else:
        upload_parallelism_results(uploader, "master-id", sections)
        assert values.batchUpdate.call_args.kwargs["body"]["data"] == reserved
        assert uploader.get_upload_checkpoint()["parallelism_upload"]["complete"] is True


def test_leveling_requires_master_id_before_template_upload():
    context = SimpleNamespace(config_repo=MagicMock())
    context.config_repo.get_upload_config.return_value = {"ifupdate": True}
    uploader = SpreadsheetUploader(context)
    uploader.spreadsheet_workflow.run = MagicMock()
    with pytest.raises(ValueError, match="配置平行度测试总表"):
        uploader.upload({"upload_config_key": "robot_update_leveling"})
    uploader.spreadsheet_workflow.run.assert_not_called()


def test_manual_menu_checks_detected_type_without_overriding_csv_metadata():
    valid = extract_csv(str(SAMPLE), meta={"expected_upload_config_key": "robot_update_leveling"})
    assert valid["error"] == "False"
    mismatch = extract_csv(str(SAMPLE), meta={"expected_upload_config_key": "robot_update_z_stage"})
    assert "类型与所选菜单不匹配" in mismatch["error"]


def test_master_id_persists_per_environment_and_reloads_for_existing_workers(tmp_path):
    for env in ("production", "debug"):
        (tmp_path / f"upload_{env}.yaml").write_text("last_row: F:I\nrobot_update_leveling:\n- ifupdate: true\n")
    worker = ConfigRepository(tmp_path, "production")
    editor = ConfigRepository(tmp_path, "production")
    assert editor.update_parallelism_spreadsheet_id("https://docs.google.com/spreadsheets/d/master-id/edit#gid=0") == "master-id"
    assert worker.get_upload_config("robot_update_leveling")["parallelism_spreadsheet_id"] == "master-id"
    assert ConfigRepository(tmp_path, "debug").get_parallelism_spreadsheet_id() == ""
    with pytest.raises(ValueError):
        editor.update_parallelism_spreadsheet_id("invalid id")
    assert ConfigRepository(tmp_path, "production").get_parallelism_spreadsheet_id() == "master-id"


@pytest.mark.parametrize("write_fails", [False, True])
def test_parallelism_runs_before_database_even_when_combined_tests_are_incomplete(write_fails):
    uploader = MagicMock()
    uploader.get_upload_checkpoint.return_value = {
        "spreadsheet_id": "working-sheet", "spreadsheet_link": "working-link",
        "spreadsheet_written": True, "spreadsheet_archived": True,
        "raw_data_result": {"url": "N/A", "name": ""},
    }
    parallelism_writer = MagicMock(side_effect=RuntimeError("write failed") if write_fails else None)
    calls = []

    def record_writer(_payload):
        parallelism_writer.assert_called_once()
        calls.append("database")
        return {"saved": True, "workflow_complete": False, "missing_tests": ["diagnostic"]}

    plan = SpreadsheetUploadPlan(
        yaml_cfg={"ifupdate": True, "ifcopydata": [], "ifpaste": []},
        result=UploadResult.base(sn=ROBOT_SN, model="Robot", production_type="Opentrons"),
        file_desc={"file_path": str(SAMPLE), "upload_config_key": "robot_update_leveling"},
        template_id="template", new_filename="name", timestamp="timestamp",
        spreadsheet_strategy="reuse_within_workflow", csv_sheet_name="Leveling", csv_range=["A-AP"],
        tracker_sheet_name="Opentrons OT3", result_cell="A1", total_result_cell=None,
        record_writer=record_writer, parallelism_writer=parallelism_writer,
    )
    result = SpreadsheetUploadWorkflow(uploader).run(plan)
    parallelism_writer.assert_called_once()
    if write_fails:
        assert "平行度测试总表写入失败" in result["error"]
        assert calls == []
    else:
        assert calls == ["database"]
        assert result["missing_tests"] == ["diagnostic"]


@pytest.mark.parametrize("extra_rows", [0, 2, 1001])
def test_leveling_pastes_whole_source_into_template_before_master(monkeypatch, tmp_path, extra_rows):
    with SAMPLE.open(encoding="utf-8-sig", newline="") as source:
        source_rows = list(csv.reader(source))
    if extra_rows:
        # A source wider than A:AP, with quoted/multiline cells and a blank row.
        extra = ["metadata", "quoted, note\nsecond line", *([""] * 47), "last-column"]
        source_rows = [extra] * (extra_rows - 1) + [[]] + source_rows
    path = tmp_path / "leveling.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        csv.writer(output).writerows(source_rows)

    context = SimpleNamespace(gdrive=MagicMock(), config_repo=MagicMock(), upload_checkpoint={})
    cfg = ConfigRepository.from_environment("production").get_upload_config("robot_update_leveling")
    cfg.update({"parallelism_spreadsheet_id": "master-id", "last_row": "D:G", "Range": ["A-B"], "ifcopydata": []})
    context.config_repo.get_upload_config.return_value = cfg
    context.gdrive.get_sheet_info.return_value = [{
        "title": "Leveling", "sheet_id": 42,
        "grid_properties": {"rowCount": 10, "columnCount": 26},
    }]
    context.gdrive.update_excel_sheet_page_batch.return_value = True
    uploader = SpreadsheetUploader(context)
    uploader.cleanup_incomplete_combined_workflow_if_needed = lambda *_args: {}
    uploader.query_reusable_csv_link = lambda *_args: None
    uploader.get_or_copy_spreadsheet = MagicMock(return_value=("working-sheet", "working-link"))
    uploader.move_spreadsheet_to_month = lambda *_args, **_kwargs: True
    uploader.upload_raw_data = lambda *_args, **_kwargs: {"url": "N/A"}
    uploader.save_upload_result_to_database = lambda *_args: {
        "saved": True, "workflow_complete": False, "missing_tests": ["diagnostic"],
    }
    uploader.log_upload_links = lambda *_args: None
    checked = []

    def check_raw_data_before_master(_uploader, master_id, _sections, *, last_row_range):
        assert master_id == "master-id"
        assert last_row_range == "D:G"
        write = context.gdrive.update_excel_sheet_page_batch.call_args.kwargs
        assert write["spreadsheet_id"] == "working-sheet"
        assert write["sheet_name"] == "Leveling"
        actual = [row for batch in write["new_values"] for row in batch]
        width = max(map(len, source_rows))
        assert actual == [row + [""] * (width - len(row)) for row in source_rows]
        end_column = "AP" if extra_rows == 0 else "AX"
        assert write["ranges"][0] == f"!A1:{end_column}{min(1000, len(source_rows))}"
        assert write["ranges"][-1].endswith(f":{end_column}{len(source_rows)}")
        expansion = context.gdrive.sheet_service_client.spreadsheets.return_value.batchUpdate.call_args.kwargs
        assert expansion["spreadsheetId"] == "working-sheet"
        assert expansion["body"]["requests"] == [
            {"appendDimension": {"sheetId": 42, "dimension": "ROWS", "length": len(source_rows) - 10}},
            {"appendDimension": {"sheetId": 42, "dimension": "COLUMNS", "length": width - 26}},
        ]
        checked.append(True)

    monkeypatch.setattr(
        "modules.uploads.handler.uploaders.spreadsheet_uploader.upload_parallelism_results",
        check_raw_data_before_master,
    )
    result = uploader.upload({
        "upload_config_key": "robot_update_leveling", "sn": ROBOT_SN,
        "model": "Robot", "file_path": str(path),
    })
    assert checked == [True]
    assert result["database_saved"] is True
    uploader.get_or_copy_spreadsheet.assert_called_once()
