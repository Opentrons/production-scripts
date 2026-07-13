from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

from upload_handler.models import TestTypes


FinishMode = Literal["all_present", "all_match"]
FieldSource = Literal["metadata", "config"]
FinishEvaluator = Callable[[list[list[Any]]], bool]


@dataclass(frozen=True)
class CsvSectionDefinition:
    start: str
    end: str
    key_name_loc: str = "B"
    value_loc: str = "C"


@dataclass(frozen=True)
class CsvFieldDefinition:
    key_name: str | tuple[str, ...]
    key_name_loc: str = "B"
    value_loc: str = "C"
    source: FieldSource = "metadata"
    extra_words: tuple[str, ...] = ()

    @property
    def key_names(self) -> tuple[str, ...]:
        if isinstance(self.key_name, str):
            return (self.key_name,)
        return self.key_name


@dataclass(frozen=True)
class CsvFinishDefinition:
    start: str
    end: str
    mode: FinishMode = "all_present"
    key_name_loc: str = "B"
    value_loc: str = "C"
    expected_word: str = "PASS"
    danger_words: tuple[str, ...] = ("None", "")
    key_contains_all: tuple[str, ...] = ()
    key_contains_any: tuple[str, ...] = ()
    ignore_keys: tuple[str, ...] = ()


FinishRange = CsvFinishDefinition | FinishEvaluator


@dataclass(frozen=True)
class CsvParserDefinition:
    upload_config_key: str
    test_type: TestTypes
    metadata_range: CsvSectionDefinition
    finish_range: FinishRange
    sn: CsvFieldDefinition | tuple[CsvFieldDefinition, ...]
    kind: CsvFieldDefinition | None = None
    test_name: CsvFieldDefinition = CsvFieldDefinition("test_name")
    config_range: CsvSectionDefinition | None = None
    default_finished: bool = True
    metadata_operator_alias: str | None = "operator-name"

    @property
    def sn_fields(self) -> tuple[CsvFieldDefinition, ...]:
        if isinstance(self.sn, CsvFieldDefinition):
            return (self.sn,)
        return self.sn


PIPETTE_GRAVIMETRIC_DEFINITION = {
    "metadata_range": CsvSectionDefinition("META_DATA_START", "META_DATA_END"),
    "config_range": CsvSectionDefinition("CONFIG_START", "CONFIG_END"),
    "finish_range": CsvFinishDefinition(
        "VOLUMES_START",
        "VOLUMES_END",
        mode="all_present",
        key_contains_all=("volume-dispense", "trial", "average"),
    ),
    "sn": (
        CsvFieldDefinition("test_tag", extra_words=("-qc", "-recorder", "-results")),
        CsvFieldDefinition("pipette", extra_words=("-qc", "-recorder", "-results")),
    ),
    "kind": CsvFieldDefinition("kind", source="config"),
    "test_name": CsvFieldDefinition("test_name"),
    "default_finished": False,
    "metadata_operator_alias": None,
}

PIPETTE_1CH_8CH_ASSEMBLY_QC_DEFINITION = {
    "metadata_range": CsvSectionDefinition("METADATA", "-------------------"),
    "finish_range": CsvFinishDefinition("RESULTS", "--------"),
    "sn": CsvFieldDefinition("pipette"),
    "kind": CsvFieldDefinition("operator-name"),
    "test_name": CsvFieldDefinition("test-name"),
}

PIPETTE_1CH_8CH_CURRENT_SPEED_DEFINITION = {
    "metadata_range": CsvSectionDefinition("META_DATA_START", "META_DATA_END"),
    "finish_range": CsvFinishDefinition(
        "RESULTS_OVERVIEW_START",
        "RESULTS_OVERVIEW_END",
        key_contains_any=("0.75", "1.0"),
    ),
    "sn": CsvFieldDefinition("test_tag", extra_words=("-qc", "-recorder", "-results")),
    "kind": CsvFieldDefinition("test_operator"),
    "test_name": CsvFieldDefinition("test_name"),
}

