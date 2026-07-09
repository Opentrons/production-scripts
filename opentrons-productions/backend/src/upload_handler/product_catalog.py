from __future__ import annotations

from dataclasses import dataclass
import re
from typing import TYPE_CHECKING

from settings import get_logger
from upload_handler.models import ProductionTypes, Productions, TestTypes

if TYPE_CHECKING:
    from upload_handler.parsers.definitions import CsvParserDefinition

logger = get_logger(__name__)

SERIAL_NUMBER_MODEL_MAPPING = {
    "P50S": Productions.P50S,
    "P1KS": Productions.P1000S,
    "P1KM": Productions.P1000M,
    "P50M": Productions.P50M,
    "P1KH": Productions.P1KH,
    "P2HH": Productions.P2HH,
    "FLX": Productions.ROBOT,
    "ZS": Productions.ROBOT,
    "GRPV": Productions.GRIPPER,
}

PIPETTE_1CH_MODELS = {
    Productions.P50S,
    Productions.P1000S,
}

PIPETTE_8CH_MODELS = {
    Productions.P50M,
    Productions.P1000M,
}

PIPETTE_96CH_MODELS = {
    Productions.P2HH,
    Productions.P1KH,
}


@dataclass(frozen=True)
class UploadProductProfile:
    uploader_key: str
    collection_prefix: str


@dataclass(frozen=True)
class UploadHandlerConfig:
    uploader_key: str
    upload_method: str
    test_display_name: str
    new_filename_template: str = "{sn}-{test_slug}-{timestamp}"
    timestamp_format: str = "%Y%m%d%H%M%S"
    tracker_sheet_name_template: str = "{oem} {model}"
    sheet_link_index: int = 0
    sheet_link_mode: str = "insert"


@dataclass(frozen=True)
class UploadDatabaseConfig:
    collection_workflow: str
    test_field: str
    upload_flag_field: str = ""


UPLOAD_PRODUCT_PROFILES = {
    Productions.P50S: UploadProductProfile(
        uploader_key="spreadsheet",
        collection_prefix="pipette_1ch",
    ),
    Productions.P1000S: UploadProductProfile(
        uploader_key="spreadsheet",
        collection_prefix="pipette_1ch",
    ),
    Productions.P50M: UploadProductProfile(
        uploader_key="spreadsheet",
        collection_prefix="pipette_8ch",
    ),
    Productions.P1000M: UploadProductProfile(
        uploader_key="spreadsheet",
        collection_prefix="pipette_8ch",
    ),
    Productions.P2HH: UploadProductProfile(
        uploader_key="spreadsheet",
        collection_prefix="pipette_96ch",
    ),
    Productions.P1KH: UploadProductProfile(
        uploader_key="spreadsheet",
        collection_prefix="pipette_96ch",
    ),
    Productions.ROBOT: UploadProductProfile(
        uploader_key="spreadsheet",
        collection_prefix="robot",
    ),
    Productions.GRIPPER: UploadProductProfile(
        uploader_key="spreadsheet",
        collection_prefix="gripper",
    ),
}

# 每个 tuple 表示一组需要落到同一个 Google Sheet / upload session 的配置 key。
# tuple 顺序会参与 workflow 名生成，新增组合时请保持稳定顺序。
UPLOAD_CONFIG_COMBINES: list[tuple[str, ...]] = [
    ("1ch_update_assembly_qc", "1ch_update_current_speed"),
    ("8ch_update_assembly_qc", "8ch_update_current_speed"),
    ("8ch_update_burn_in_result", "8ch_update_burn_in_records"),
    (
        "robot_update_diagnostic",
        "robot_update_xy_belt_calibration",
        "robot_update_gantry_stress",
        "robot_update_leveling",
        "robot_update_z_stage",
    ),
]

