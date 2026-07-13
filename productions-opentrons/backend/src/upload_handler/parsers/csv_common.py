import csv
from pathlib import Path
from typing import Any, Dict

from upload_handler.product_catalog import (
    SERIAL_NUMBER_MODEL_MAPPING,
    get_model_from_serial_number,
    get_oem_type_from_text,
)
from upload_handler.parsers.definitions import (
    CsvFieldDefinition,
    CsvFinishDefinition,
    CsvParserDefinition,
    CsvSectionDefinition,
    FinishRange,
)


MODEL_MAPPING = {
    pattern: production.value
    for pattern, production in SERIAL_NUMBER_MODEL_MAPPING.items()
}

META_START_PATTERNS = {
    "META_DATA_START",
    "METADATA",
    "META-DATA-START",
    "META DATA START",
    "META_DATA",
    "METADATA_START",
}

META_END_PATTERNS = {
    "META_DATA_END",
    "METADATA_END",
    "META-DATA-END",
    "META DATA END",
    "-------------------",
    "--------------------",
}

METADATA_FALLBACK_SCAN_ROWS = 10
KEY_COLUMN = "B"
VALUE_COLUMN = "C"


def build_default_parse_result(file_path: str, finished: bool = True) -> Dict[str, Any]:
    return {
        "metadata": {},
        "finished": finished,
        "file_name": Path(file_path).name,
        "sn": "",
        "model": "NA",
        "kind_stage_type": "Production",
        "kind_oem_type": "NA",
        "test_type": "NA",
        "error": "False",
    }


def iter_csv_key_values(file_path: str):
    with open(file_path, "r", encoding="utf-8-sig") as csv_file:
        reader = csv.reader(csv_file)
        for row in reader:
            if not row or all(cell == "" for cell in row) or len(row) < 2:
                continue
            key = row[1].strip() if len(row) > 1 else ""
            value = row[2].strip() if len(row) > 2 else ""
            yield key, value


def read_csv_rows(file_path: str) -> list[list[str]]:
    with open(file_path, "r", encoding="utf-8-sig") as csv_file:
        return list(csv.reader(csv_file))


def column_index(column_name: str) -> int:
    column_name = str(column_name).strip().upper()
    index = 0
    for char in column_name:
        if not ("A" <= char <= "Z"):
            raise ValueError(f"Invalid CSV column name: {column_name}")
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index - 1


def get_cell(row: list[str], column_name: str) -> str:
    index = column_index(column_name)
    if index >= len(row):
        return ""
    return str(row[index]).strip()


def parse_numeric_value(value: str) -> Any:
    if not value:
        return value

    try:
        if "E" in value.upper() or "e" in value:
            return float(value)
        if "." in value:
            return float(value)
        return int(value)
    except (ValueError, TypeError):
        return value


def normalize_metadata_key(key: str) -> str:
    return "".join(char for char in str(key).lower() if char.isalnum())


def is_test_name_key(key: str) -> bool:
    return normalize_metadata_key(key) == "testname"


def normalize_metadata_value(value: str) -> Any:
    return None if value in ("None", "") else parse_numeric_value(value)


def find_metadata_rows(rows: list[list[str]]) -> tuple[list[list[str]], bool]:
    in_metadata = False
    metadata_rows = []

    for row in rows:
        key = get_cell(row, KEY_COLUMN)
        normalized_key = key.upper()
        if not in_metadata and normalized_key in META_START_PATTERNS:
            in_metadata = True
            continue
        if in_metadata and normalized_key in META_END_PATTERNS:
            return metadata_rows, True
        if in_metadata:
            metadata_rows.append(row)

    return metadata_rows, False


def extract_meta_data_from_csv(file_path: str) -> Dict[str, Any]:
    try:
        rows = read_csv_rows(file_path)
        metadata_rows, found_metadata_range = find_metadata_rows(rows)
        if not found_metadata_range:
            metadata_rows = rows[:METADATA_FALLBACK_SCAN_ROWS]

        metadata = {}
        for row in metadata_rows:
            key = get_cell(row, KEY_COLUMN)
            value = get_cell(row, VALUE_COLUMN)
            if key:
                normalized_value = normalize_metadata_value(value)
                metadata[key] = normalized_value
                if is_test_name_key(key):
                    metadata["test_name"] = normalized_value
        return metadata
    except FileNotFoundError:
        return {"error": f"文件未找到: {file_path}", "failed": True}
    except Exception as exc:
        return {"error": str(exc), "failed": True}


def extract_model_from_sn(sn: str, model_mapping: Dict[str, str] = MODEL_MAPPING) -> str:
    if model_mapping != MODEL_MAPPING:
        from re import escape, search

        for model_pattern, model_name in model_mapping.items():
            if search(escape(model_pattern), sn):
                return model_name
    return get_model_from_serial_number(sn)