PIPETTE_96CH_ASSEMBLY_QC_DEFINITION = {
    "metadata_range": CsvSectionDefinition("META_DATA_START", "META_DATA_END"),
    "finish_range": CsvFinishDefinition(
        "RESULTS_OVERVIEW_START",
        "RESULTS_OVERVIEW_END",
        ignore_keys=("RESULT_ENVIRONMENT-SENSOR",),
    ),
    "sn": CsvFieldDefinition("test_tag", extra_words=("-qc", "-recorder", "-results")),
    "kind": CsvFieldDefinition(("operator-name", "test_operator")),
    "test_name": CsvFieldDefinition("test_name"),
}

PIPETTE_BURN_IN_RESULT_DEFINITION = {
    "metadata_range": CsvSectionDefinition("META_DATA_START", "META_DATA_END"),
    "finish_range": CsvFinishDefinition("CYCLING-RESULTS_START", "CYCLING-RESULTS_END"),
    "sn": CsvFieldDefinition("test_tag", extra_words=("-qc", "-recorder", "-results")),
    "kind": CsvFieldDefinition("test_operator"),
    "test_name": CsvFieldDefinition("test_name"),
}

PIPETTE_BURN_IN_RECORDS_DEFINITION = {
    "metadata_range": CsvSectionDefinition("META_DATA_START", "META_DATA_END"),
    "finish_range": CsvFinishDefinition("RESULTS_OVERVIEW_START", "RESULTS_OVERVIEW_END"),
    "sn": CsvFieldDefinition("test_tag", extra_words=("-qc", "-recorder", "-results")),
    "kind": CsvFieldDefinition("test_operator"),
    "test_name": CsvFieldDefinition("test_name"),
}


GANTRY_STRESS_REQUIRED_DATA_ROWS = 650