# the key name must be same as the configs/yaml keys
UPLOAD_HANDLER_CONFIGS = {
    "1ch_update_volume": UploadHandlerConfig(
        uploader_key="spreadsheet",
        upload_method="upload",
        test_display_name="Gravimetric",
        new_filename_template="{sn}-{timestamp}.csv",
        tracker_sheet_name_template="{model}",
    ),
    "8ch_update_volume": UploadHandlerConfig(
        uploader_key="spreadsheet",
        upload_method="upload",
        test_display_name="Gravimetric",
        new_filename_template="{sn}-{timestamp}.csv",
        tracker_sheet_name_template="{model}",
    ),
    "1ch_update_assembly_qc": UploadHandlerConfig(
        uploader_key="spreadsheet",
        upload_method="upload",
        test_display_name="Assembly QC",
        new_filename_template="{sn}-QC-CURRENTSPEED-{timestamp}",
        timestamp_format="%Y-%m-%d-%H-%M-%S",
    ),
    "8ch_update_assembly_qc": UploadHandlerConfig(
        uploader_key="spreadsheet",
        upload_method="upload",
        test_display_name="Assembly QC",
        new_filename_template="{sn}-QC-CURRENTSPEED-{timestamp}",
        timestamp_format="%Y-%m-%d-%H-%M-%S",
    ),
    "1ch_update_current_speed": UploadHandlerConfig(
        uploader_key="spreadsheet",
        upload_method="upload",
        test_display_name="Speed Current",
        new_filename_template="{sn}-QC-CURRENTSPEED-{timestamp}",
    ),
    "8ch_update_current_speed": UploadHandlerConfig(
        uploader_key="spreadsheet",
        upload_method="upload",
        test_display_name="Speed Current",
        new_filename_template="{sn}-QC-CURRENTSPEED-{timestamp}",
    ),
    "96_p200_update_qc": UploadHandlerConfig(
        uploader_key="spreadsheet",
        upload_method="upload",
        test_display_name="Assembly QC",
        new_filename_template="{sn}-Assembly-QC-{timestamp}",
        sheet_link_index=3,
        sheet_link_mode="set",
    ),
    "96_p1000_update_qc": UploadHandlerConfig(
        uploader_key="spreadsheet",
        upload_method="upload",
        test_display_name="Assembly QC",
        new_filename_template="{sn}-Assembly-QC-{timestamp}",
        sheet_link_index=3,
        sheet_link_mode="set",
    ),
    "8ch_update_burn_in_result": UploadHandlerConfig(
        uploader_key="spreadsheet",
        upload_method="upload",
        test_display_name="Burn In Result",
        new_filename_template="{sn}-Burn-In-Result-{timestamp}",
    ),
    "8ch_update_burn_in_records": UploadHandlerConfig(
        uploader_key="spreadsheet",
        upload_method="upload",
        test_display_name="Burn In Records",
        new_filename_template="{sn}-Burn-In-Records-{timestamp}",
    ),
    "robot_update_z_stage": UploadHandlerConfig(
        uploader_key="spreadsheet",
        upload_method="upload",
        test_display_name="Z Stage",
        new_filename_template="{sn}-RobotAssembly-{timestamp}",
    ),
    "robot_update_diagnostic": UploadHandlerConfig(
        uploader_key="spreadsheet",
        upload_method="upload",
        test_display_name="Diagnostic",
        new_filename_template="{sn}-RobotAssembly-{timestamp}",
    ),
    "robot_update_xy_belt_calibration": UploadHandlerConfig(
        uploader_key="spreadsheet",
        upload_method="upload",
        test_display_name="XY Belt Calibration",
        new_filename_template="{sn}-RobotAssembly-{timestamp}",
    ),
    "robot_update_gantry_stress": UploadHandlerConfig(
        uploader_key="spreadsheet",
        upload_method="upload",
        test_display_name="Gantry Stress",
        new_filename_template="{sn}-RobotAssembly-{timestamp}",
    ),
    "robot_update_leveling": UploadHandlerConfig(
        uploader_key="spreadsheet",
        upload_method="upload",
        test_display_name="Leveling",
        new_filename_template="{sn}-RobotAssembly-{timestamp}",
    ),
}

