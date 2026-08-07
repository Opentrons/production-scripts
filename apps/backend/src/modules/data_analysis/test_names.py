from __future__ import annotations

import re
from typing import Any


UNKNOWN_TEST_TYPE_KEYS = {"", "-", "na", "n/a", "none", "null", "unknown", "unknow"}

TEST_TYPE_LABELS_BY_KEY = {
    "gravimetric": "Gravimetric",
    "grav": "Gravimetric",
    "volume": "Gravimetric",
    "1chupdatevolume": "Gravimetric",
    "8chupdatevolume": "Gravimetric",
    "assemblyqc": "Assembly QC",
    "qc": "Assembly QC",
    "1chupdateassemblyqc": "Assembly QC",
    "8chupdateassemblyqc": "Assembly QC",
    "96p200updateqc": "Assembly QC",
    "96p1000updateqc": "Assembly QC",
    "speedcurrent": "Speed Current",
    "currentspeed": "Speed Current",
    "speedcurrenttest": "Speed Current",
    "1chupdatecurrentspeed": "Speed Current",
    "8chupdatecurrentspeed": "Speed Current",
    "burninresult": "Burn In Result",
    "burninresulttest": "Burn In Result",
    "8chupdateburninresult": "Burn In Result",
    "burninrecord": "Burn In Records",
    "burninrecords": "Burn In Records",
    "burninrecordtest": "Burn In Records",
    "8chupdateburninrecords": "Burn In Records",
    "pressureleakage": "Pressure Leakage",
    "pressureleakagetest": "Pressure Leakage",
    "zstage": "Z Stage",
    "zstagetest": "Z Stage",
    "robotupdatezstage": "Z Stage",
    "diagnostic": "Diagnostic",
    "robotassembly": "Diagnostic",
    "robotupdatediagnostic": "Diagnostic",
    "xycalibration": "XY Belt Calibration",
    "xybeltcalibration": "XY Belt Calibration",
    "robotupdatexybeltcalibration": "XY Belt Calibration",
    "gantrystress": "Gantry Stress",
    "gantrystresstest": "Gantry Stress",
    "robotupdategantrystress": "Gantry Stress",
    "leveling": "Leveling",
    "levelingtest": "Leveling",
    "robotupdateleveling": "Leveling",
    "photometric": "Photometric",
}

TEST_TYPE_QUERY_VARIANTS = {
    "Gravimetric": {
        "Gravimetric",
        "gravimetric",
        "Grav",
        "grav",
        "Volume",
        "volume",
        "1ch_update_volume",
        "8ch_update_volume",
    },
    "Assembly QC": {
        "Assembly QC",
        "assembly_qc",
        "Assembly_QC",
        "assembly qc",
        "assembly-qc",
        "QC",
        "qc",
        "1ch_update_assembly_qc",
        "8ch_update_assembly_qc",
        "96_p200_update_qc",
        "96_p1000_update_qc",
    },
    "Speed Current": {
        "Speed Current",
        "speed_current_test",
        "speed current",
        "current speed",
        "1ch_update_current_speed",
        "8ch_update_current_speed",
    },
    "Burn In Result": {
        "Burn In Result",
        "burn_in_result_test",
        "burn in result",
        "8ch_update_burn_in_result",
    },
    "Burn In Records": {
        "Burn In Records",
        "Burn In Record",
        "burn_in_record_test",
        "burn in record",
        "burn in records",
        "8ch_update_burn_in_records",
    },
    "Pressure Leakage": {
        "Pressure Leakage",
        "pressure_leakage_test",
        "pressure leakage",
    },
    "Z Stage": {
        "Z Stage",
        "z_stage_test",
        "z stage",
        "robot_update_z_stage",
    },
    "Diagnostic": {
        "Diagnostic",
        "diagnostic",
        "Robot Assembly",
        "robot_update_diagnostic",
    },
    "XY Belt Calibration": {
        "XY Belt Calibration",
        "xy_calibration",
        "xy belt calibration",
        "robot_update_xy_belt_calibration",
    },
    "Gantry Stress": {
        "Gantry Stress",
        "gantry_stress_test",
        "gantry stress",
        "robot_update_gantry_stress",
    },
    "Leveling": {
        "Leveling",
        "leveling_test",
        "robot_update_leveling",
    },
    "Photometric": {
        "Photometric",
        "photometric",
    },
}


def normalize_test_type_key(value: Any) -> str:
    raw_value = getattr(value, "value", value)
    text = str(raw_value or "").strip()
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def canonical_test_type(value: Any) -> str:
    raw_value = getattr(value, "value", value)
    text = str(raw_value or "").strip()
    key = normalize_test_type_key(text)
    if key in UNKNOWN_TEST_TYPE_KEYS or key.startswith("unknown") or key.startswith("unknow"):
        return ""
    if key in TEST_TYPE_LABELS_BY_KEY:
        return TEST_TYPE_LABELS_BY_KEY[key]
    if "gravimetric" in key or "volume" in key:
        return "Gravimetric"
    if "assemblyqc" in key or (("assembly" in key or key.endswith("qc")) and "rawdata" not in key):
        return "Assembly QC"
    if "speed" in key and "current" in key:
        return "Speed Current"
    if "burnin" in key and "result" in key:
        return "Burn In Result"
    if "burnin" in key and ("record" in key or "records" in key):
        return "Burn In Records"
    if "pressure" in key and "leakage" in key:
        return "Pressure Leakage"
    if "zstage" in key:
        return "Z Stage"
    if "xy" in key and "calibration" in key:
        return "XY Belt Calibration"
    if "gantry" in key and "stress" in key:
        return "Gantry Stress"
    if "leveling" in key:
        return "Leveling"
    if "diagnostic" in key:
        return "Diagnostic"
    if "photometric" in key:
        return "Photometric"
    return title_case_test_type(text)


def title_case_test_type(value: str) -> str:
    words = re.split(r"[\s_-]+", value.strip())
    normalized_words: list[str] = []
    for word in words:
        if not word:
            continue
        upper_word = word.upper()
        if upper_word in {"QC", "XY", "CV", "SN"}:
            normalized_words.append(upper_word)
        else:
            normalized_words.append(word[:1].upper() + word[1:].lower())
    return " ".join(normalized_words)


def unique_test_types(values: list[Any] | tuple[Any, ...] | set[Any]) -> list[str]:
    return sorted({label for value in values if (label := canonical_test_type(value))})


def same_test_type(left: Any, right: Any) -> bool:
    left_label = canonical_test_type(left)
    right_label = canonical_test_type(right)
    return bool(left_label and left_label == right_label)


def test_type_query_values(value: Any) -> list[str]:
    label = canonical_test_type(value)
    if not label:
        return []
    return sorted({label, *(TEST_TYPE_QUERY_VARIANTS.get(label) or set())})
