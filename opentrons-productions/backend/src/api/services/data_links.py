from __future__ import annotations

from datetime import datetime
from typing import Any

import settings as setting
from api.services.logging import logger
from upload_handler.models import Productions, TestTypes
from upload_handler.product_catalog import (
    get_upload_config_key,
    get_upload_handler_config,
)
from upload_handler.repositories.config_repository import ConfigRepository


SPREADSHEET_URL_TEMPLATE = "https://docs.google.com/spreadsheets/d/{file_id}/edit#gid=0"
DRIVE_FOLDER_URL_TEMPLATE = "https://drive.google.com/drive/folders/{file_id}"

PRODUCTS_WITH_UPLOAD_LINKS = (
    Productions.P50S,
    Productions.P1000S,
    Productions.P50M,
    Productions.P1000M,
    Productions.P2HH,
    Productions.P1KH,
)

TEST_TYPES_WITH_UPLOAD_LINKS = (
    TestTypes.Gravimetric,
    TestTypes.Assembly_QC,
    TestTypes.Speed_Current_Test,
    TestTypes.BurnIn_Result,
    TestTypes.BurnIn_Record,
)

OEM_LABELS = {
    "default": "默认模版",
    "opentrons": "Opentrons 模版",
    "ultima": "Ultima 模版",
    "millipore": "Millipore 模版",
}


def get_data_links() -> dict:
    try:
        now = datetime.now()
        config_repo = ConfigRepository.from_environment(setting.ENVIRONMENT)
        warnings: list[str] = []
        links: list[dict[str, Any]] = []

        for product in PRODUCTS_WITH_UPLOAD_LINKS:
            for test_type in TEST_TYPES_WITH_UPLOAD_LINKS:
                try:
                    config_key = get_upload_config_key(product.value, test_type)
                    yaml_cfg = config_repo.get_upload_config(config_key)
                except ValueError:
                    continue
                except Exception as exc:
                    warnings.append(f"{product.value} {test_type.value}: {exc}")
                    continue

                links.append(
                    build_data_link_entry(
                        product=product.value,
                        test_type=test_type.value,
                        config_key=config_key,
                        yaml_cfg=yaml_cfg,
                        current_month=now.month,
                    )
                )

        return {
            "environment": config_repo.environment,
            "config_file": config_repo.config_file_name,
            "current_date": now.strftime("%Y-%m-%d"),
            "current_month": now.month,
            "links": links,
            "total": len(links),
            "warnings": warnings,
            "error": None,
        }
    except Exception as exc:
        logger.error(f"Error building data links: {str(exc)}", exc_info=True)
        return {
            "environment": setting.ENVIRONMENT,
            "config_file": None,
            "current_date": datetime.now().strftime("%Y-%m-%d"),
            "current_month": datetime.now().month,
            "links": [],
            "total": 0,
            "warnings": [],
            "error": str(exc),
        }


def build_data_link_entry(
    *,
    product: str,
    test_type: str,
    config_key: str,
    yaml_cfg: dict[str, Any],
    current_month: int,
) -> dict[str, Any]:
    handler_config = get_upload_handler_config(config_key)
    return {
        "product": product,
        "test_type": test_type,
        "test_display_name": handler_config.test_display_name,
        "config_key": config_key,
        "templates": build_template_links(yaml_cfg.get("ifcopytemplate")),
        "trackers": build_tracker_links(
            yaml_cfg.get("ifpaste"),
            product=product,
        ),
        "raw_data_folder": build_raw_data_folder_link(
            yaml_cfg.get("ifupdaterawdata"),
            product=product,
            current_month=current_month,
        ),
        "raw_data_parent_folder": build_raw_data_parent_link(
            yaml_cfg.get("ifupdaterawdata"),
            product=product,
        ),
    }


def build_template_links(template_cfg: Any) -> list[dict[str, Any]]:
    if not template_cfg:
        return []

    if isinstance(template_cfg, dict):
        return [
            build_link(
                label=format_template_label(key),
                file_id=value,
                link_type="spreadsheet",
            )
            for key, value in template_cfg.items()
            if value
        ]

    return [
        build_link(
            label="默认模版",
            file_id=template_cfg,
            link_type="spreadsheet",
        )
    ]