def parse_operator_kind(operator_name: str):
    if not operator_name or operator_name == "None":
        return "NA", get_oem_type_from_text(operator_name)
    try:
        parts = operator_name.split(".")
        kind_parts = parts[1:]
        oem_type = get_oem_type_from_text(operator_name)
        if "Production" in kind_parts and len(kind_parts) >= 2:
            return "Production", oem_type
        return parts[2], oem_type
    except Exception:
        return "NA", get_oem_type_from_text(operator_name)


def iter_section_key_values(
    rows: list[list[str]],
    section: CsvSectionDefinition,
    key_name_loc: str | None = None,
    value_loc: str | None = None,
):
    key_column = key_name_loc or section.key_name_loc
    value_column = value_loc or section.value_loc
    in_section = False
    for row in rows:
        section_key = get_cell(row, section.key_name_loc)
        key = get_cell(row, key_column)
        value = get_cell(row, value_column)
        if not in_section and section_key == section.start:
            in_section = True
            continue
        if in_section and section_key == section.end:
            break
        if in_section and key:
            yield key, value


def extract_section(rows: list[list[str]], section: CsvSectionDefinition) -> Dict[str, Any]:
    values = {}
    for key, value in iter_section_key_values(rows, section):
        values[key] = None if value == "None" else value
    return values


def find_field_value(
    rows: list[list[str]],
    definition: CsvParserDefinition,
    field: CsvFieldDefinition,
    meta: dict[str, Any] | None = None,
) -> str:
    if field.source == "metadata" and meta:
        for key_name in field.key_names:
            value = meta.get(key_name)
            if value is None:
                continue
            value = str(value).strip()
            for extra_word in field.extra_words:
                value = value.replace(extra_word, "")
            if value and value != "None":
                return value

    section = definition.metadata_range if field.source == "metadata" else definition.config_range
    if section is None:
        return ""

    source_values = {
        key: value
        for key, value in iter_section_key_values(
            rows,
            section,
            key_name_loc=field.key_name_loc,
            value_loc=field.value_loc,
        )
    }
    for key_name in field.key_names:
        value = source_values.get(key_name)
        if value is None:
            continue
        value = str(value).strip()
        for extra_word in field.extra_words:
            value = value.replace(extra_word, "")
        if value and value != "None":
            return value
    return ""


def row_matches_finish_rule(key: str, finish_range: CsvFinishDefinition) -> bool:
    if not key or key in finish_range.ignore_keys:
        return False
    if finish_range.key_contains_all and not all(text in key for text in finish_range.key_contains_all):
        return False
    if finish_range.key_contains_any and not any(text in key for text in finish_range.key_contains_any):
        return False
    return True


def evaluate_finished(rows: list[list[str]], finish_range: FinishRange, default: bool) -> bool:
    if callable(finish_range):
        return finish_range(rows)

    values = []
    in_section = False
    danger_words = {str(word).strip().lower() for word in finish_range.danger_words}

    for row in rows:
        key = get_cell(row, finish_range.key_name_loc)
        value = get_cell(row, finish_range.value_loc)
        if not in_section and key == finish_range.start:
            in_section = True
            continue
        if in_section and key == finish_range.end:
            break
        if not in_section or not row_matches_finish_rule(key, finish_range):
            continue
        values.append(value)

        if finish_range.mode == "all_match" and value != finish_range.expected_word:
            return False
        if finish_range.mode == "all_present" and str(value).strip().lower() in danger_words:
            return False

    if not values:
        return default
    return True


def parse_csv_by_definition(
    file_path: str,
    definition: CsvParserDefinition,
    meta: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Dict[str, Any]:
    result = build_default_parse_result(file_path, finished=definition.default_finished)

    try:
        rows = read_csv_rows(file_path)
        parsed_metadata = metadata if metadata is not None else extract_section(rows, definition.metadata_range)
        if meta:
            parsed_metadata.update(meta)
        config_values = extract_section(rows, definition.config_range) if definition.config_range else {}
        result["metadata"] = parsed_metadata
        result["test_type"] = definition.test_type.value
        result["upload_config_key"] = definition.upload_config_key
        result["finished"] = evaluate_finished(rows, definition.finish_range, definition.default_finished)

        for sn_field in definition.sn_fields:
            sn = find_field_value(rows, definition, sn_field, meta=parsed_metadata)
            if sn:
                result["sn"] = sn
                result["model"] = extract_model_from_sn(sn, MODEL_MAPPING)
                break

        if definition.kind:
            kind_value = find_field_value(rows, definition, definition.kind, meta=parsed_metadata)
            if kind_value:
                result["kind_stage_type"], result["kind_oem_type"] = parse_operator_kind(kind_value)
                if definition.metadata_operator_alias:
                    parsed_metadata[definition.metadata_operator_alias] = kind_value.split(".")[0]

        if not result.get("kind_stage_type") or result.get("kind_stage_type") == "NA":
            result["kind_stage_type"] = "Production"

        return result
    except FileNotFoundError:
        result["error"] = f"文件未找到: {file_path}"
        return result
    except Exception as exc:
        result["error"] = f"解析文件时出错: {str(exc)}"
        return result
