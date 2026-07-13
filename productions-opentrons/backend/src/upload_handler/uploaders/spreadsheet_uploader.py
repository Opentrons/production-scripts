from settings import DATA_DB_NAME, get_logger
from upload_handler.models import UploadResult
from upload_handler.product_catalog import (
    get_upload_collection_name_from_config_key,
    get_upload_config_key,
    get_upload_handler_config,
)
from upload_handler.uploaders.common import ProductUploaderBase
from upload_handler.uploaders.workflows import SpreadsheetUploadPlan, SpreadsheetUploadWorkflow

logger = get_logger(__name__)


class SpreadsheetUploader(ProductUploaderBase):
    """Generic uploader for CSV-to-template spreadsheet workflows."""

    def __init__(self, context) -> None:
        super().__init__(context)
        self.spreadsheet_workflow = SpreadsheetUploadWorkflow(self)

    def upload(self, file_desc: dict, note_str: str = "") -> dict | None:
        config_key = self._resolve_config_key(file_desc)
        handler_config = get_upload_handler_config(config_key)
        yaml_cfg = self.config_repo.get_upload_config(config_key)
        if not yaml_cfg["ifupdate"]:
            return None

        model = file_desc.get("model")
        device_sn = file_desc.get("sn")
        oem_type = self.normalize_oem_type(file_desc)
        timestamp = self.current_timestamp(handler_config.timestamp_format)
        collection = get_upload_collection_name_from_config_key(model, config_key)
        cleanup_result = self.cleanup_incomplete_combined_workflow_if_needed(
            DATA_DB_NAME,
            collection,
            file_desc,
        )
        if cleanup_result.get("cleaned"):
            drive_cleanup = cleanup_result.get("drive_cleanup") or {}
            logger.info(
                "Reset incomplete combined workflow before upload: workflow=%s "
                "deleted_records=%s stale_drive_links=%s drive_deleted=%s drive_failed=%s",
                cleanup_result.get("workflow"),
                cleanup_result.get("deleted_records"),
                cleanup_result.get("stale_drive_links"),
                len(drive_cleanup.get("deleted", [])),
                len(drive_cleanup.get("failed", [])),
            )
        csv_link = self.query_reusable_csv_link(DATA_DB_NAME, collection, file_desc)
        logger.info(f"Uploading data from {file_desc.get('file_path')}, csv link is {csv_link}")

        total_result_cell = self.resolve_optional_result_cell(yaml_cfg, file_desc)
        return self.spreadsheet_workflow.run(
            SpreadsheetUploadPlan(
                yaml_cfg=yaml_cfg,
                result=UploadResult.base(sn=device_sn, model=model, production_type=oem_type),
                file_desc=file_desc,
                template_id=self.resolve_template_id(yaml_cfg["ifcopytemplate"], file_desc),
                new_filename=self._build_new_filename(
                    handler_config.new_filename_template,
                    sn=device_sn,
                    model=model,
                    timestamp=timestamp,
                    config_key=config_key,
                    test_display_name=handler_config.test_display_name,
                ),
                timestamp=timestamp,
                spreadsheet_strategy=yaml_cfg.get("spreadsheet_strategy", "reuse_within_workflow"),
                csv_sheet_name=yaml_cfg["csv_target_sheet_name"],
                csv_range=yaml_cfg["Range"],
                tracker_sheet_name=self._build_tracker_sheet_name(
                    handler_config.tracker_sheet_name_template,
                    oem=oem_type,
                    model=model,
                ),
                result_cell=self.resolve_result_cell(yaml_cfg, file_desc),
                total_result_cell=total_result_cell,
                csv_link=csv_link,
                is_ultima=self.is_ultima_oem(oem_type),
                sheet_link_index=handler_config.sheet_link_index,
                sheet_link_mode=handler_config.sheet_link_mode,
                require_total_result_for_tracker=bool(total_result_cell),
                record_writer=lambda upload_result: self.save_upload_result_to_database(
                    DATA_DB_NAME,
                    file_desc,
                    upload_result,
                ),
            )
        )

    @staticmethod
    def _resolve_config_key(file_desc: dict) -> str:
        config_key = str(file_desc.get("upload_config_key") or "")
        if config_key:
            return config_key
        return get_upload_config_key(file_desc.get("model"), file_desc.get("test_type"))

    @staticmethod
    def _build_new_filename(
        template: str,
        *,
        sn: str,
        model: str,
        timestamp: str,
        config_key: str,
        test_display_name: str,
    ) -> str:
        test_slug = "-".join(str(test_display_name).split())
        return template.format(
            sn=sn,
            model=model,
            timestamp=timestamp,
            config_key=config_key,
            test_display_name=test_display_name,
            test_slug=test_slug,
        )

    @staticmethod
    def _build_tracker_sheet_name(template: str, *, oem: str, model: str) -> str:
        return template.format(oem=oem, model=model).strip()
