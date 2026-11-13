from __future__ import annotations

import io
import unicodedata
from collections.abc import Iterable
from typing import Any

from openpyxl import load_workbook

from core.google import GoogleDriver
from modules.supplies.models import SupplementaryMaterialCreate


class SupplementaryMaterialSourceError(ValueError):
    pass


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def parse_material_rows(rows: Iterable[Iterable[Any]]) -> list[SupplementaryMaterialCreate]:
    """Scan from row one and stop at the first completely empty row."""
    aliases = {
        "material_number": {"物料编号", "料号", "物料号", "materialnumber", "partnumber", "cpn", "pn"},
        "english_name": {"英文名称", "英文名", "englishname"},
        "chinese_name": {"中文名称", "中文名", "chinesename"},
        "eid": {"eid"},
    }
    columns = {"material_number": 0, "english_name": 1, "chinese_name": 2, "eid": 3}
    materials: dict[str, SupplementaryMaterialCreate] = {}
    for row_number, row in enumerate(rows, 1):
        cells = [_cell_text(value) for value in row]
        if not any(cells):
            break
        if row_number == 1:
            headers = ["".join(unicodedata.normalize("NFKC", value).casefold().split()).replace("/", "").replace("_", "") for value in cells]
            detected = {
                field: next((index for index, header in enumerate(headers) if header in names), -1)
                for field, names in aliases.items()
            }
            if detected["material_number"] >= 0:
                columns = detected
                continue
        values = {field: cells[index] if 0 <= index < len(cells) else "" for field, index in columns.items()}
        if not values["material_number"]:
            raise SupplementaryMaterialSourceError(f"辅料原表第 {row_number} 行有内容但物料编号为空")
        values["material_number"] = unicodedata.normalize("NFKC", values["material_number"]).upper()
        material = SupplementaryMaterialCreate(**values)
        previous = materials.get(material.material_number)
        if previous is not None and previous != material:
            raise SupplementaryMaterialSourceError(f"辅料原表第 {row_number} 行料号重复且内容不一致：{material.material_number}")
        materials[material.material_number] = material
    if not materials:
        raise SupplementaryMaterialSourceError("辅料原表在首个空行之前没有有效料号，已保留原有数据")
    return list(materials.values())


class GoogleSupplementaryMaterialSource:
    def __init__(self, driver: GoogleDriver, spreadsheet_id: str, sheet_gid: int, sheet_title: str) -> None:
        self.driver = driver
        self.spreadsheet_id = spreadsheet_id
        self.sheet_gid = sheet_gid
        self.sheet_title = sheet_title

    @property
    def source_url(self) -> str:
        return f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/edit?gid={self.sheet_gid}#gid={self.sheet_gid}"

    def read(self) -> list[SupplementaryMaterialCreate]:
        metadata = self.driver.get_file_metadata(self.spreadsheet_id)
        if metadata.mime_type == "application/vnd.google-apps.spreadsheet":
            sheet = self.driver.read_sheet_by_gid(self.spreadsheet_id, self.sheet_gid)
            return parse_material_rows(sheet.values)
        if metadata.mime_type != "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
            raise SupplementaryMaterialSourceError("辅料原表须为 Google Sheets 或 Excel .xlsx 文件")
        _, content = self.driver.download_file_bytes(self.spreadsheet_id)
        return self.read_excel_bytes(content)

    def read_excel_bytes(self, content: bytes) -> list[SupplementaryMaterialCreate]:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        try:
            if self.sheet_title not in workbook.sheetnames:
                raise SupplementaryMaterialSourceError(f"辅料原文件中没有“{self.sheet_title}”工作表")
            return parse_material_rows(workbook[self.sheet_title].iter_rows(values_only=True))
        finally:
            workbook.close()