def build_tracker_links(paste_cfg_list: Any, *, product: str) -> list[dict[str, Any]]:
    if not isinstance(paste_cfg_list, list):
        return []

    tracker_links: list[dict[str, Any]] = []
    for paste_cfg in paste_cfg_list:
        if not isinstance(paste_cfg, dict) or paste_cfg.get("off/on") is False:
            continue

        default_id = paste_cfg.get("pastefileid")
        if default_id:
            tracker_links.append(
                build_link(
                    label=resolve_tracker_tab_label(
                        paste_cfg,
                        product=product,
                        oem_name="Opentrons",
                    ),
                    file_id=default_id,
                    link_type="spreadsheet",
                )
            )

        ultima_id = paste_cfg.get("Ultimapastefileid")
        if ultima_id:
            tracker_links.append(
                build_link(
                    label=resolve_tracker_tab_label(
                        paste_cfg,
                        product=product,
                        oem_name="Ultima",
                    ),
                    file_id=ultima_id,
                    link_type="spreadsheet",
                )
            )

    return tracker_links


def build_raw_data_folder_link(
    folder_cfg: Any,
    *,
    product: str,
    current_month: int,
) -> dict[str, Any]:
    cfg = resolve_product_folder_cfg(folder_cfg, product)
    month_folder_id = get_month_folder_id(cfg, current_month)
    return build_link(
        label=f"{current_month} 月原数据文件夹",
        file_id=month_folder_id,
        link_type="drive_folder",
        note=None if month_folder_id else "当前 YAML 未配置该月份文件夹",
    )


def build_raw_data_parent_link(folder_cfg: Any, *, product: str) -> dict[str, Any] | None:
    cfg = resolve_product_folder_cfg(folder_cfg, product)
    parent_id = cfg.get("fumulu") if isinstance(cfg, dict) else None
    if not parent_id:
        return None
    return build_link(
        label="原数据父目录",
        file_id=parent_id,
        link_type="drive_folder",
    )


def resolve_product_folder_cfg(folder_cfg: Any, product: str) -> dict[str, Any]:
    if not isinstance(folder_cfg, dict):
        return {}

    for key in (product, product.lower(), product.upper()):
        nested_cfg = folder_cfg.get(key)
        if isinstance(nested_cfg, dict):
            return nested_cfg

    return folder_cfg


def get_month_folder_id(folder_cfg: dict[str, Any], month: int) -> str | None:
    for key in (month, str(month), f"{month:02d}"):
        folder_id = folder_cfg.get(key)
        if folder_id:
            return str(folder_id).strip()
    return None


def resolve_tracker_tab_label(
    paste_cfg: dict[str, Any],
    *,
    product: str,
    oem_name: str,
) -> str:
    tab_name = str(paste_cfg.get("unit_tracker_tab") or "").strip()
    if tab_name:
        return tab_name
    return f"{oem_name} {product}"


def build_link(
    *,
    label: str,
    file_id: Any,
    link_type: str,
    note: str | None = None,
) -> dict[str, Any]:
    normalized_id = normalize_file_id(file_id)
    return {
        "label": label,
        "link_type": link_type,
        "file_id": normalized_id,
        "url": build_url(normalized_id, link_type),
        "available": bool(normalized_id),
        "note": note,
    }


def normalize_file_id(file_id: Any) -> str | None:
    if file_id is None:
        return None
    value = str(file_id).strip()
    return value or None


def build_url(file_id: str | None, link_type: str) -> str | None:
    if not file_id:
        return None
    if file_id.startswith(("http://", "https://")):
        return file_id
    if link_type == "drive_folder":
        return DRIVE_FOLDER_URL_TEMPLATE.format(file_id=file_id)
    return SPREADSHEET_URL_TEMPLATE.format(file_id=file_id)


def format_template_label(key: Any) -> str:
    normalized_key = str(key).strip().lower()
    if normalized_key in OEM_LABELS:
        return OEM_LABELS[normalized_key]
    return f"{str(key).strip()} 模版"
