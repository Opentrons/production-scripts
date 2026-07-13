from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from settings import DATA_DB_NAME, get_logger
from upload_handler.models import UploadResult
from upload_handler.product_catalog import get_upload_config_key, get_upload_database_config

logger = get_logger(__name__)


PasteFileResolver = Callable[[dict], str]
ResultCellResolver = Callable[[dict], str]
RecordWriter = Callable[[dict], dict]


@dataclass
class SpreadsheetUploadPlan:
    yaml_cfg: dict
    result: UploadResult
    file_desc: dict
    template_id: str
    new_filename: str
    timestamp: str
    spreadsheet_strategy: str
    csv_sheet_name: str
    csv_range: list
    tracker_sheet_name: str
    result_cell: str | ResultCellResolver
    total_result_cell: str | None
    record_writer: RecordWriter
    csv_link: str | None = None
    is_ultima: bool = False
    model_key: str | None = None
    sheet_link_index: int = 0
    sheet_link_mode: str = "insert"
    paste_file_resolver: PasteFileResolver | None = None
    require_total_result_for_tracker: bool = True


class SpreadsheetUploadWorkflow:
    """Runs the common copy/upload/summary/paste/finalize flow."""

    def __init__(self, uploader) -> None:
        self.uploader = uploader

    def run(self, plan: SpreadsheetUploadPlan) -> dict | None:
        if not plan.yaml_cfg["ifupdate"]:
            return None

        updatefileid, sheetlink = self._prepare_spreadsheet(plan)
        if not updatefileid:
            return plan.result.to_dict()

        logger.info(f"Coping datas to {plan.csv_sheet_name}")
        upload_ok = self.uploader.upload_csv_to_spreadsheet(
            updatefileid,
            plan.csv_sheet_name,
            plan.file_desc.get("file_path"),
            plan.csv_range,
        )
        self._set_upload_result(plan, upload_ok=upload_ok)
        plan.result.set_csv_link(sheetlink)
        logger.info("template coping finished" if upload_ok else f"更新文件：失败 {plan.yaml_cfg}")

        if not upload_ok:
            return plan.result.to_dict()

        copy_data_list = self.uploader.copy_summary_ranges(
            plan.yaml_cfg,
            updatefileid,
            is_ultima=plan.is_ultima,
        )
        self._copy_test_result(plan, updatefileid, use_total_result_cell=False)

        self.uploader.move_spreadsheet_to_month(plan.yaml_cfg, updatefileid, model_key=plan.model_key)
        raw_data = self.uploader.upload_raw_data(
            plan.yaml_cfg,
            plan.result.sn,
            plan.timestamp,
            plan.file_desc.get("zip_file"),
            model_key=plan.model_key,
        )
        plan.result.set_raw_data(
            raw_data.get("url", "N/A"),
            raw_data.get("name", ""),
        )
        database_status = plan.record_writer(plan.result.to_db_dict())
        database_saved = bool(database_status.get("saved"))
        plan.result.set_database_saved(database_saved)
        if not database_saved:
            database_error = database_status.get("error") or "Database upload failed"
            logger.error("Upload result was not saved to database: %s", database_error)
            plan.result.set_unit_tracker_status(database_error)
            plan.result.set_error(database_error)
            return plan.result.to_dict()

        workflow_complete = bool(database_status.get("workflow_complete"))
        if workflow_complete and plan.total_result_cell:
            self._copy_test_result(plan, updatefileid, use_total_result_cell=True)

        missing_tests = database_status.get("missing_tests", [])
        if not workflow_complete:
            status = f"Waiting for combined tests: {', '.join(missing_tests)}"
            logger.info(status)
            plan.result.set_unit_tracker("N/A")
            plan.result.set_unit_tracker_status(status, missing_tests=missing_tests)
            self.uploader.log_upload_links(sheetlink, "N/A")
            return plan.result.to_dict()

        if database_status.get("unit_tracker_uploaded"):
            tracking_sheet = database_status.get("unit_tracker_link") or "N/A"
            status = "Unit Tracker already uploaded for this workflow"
            logger.info(status)
            plan.result.set_unit_tracker(tracking_sheet)
            plan.result.set_unit_tracker_status(status)
            self.uploader.log_upload_links(sheetlink, tracking_sheet)
            return plan.result.to_dict()

        tracking_sheet = self._paste_to_tracker(plan, copy_data_list, sheetlink)
        if tracking_sheet and tracking_sheet != "NA":
            if self.uploader.mark_unit_tracker_uploaded(
                db_name=DATA_DB_NAME,
                file_desc=plan.file_desc,
                unit_tracker_link=tracking_sheet,
            ):
                plan.result.set_unit_tracker_status("Uploaded to Unit Tracker")
        else:
            plan.result.set_unit_tracker_status("Unit Tracker append skipped or failed")

        self.uploader.log_upload_links(sheetlink, tracking_sheet)
        return plan.result.to_dict()

    def _prepare_spreadsheet(self, plan: SpreadsheetUploadPlan) -> tuple[str | None, str | None]:
        if plan.spreadsheet_strategy == "always_new":
            return self.uploader.copy_new_spreadsheet(plan.template_id, plan.new_filename)
        if plan.spreadsheet_strategy == "reuse_within_workflow":
            return self.uploader.get_or_copy_spreadsheet(
                plan.csv_link,
                plan.template_id,
                plan.new_filename,
            )
        raise ValueError(f"Unsupported spreadsheet strategy: {plan.spreadsheet_strategy}")

    def _set_upload_result(self, plan: SpreadsheetUploadPlan, **kwargs) -> None:
        db_config = get_upload_database_config(self._resolve_config_key(plan))
        plan.result.set_test_result(
            upload_flag_field=db_config.upload_flag_field,
            **kwargs,
        )

    def _copy_test_result(
        self,
        plan: SpreadsheetUploadPlan,
        updatefileid: str,
        *,
        use_total_result_cell: bool,
    ) -> None:
        result_cell = self._resolve_cell(plan.result_cell, plan.file_desc)
        for copy_cfg in plan.yaml_cfg["ifcopydata"]:
            if not copy_cfg["off/on"]:
                continue
            sheet_name = copy_cfg["summary_source_sheet_name"]
            logger.info(
                "Reading test result from %s (result_cell=%s, use_total_result_cell=%s)",
                sheet_name,
                result_cell,
                use_total_result_cell,
            )
            result_value = self.uploader.get_sheet_cell_value(updatefileid, sheet_name, result_cell)
            total_result = result_value
            if use_total_result_cell and plan.total_result_cell:
                total_result = self.uploader.get_sheet_cell_value(
                    updatefileid,
                    sheet_name,
                    plan.total_result_cell,
                )
            self._set_upload_result(
                plan,
                upload_ok=True,
                total_result=total_result,
            )

    def _paste_to_tracker(self, plan: SpreadsheetUploadPlan, copy_data_list: list, sheetlink: str) -> str:
        tracking_sheet = "NA"
        for index, paste_cfg in enumerate(plan.yaml_cfg["ifpaste"]):
            if not paste_cfg["off/on"]:
                continue
            if plan.require_total_result_for_tracker and not plan.result.total_result:
                logger.warning("total_result is empty, skip this step")
                plan.result.set_unit_tracker("N/A")
                continue

            paste_file_id = self._resolve_paste_file_id(plan, paste_cfg)
            tracker_sheet_name = self.uploader.resolve_tracker_sheet_name(
                paste_cfg,
                plan.tracker_sheet_name,
            )
            tracker_sheet_name, _ = self.uploader.resolve_sheet_name(
                paste_file_id,
                tracker_sheet_name,
            )
            values = self.uploader.gdrive.get_excel_sheet(
                spreadsheetId=paste_file_id,
                range=tracker_sheet_name,
            )
            if not values:
                logger.warning(f"Cannot read tracker sheet: {tracker_sheet_name}")
                plan.result.set_unit_tracker("N/A")
                continue

            last_row_index = self.uploader.find_last_row_by_length(values)
            paste_range, _, _ = self.uploader.resolve_paste_line_range(
                paste_cfg,
                last_row_index,
                plan.is_ultima,
            )
            logger.info(f"Trying to paste result to {tracker_sheet_name}")
            if self.uploader.paste_row_to_tracker(
                paste_file_id,
                tracker_sheet_name,
                paste_range,
                copy_data_list[index][0],
                sheet_link=sheetlink,
                sheet_link_index=plan.sheet_link_index,
                sheet_link_mode=plan.sheet_link_mode,
            ):
                logger.info("Update unit tracker successful")
                tracking_sheet = self.uploader.build_tracking_sheet_link(
                    paste_file_id,
                    tracker_sheet_name,
                )
                plan.result.set_unit_tracker(tracking_sheet)
            else:
                logger.error("Update unit tracker failed")
                plan.result.set_unit_tracker("N/A")
        return tracking_sheet

    def _resolve_paste_file_id(self, plan: SpreadsheetUploadPlan, paste_cfg: dict) -> str:
        if plan.paste_file_resolver:
            return plan.paste_file_resolver(paste_cfg)
        return self.uploader.resolve_paste_file_id(paste_cfg, plan.is_ultima)

    @staticmethod
    def _resolve_cell(cell: str | ResultCellResolver, file_desc: dict) -> str:
        if callable(cell):
            return cell(file_desc)
        return cell

    @staticmethod
    def _resolve_config_key(plan: SpreadsheetUploadPlan) -> str:
        config_key = str(plan.file_desc.get("upload_config_key") or "")
        if config_key:
            return config_key
        return get_upload_config_key(plan.file_desc.get("model"), plan.file_desc.get("test_type"))