UPLOAD_DATABASE_CONFIGS = {
    "1ch_update_volume": UploadDatabaseConfig(
        collection_workflow="gravimetric",
        test_field="gravimetric",
        upload_flag_field="gravimetric",
    ),
    "8ch_update_volume": UploadDatabaseConfig(
        collection_workflow="gravimetric",
        test_field="gravimetric",
        upload_flag_field="gravimetric",
    ),
    "1ch_update_assembly_qc": UploadDatabaseConfig(
        collection_workflow="assembly_qc",
        test_field="assembly_qc",
        upload_flag_field="assembly_qc",
    ),
    "8ch_update_assembly_qc": UploadDatabaseConfig(
        collection_workflow="assembly_qc",
        test_field="assembly_qc",
        upload_flag_field="assembly_qc",
    ),
    "1ch_update_current_speed": UploadDatabaseConfig(
        collection_workflow="assembly_qc",
        test_field="current_speed",
        upload_flag_field="current_speed",
    ),
    "8ch_update_current_speed": UploadDatabaseConfig(
        collection_workflow="assembly_qc",
        test_field="current_speed",
        upload_flag_field="current_speed",
    ),
    "96_p200_update_qc": UploadDatabaseConfig(
        collection_workflow="assembly_qc",
        test_field="qc",
        upload_flag_field="ninety_six_assembly_qc",
    ),
    "96_p1000_update_qc": UploadDatabaseConfig(
        collection_workflow="assembly_qc",
        test_field="qc",
        upload_flag_field="ninety_six_assembly_qc",
    ),
    "8ch_update_burn_in_result": UploadDatabaseConfig(
        collection_workflow="burn_in",
        test_field="burn_in_result",
        upload_flag_field="burn_in_result",
    ),
    "8ch_update_burn_in_records": UploadDatabaseConfig(
        collection_workflow="burn_in",
        test_field="burn_in_records",
        upload_flag_field="burn_in_records",
    ),
    "robot_update_diagnostic": UploadDatabaseConfig(
        collection_workflow="diagnostic",
        test_field="diagnostic",
        upload_flag_field="diagnostic",
    ),
    "robot_update_xy_belt_calibration": UploadDatabaseConfig(
        collection_workflow="xy_calibration",
        test_field="xy_calibration",
        upload_flag_field="xy_calibration",
    ),
    "robot_update_gantry_stress": UploadDatabaseConfig(
        collection_workflow="gantry_stress",
        test_field="gantry_stress",
        upload_flag_field="gantry_stress_test",
    ),
    "robot_update_leveling": UploadDatabaseConfig(
        collection_workflow="leveling",
        test_field="leveling",
        upload_flag_field="leveling_test",
    ),
    "robot_update_z_stage": UploadDatabaseConfig(
        collection_workflow="z_stage",
        test_field="z_stage",
        upload_flag_field="z_stage_test",
    ),
}

SERIAL_NUMBER_METADATA_KEYS = ("test_tag", "pipette", "test_device_id", "serial-number")
SERIAL_NUMBER_EXTRA_WORDS = ("-qc", "-recorder", "-results")


def get_model_from_serial_number(sn: str) -> str:
    if not sn or sn == "None":
        return "NA"

    for pattern, production in SERIAL_NUMBER_MODEL_MAPPING.items():
        if re.search(re.escape(pattern), sn):
            return production.value

    match = re.search(r"P(\d+)([SM])", sn)
    if match:
        volume = match.group(1)
        channel_type = match.group(2)
        return f"P{volume}{channel_type}"
    return "NA"


def get_test_type_from_name(test_name: str) -> str:
    if not test_name or test_name == "None":
        return "NA"

    test_name_lower = str(test_name).lower()
    if "peek-burn-in" in test_name_lower and "result" in test_name_lower:
        return TestTypes.BurnIn_Result.value
    if "peek-burn-in" in test_name_lower and ("recorder" in test_name_lower or "record" in test_name_lower):
        return TestTypes.BurnIn_Record.value
    if "gravimetric" in test_name_lower or "grav" in test_name_lower:
        return TestTypes.Gravimetric.value
    if "speed" in test_name_lower or "current" in test_name_lower:
        return TestTypes.Speed_Current_Test.value
    if "z-stage" in test_name_lower or "z stage" in test_name_lower:
        return TestTypes.ZStage_Test.value
    if "robot-assembly" in test_name_lower:
        return TestTypes.Diagnostic.value
    if "belt-calibration" in test_name_lower:
        return TestTypes.XY_Calibration.value
    if "stress-test" in test_name_lower:
        return TestTypes.Gantry_Stress.value
    if "leveling" in test_name_lower:
        return TestTypes.Leveling_Test.value
    if "assembly" in test_name_lower:
        return TestTypes.Assembly_QC.value
    return "NA"


