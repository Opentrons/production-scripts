from __future__ import annotations

from unittest.mock import MagicMock

from modules.uploads.handler.models import UploadResult
from modules.uploads.handler.product_catalog import UPLOAD_HANDLER_CONFIGS
from modules.uploads.handler.uploaders.common import ProductUploaderBase
from modules.uploads.handler.uploaders.workflows import SpreadsheetUploadPlan, SpreadsheetUploadWorkflow

SHEET_LINK = "https://docs.google.com/spreadsheets/d/new-sheet/edit#gid=0"
YAML_CFG = {
    "ifupdate": True,
    "ifcopydata": [{"off/on": True, "summary_source_sheet_name": "Summary", "copyRange": ["!B4:Z4"]}],
    "ifpaste": [{"off/on": True, "pastefileid": "tracker", "pastelineRange": {"star": "J", "end": "AI"}}],
}


def test_robot_configs_write_new_sheet_link_to_summary_a4() -> None:
    robot_keys = [key for key in UPLOAD_HANDLER_CONFIGS if key.startswith("robot_update_")]
    assert len(robot_keys) == 5
    assert {UPLOAD_HANDLER_CONFIGS[key].summary_link_cell for key in robot_keys} == {"A4"}


def test_write_summary_sheet_link_overwrites_summary_cell() -> None:
    uploader = ProductUploaderBase.__new__(ProductUploaderBase)
    uploader.context = MagicMock()
    uploader.context.gdrive.update_excel_sheet_page_batch.return_value = True

    assert uploader.write_summary_sheet_link(YAML_CFG, "new-sheet", "A4", SHEET_LINK) is True
    uploader.context.gdrive.update_excel_sheet_page_batch.assert_called_once_with(
        spreadsheet_id="new-sheet",
        sheet_name="Summary",
        ranges="!A4",
        new_values=[[SHEET_LINK]],
    )


def _plan(summary_link_cell: str = "A4") -> SpreadsheetUploadPlan:
    return SpreadsheetUploadPlan(
        yaml_cfg=YAML_CFG,
        result=UploadResult.base(sn="FLXA3020261119001", model="Robot", production_type="Opentrons"),
        file_desc={"file_path": "robot.csv", "model": "Robot"},
        template_id="template",
        new_filename="FLXA3020261119001-RobotAssembly-20261123",
        timestamp="20261123",
        spreadsheet_strategy="always_new",
        csv_sheet_name="Z-Stage",
        csv_range=["A"],
        tracker_sheet_name="Opentrons OT3",
        result_cell="!B18:B18",
        total_result_cell=None,
        summary_link_cell=summary_link_cell,
        require_total_result_for_tracker=False,
        record_writer=lambda _payload: {"saved": True, "workflow_complete": True},
    )


def _uploader() -> MagicMock:
    uploader = MagicMock()
    uploader.get_upload_checkpoint.return_value = {}
    uploader.copy_new_spreadsheet.return_value = ("new-sheet", SHEET_LINK)
    uploader.upload_csv_to_spreadsheet.return_value = True
    uploader.write_summary_sheet_link.return_value = True
    uploader.copy_summary_ranges.return_value = [[["ZS1", "PASS"]]]
    uploader.get_sheet_cell_value.return_value = "PASS"
    uploader.pick_config_value.return_value = "N/A"
    uploader.move_spreadsheet_to_month.return_value = True
    uploader.upload_raw_data.return_value = {"url": "N/A"}
    uploader.resolve_tracker_sheet_name.return_value = "Opentrons OT3"
    uploader.resolve_sheet_name.return_value = ("Opentrons OT3", None)
    uploader.resolve_paste_line_range.return_value = ("!J20:AI20", "J", "AI")
    uploader.get_first_blank_tracker_row.return_value = 20
    uploader.ensure_tracker_row_capacity.return_value = True
    uploader.paste_row_to_tracker.return_value = True
    uploader.build_tracking_sheet_link.return_value = "tracker-link"
    uploader.mark_unit_tracker_uploaded.return_value = True
    return uploader


def test_workflow_writes_summary_link_before_copying_summary_row() -> None:
    uploader = _uploader()
    workflow = SpreadsheetUploadWorkflow(uploader)
    workflow._set_upload_result = lambda plan, **kwargs: None

    result = workflow.run(_plan())

    assert not result.get("error"), result
    names = [call[0] for call in uploader.mock_calls]
    assert names.index("write_summary_sheet_link") < names.index("copy_summary_ranges")
    uploader.write_summary_sheet_link.assert_called_once_with(YAML_CFG, "new-sheet", "A4", SHEET_LINK)
    assert uploader.paste_row_to_tracker.call_args.kwargs["sheet_link"] == SHEET_LINK


def test_workflow_stops_when_summary_link_cannot_be_written() -> None:
    uploader = _uploader()
    uploader.write_summary_sheet_link.return_value = False
    uploader.gdrive.last_error = "quota"
    workflow = SpreadsheetUploadWorkflow(uploader)
    workflow._set_upload_result = lambda plan, **kwargs: None

    result = workflow.run(_plan())

    assert "A4" in result["error"]
    uploader.copy_summary_ranges.assert_not_called()
    uploader.paste_row_to_tracker.assert_not_called()


def test_workflow_skips_summary_link_when_not_configured() -> None:
    uploader = _uploader()
    workflow = SpreadsheetUploadWorkflow(uploader)
    workflow._set_upload_result = lambda plan, **kwargs: None

    workflow.run(_plan(summary_link_cell=""))

    uploader.write_summary_sheet_link.assert_not_called()
