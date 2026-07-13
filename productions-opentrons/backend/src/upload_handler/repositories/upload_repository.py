from __future__ import annotations

from typing import Any

from upload_handler.models import TestTypes, UploadApiResponse, format_production_name
from upload_handler.product_catalog import (
    get_upload_config_key,
    get_upload_handler_config,
)
from upload_handler.uploaders.spreadsheet_uploader import SpreadsheetUploader


class UploadRepository:
    """Unified upload repository.

    Product/test differences are configured in product_catalog by upload config key.
    """

    def __init__(self, uploaders: dict[str, Any]) -> None:
        self.uploaders = uploaders

    @staticmethod
    def get_config_key(file_desc: dict) -> str:
        config_key = str(file_desc.get("upload_config_key") or "")
        if config_key:
            return config_key
        return get_upload_config_key(file_desc.get("model"), file_desc.get("test_type"))

    def supports(self, file_desc: dict, test_type: TestTypes | None = None) -> bool:
        try:
            get_upload_handler_config(self.get_config_key(file_desc))
        except ValueError:
            return False
        return True

    def upload(self, file_desc: dict) -> dict | None:
        config_key = self.get_config_key(file_desc)
        handler_config = get_upload_handler_config(config_key)
        if not handler_config.upload_method:
            raise ValueError(f"Upload method not configured: config_key={config_key}")

        uploader = self.uploaders.get(handler_config.uploader_key)
        if uploader is None:
            raise ValueError(
                f"Uploader not registered: config_key={config_key}, uploader_key={handler_config.uploader_key}"
            )

        upload_method = getattr(uploader, handler_config.upload_method, None)
        if not callable(upload_method):
            raise ValueError(
                f"Upload method not found: config_key={config_key}, method={handler_config.upload_method}"
            )

        return upload_method(file_desc)

    def build_message(self, result: dict, file_desc: dict) -> UploadApiResponse:
        config_key = self.get_config_key(file_desc)
        handler_config = get_upload_handler_config(config_key)
        return {
            "production_name": format_production_name(
                result.get("type", ""),
                result.get("model") or file_desc.get("model", ""),
            ),
            "test_type": handler_config.test_display_name,
            "test_result": result.get("total_result", ""),
            "sn": result.get("sn") or file_desc.get("sn", ""),
            "csv_link": result.get("csv_link") or "",
            "unit_tracker": result.get("unit_tracker"),
        }


def default_upload_repositories(context) -> list[UploadRepository]:
    return [
        UploadRepository(
            uploaders={
                "spreadsheet": SpreadsheetUploader(context),
            }
        )
    ]


def resolve_upload_repository(
    upload_repositories: list[UploadRepository],
    file_desc: dict,
    test_type: TestTypes | None = None,
) -> UploadRepository | None:
    for repository in upload_repositories:
        if repository.supports(file_desc, test_type):
            return repository
    return None