def normalize_serial_number(sn: str | None, extra_words: tuple[str, ...] = SERIAL_NUMBER_EXTRA_WORDS) -> str:
    if not sn or sn == "None":
        return ""

    serial_number = str(sn).strip()
    for extra_word in extra_words:
        serial_number = serial_number.replace(extra_word, "")
    return serial_number


def get_test_name_from_metadata(metadata: dict) -> str:
    return str(metadata.get("test_name") or metadata.get("test-name") or metadata.get("name") or "")


def get_serial_number_from_metadata(metadata: dict) -> str:
    for key in SERIAL_NUMBER_METADATA_KEYS:
        value = metadata.get(key)
        serial_number = normalize_serial_number(value)
        if serial_number:
            return serial_number
    return ""


def get_oem_type_from_text(text: str | None) -> str:
    if text:
        for oem_type in ProductionTypes:
            if re.search(re.escape(oem_type.value), str(text), re.IGNORECASE):
                return oem_type.value

    logger.warning(
        "OEM type not found in text: %s, default to %s",
        text,
        ProductionTypes.Opentrons.value,
    )
    return ProductionTypes.Opentrons.value


def normalize_test_type(test_type: str | TestTypes | None) -> TestTypes | None:
    resolved_test_type = TestTypes.from_string(test_type)
    if resolved_test_type is None and isinstance(test_type, str):
        resolved_test_type = TestTypes.from_string(get_test_type_from_name(test_type))
    return resolved_test_type

# 返回 upload_debug.yaml / upload_production.yaml 中的配置 key。
def get_upload_config_key(model: str, test_type: str | TestTypes | None) -> str:
    production = Productions.from_string(model)
    normalized_test_type = normalize_test_type(test_type)

    if production in PIPETTE_1CH_MODELS:
        if normalized_test_type == TestTypes.Gravimetric:
            return "1ch_update_volume"
        if normalized_test_type == TestTypes.Assembly_QC:
            return "1ch_update_assembly_qc"
        if normalized_test_type == TestTypes.Speed_Current_Test:
            return "1ch_update_current_speed"

    if production in PIPETTE_8CH_MODELS:
        if normalized_test_type == TestTypes.Gravimetric:
            return "8ch_update_volume"
        if normalized_test_type == TestTypes.Assembly_QC:
            return "8ch_update_assembly_qc"
        if normalized_test_type == TestTypes.Speed_Current_Test:
            return "8ch_update_current_speed"
        if normalized_test_type == TestTypes.BurnIn_Result:
            return "8ch_update_burn_in_result"
        if normalized_test_type == TestTypes.BurnIn_Record:
            return "8ch_update_burn_in_records"

    if production == Productions.P2HH and normalized_test_type == TestTypes.Assembly_QC:
        return "96_p200_update_qc"
    if production == Productions.P1KH and normalized_test_type == TestTypes.Assembly_QC:
        return "96_p1000_update_qc"

    if production == Productions.ROBOT:
        if normalized_test_type == TestTypes.Diagnostic:
            return "robot_update_diagnostic"
        if normalized_test_type == TestTypes.XY_Calibration:
            return "robot_update_xy_belt_calibration"
        if normalized_test_type == TestTypes.Gantry_Stress:
            return "robot_update_gantry_stress"
        if normalized_test_type == TestTypes.Leveling_Test:
            return "robot_update_leveling"
        if normalized_test_type == TestTypes.ZStage_Test:
            return "robot_update_z_stage"

    raise ValueError(f"Upload config key not found: model={model}, test_type={test_type}")