def _has_cell_value(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _row_has_data(row: list[Any]) -> bool:
    return any(_has_cell_value(value) for value in row)


def _normalize_key(value: Any) -> str:
    return "".join(char for char in str(value).lower() if char.isalnum())


def _is_numeric_one(value: Any) -> bool:
    try:
        return float(str(value).strip()) == 1.0
    except (TypeError, ValueError):
        return False


def _row_has_fail_count_one(row: list[Any]) -> bool:
    for index, value in enumerate(row[:-1]):
        if _normalize_key(value) == "failcount" and _is_numeric_one(row[index + 1]):
            return True
    return False


def evaluate_gantry_stress_finished(rows: list[list[Any]]) -> bool:
    if len(rows) < GANTRY_STRESS_REQUIRED_DATA_ROWS:
        return False
    if any(not _row_has_data(row) for row in rows[:GANTRY_STRESS_REQUIRED_DATA_ROWS]):
        return False
    return not any(_row_has_fail_count_one(row) for row in rows[GANTRY_STRESS_REQUIRED_DATA_ROWS:])


GENERAl_QC_DEFINITION = {
    "metadata_range": CsvSectionDefinition("META_DATA_START", "META_DATA_END"),
    "finish_range": CsvFinishDefinition(
        "RESULTS_OVERVIEW_START",
        "RESULTS_OVERVIEW_END",
    ),
    "sn": CsvFieldDefinition("test_tag", extra_words=("-qc", "-recorder", "-results")),
    "kind": CsvFieldDefinition(("operator-name", "test_operator")),
    "test_name": CsvFieldDefinition("test_name"),
}

OT3_GANTRY_STRESS_DEFINITION = {
    "metadata_range": CsvSectionDefinition("METADATA", "date"),
    "finish_range": evaluate_gantry_stress_finished,
    "sn": CsvFieldDefinition("serial-number", extra_words=("-qc", "-recorder", "-results")),
    "kind": CsvFieldDefinition(("operator-name", "test_operator")),
    "test_name": CsvFieldDefinition("test-name"),
}

OT3_XY_CALIBRATION_DEFINITION = {
    "metadata_range": CsvSectionDefinition("META_DATA_START", "META_DATA_END"),
    "finish_range": CsvFinishDefinition(
        "RESULTS_OVERVIEW_START",
        "RESULTS_OVERVIEW_END",
        ignore_keys=("RESULT_ATTITUDE", "RESULT_BELT-CALIBRATION-POSITIONS",
        "RESULT_BELT-CALIBRATION-SHIFTS", "RESULT_PIPETTE-OFFSETS", "RESULT_SLOT-OFFSETS"),
    ),
    "sn": CsvFieldDefinition("test_tag", extra_words=("-qc", "-recorder", "-results")),
    "kind": CsvFieldDefinition(("operator-name", "test_operator")),
    "test_name": CsvFieldDefinition("test_name"),
}

PARSER_DEFINITIONS: dict[str, CsvParserDefinition] = {
    "1ch_update_volume": CsvParserDefinition(
        upload_config_key="1ch_update_volume",
        test_type=TestTypes.Gravimetric,
        **PIPETTE_GRAVIMETRIC_DEFINITION,
    ),
    "8ch_update_volume": CsvParserDefinition(
        upload_config_key="8ch_update_volume",
        test_type=TestTypes.Gravimetric,
        **PIPETTE_GRAVIMETRIC_DEFINITION,
    ),
    "1ch_update_assembly_qc": CsvParserDefinition(
        upload_config_key="1ch_update_assembly_qc",
        test_type=TestTypes.Assembly_QC,
        **PIPETTE_1CH_8CH_ASSEMBLY_QC_DEFINITION,
    ),
    "8ch_update_assembly_qc": CsvParserDefinition(
        upload_config_key="8ch_update_assembly_qc",
        test_type=TestTypes.Assembly_QC,
        **PIPETTE_1CH_8CH_ASSEMBLY_QC_DEFINITION,
    ),
    "1ch_update_current_speed": CsvParserDefinition(
        upload_config_key="1ch_update_current_speed",
        test_type=TestTypes.Speed_Current_Test,
        **PIPETTE_1CH_8CH_CURRENT_SPEED_DEFINITION,
    ),
    "8ch_update_current_speed": CsvParserDefinition(
        upload_config_key="8ch_update_current_speed",
        test_type=TestTypes.Speed_Current_Test,
        **PIPETTE_1CH_8CH_CURRENT_SPEED_DEFINITION,
    ),
    "96_p200_update_qc": CsvParserDefinition(
        upload_config_key="96_p200_update_qc",
        test_type=TestTypes.Assembly_QC,
        **PIPETTE_96CH_ASSEMBLY_QC_DEFINITION,
    ),
    "96_p1000_update_qc": CsvParserDefinition(
        upload_config_key="96_p1000_update_qc",
        test_type=TestTypes.Assembly_QC,
        **PIPETTE_96CH_ASSEMBLY_QC_DEFINITION,
    ),
    "8ch_update_burn_in_result": CsvParserDefinition(
        upload_config_key="8ch_update_burn_in_result",
        test_type=TestTypes.BurnIn_Result,
        **PIPETTE_BURN_IN_RESULT_DEFINITION,
    ),
    "8ch_update_burn_in_records": CsvParserDefinition(
        upload_config_key="8ch_update_burn_in_records",
        test_type=TestTypes.BurnIn_Record,
        **PIPETTE_BURN_IN_RECORDS_DEFINITION,
    ),
    "robot_update_z_stage": CsvParserDefinition(
        upload_config_key="robot_update_z_stage",
        test_type=TestTypes.ZStage_Test,
        **GENERAl_QC_DEFINITION,
    ),
    "robot_update_diagnostic": CsvParserDefinition(
        upload_config_key="robot_update_diagnostic",
        test_type=TestTypes.Diagnostic,
        **GENERAl_QC_DEFINITION,
    ),
    "robot_update_xy_belt_calibration": CsvParserDefinition(
        upload_config_key="robot_update_xy_belt_calibration",
        test_type=TestTypes.XY_Calibration,
        **OT3_XY_CALIBRATION_DEFINITION,
    ),
    "robot_update_gantry_stress": CsvParserDefinition(
        upload_config_key="robot_update_gantry_stress",
        test_type=TestTypes.Gantry_Stress,
        **OT3_GANTRY_STRESS_DEFINITION,
    ),
    "robot_update_leveling": CsvParserDefinition(
        upload_config_key="robot_update_leveling",
        test_type=TestTypes.Leveling_Test,
        **GENERAl_QC_DEFINITION,
    ),
}


def get_parser_definition(upload_config_key: str) -> CsvParserDefinition | None:
    return PARSER_DEFINITIONS.get(upload_config_key)