def get_upload_config_key_from_metadata(metadata: dict) -> str:
    """Resolve the upload YAML key from raw CSV metadata."""
    serial_number = get_serial_number_from_metadata(metadata)
    model = get_model_from_serial_number(serial_number)
    test_name = get_test_name_from_metadata(metadata)
    return get_upload_config_key(model, test_name)


def get_parser_definition(upload_config_key: str) -> CsvParserDefinition | None:
    """Return parser definition for a YAML upload config key."""
    from upload_handler.parsers.definitions import get_parser_definition as _get_parser_definition

    return _get_parser_definition(upload_config_key)


def get_upload_config_combine(config_key: str) -> tuple[str, ...]:
    """Return the configured workflow group for a YAML upload config key."""
    for combine in UPLOAD_CONFIG_COMBINES:
        if config_key in combine:
            return combine
    return (config_key,)


def get_upload_config_peer_keys(config_key: str) -> tuple[str, ...]:
    return tuple(key for key in get_upload_config_combine(config_key) if key != config_key)


def get_test_field_from_config_key(config_key: str) -> str:
    if "_update_" not in config_key:
        raise ValueError(f"Upload config key does not contain '_update_': {config_key}")
    return config_key.split("_update_", 1)[1]


def get_combined_test_fields(config_key: str) -> tuple[str, ...]:
    return tuple(get_test_field_from_config_key(key) for key in get_upload_config_combine(config_key))


def is_combined_upload_config(config_key: str) -> bool:
    return len(get_upload_config_combine(config_key)) > 1


def get_upload_workflow_from_config_key(config_key: str) -> str:
    """Build a stable workflow name from a YAML upload config key."""
    return "__".join(get_upload_config_combine(config_key))


def get_upload_workflow(model: str, test_type: str | TestTypes | None) -> str:
    """Resolve upload workflow from product model and test type/name."""
    config_key = get_upload_config_key(model, test_type)
    return get_upload_workflow_from_config_key(config_key)


def get_upload_database_config(config_key: str) -> UploadDatabaseConfig:
    db_config = UPLOAD_DATABASE_CONFIGS.get(config_key)
    if db_config is None:
        raise ValueError(f"Upload database config not found: config_key={config_key}")
    return db_config


def get_upload_handler_config(config_key: str) -> UploadHandlerConfig:
    handler_config = UPLOAD_HANDLER_CONFIGS.get(config_key)
    if handler_config is None:
        raise ValueError(f"Upload handler config not found: config_key={config_key}")
    return handler_config


def get_upload_handler_config_for_test(model: str, test_type: str | TestTypes | None) -> UploadHandlerConfig:
    return get_upload_handler_config(get_upload_config_key(model, test_type))


def get_upload_database_config_for_test(model: str, test_type: str | TestTypes | None) -> UploadDatabaseConfig:
    return get_upload_database_config(get_upload_config_key(model, test_type))


def get_upload_database_peer_fields(config_key: str) -> tuple[str, ...]:
    return tuple(get_test_field_from_config_key(peer_key) for peer_key in get_upload_config_peer_keys(config_key))


def is_upload_result_successful(config_key: str, result: dict) -> bool:
    db_config = get_upload_database_config(config_key)
    upload_flag = result.get(db_config.upload_flag_field)
    if isinstance(upload_flag, bool):
        return upload_flag
    if upload_flag not in (None, "", "N/A"):
        return True
    return bool(result.get("csv_link"))


def get_upload_product_profile(model: str) -> UploadProductProfile | None:
    production = Productions.from_string(model)
    if production is None:
        return None
    return UPLOAD_PRODUCT_PROFILES.get(production)


def get_upload_uploader_key(model: str) -> str | None:
    profile = get_upload_product_profile(model)
    if profile is None:
        return None
    return profile.uploader_key


def get_upload_collection_name(model: str, workflow: str = "assembly_qc") -> str:
    profile = get_upload_product_profile(model)
    if profile is None:
        raise ValueError(f"Upload collection not found: model={model}")
    return f"{profile.collection_prefix}_{workflow}"


def get_upload_collection_name_from_config_key(model: str, config_key: str) -> str:
    return get_upload_collection_name(
        model,
        workflow=get_upload_database_config(config_key).collection_workflow,
    )
