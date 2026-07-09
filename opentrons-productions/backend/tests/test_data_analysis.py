from __future__ import annotations

import csv
import re
from pathlib import Path

from data_analysis.service import analyze_file_paths
from data_analysis.spec_store import get_gravimetric_spec, save_gravimetric_spec
from api.services.upload_records import summarize_product_stats
from api.services.unit_tracker import build_assembly_qc_standard_row, resolve_standard_columns


SAMPLE_PATH = Path(__file__).resolve().parents[1] / "datas" / "P200-CH96" / "P2HHV3220250331A02-qc - %D.csv"
P1000_96_SAMPLE_PATH = Path(__file__).resolve().parents[1] / "datas" / "P1000-CH96" / "P1KHV3620260603A01-qc - %D.csv"
P50S_VOLUME_SAMPLE_PATH = Path(__file__).resolve().parents[1] / "datas" / "P50S" / "P50SV3620260626A12-qc - Volume.csv"
P1KS_GRAV_SAMPLE_PATH = Path(__file__).resolve().parents[1] / "datas" / "P1KS" / "P1KSV3620260422A17-qc - Gravimetric Raw Data.csv"
P50M_GRAV_SAMPLE_PATH = Path(__file__).resolve().parents[1] / "datas" / "P50M" / "P50MV3520260425A03-qc - Gravimetric Raw Data.csv"
P1KM_GRAV_SAMPLE_PATH = Path(__file__).resolve().parents[1] / "datas" / "P1KM" / "P1KMV3520260626A02-qc - Gravimetric Raw Data.csv"
PIPETTE_ASSEMBLY_QC_SAMPLE_PATH = Path(__file__).resolve().parents[1] / "datas" / "P50S" / "P50SV3620240909A09-assembly-qc.csv"
P2HH_ASSEMBLY_QC_RAWDATA_SAMPLE_PATH = Path(__file__).resolve().parents[1] / "datas" / "P200-CH96" / "P2HHV3220260612A03-Assembly-QC-20260613105121 - RawData.csv"
ROBOT_ASSEMBLY_QC_SAMPLE_PATH = Path(__file__).resolve().parents[1] / "datas" / "Flex" / "robot-assembly-qc-ot3_run-26-06-04-08-56-54.csv"


def test_p200_96_gravimetric_analysis_sample():
    result = analyze_file_paths([str(SAMPLE_PATH)])

    assert result["errors"] == []
    assert result["summary"]["analyzed"] == 1
    analysis = result["analyses"][0]
    assert analysis["product"] == "P200-96"
    assert analysis["volumes"] == [1.0, 50.0, 200.0]
    assert analysis["result"] == "Fail"
    assert "50 uL dispense D 1.43 exceeds spec 1.2" in analysis["summary"]["failures"]
    assert len(analysis["trial_series"]) == 27
    assert analysis["trial_series"][0]["water_remain"] == 0.05
    assert len(analysis["single_channel_trial_matrices"]) == 3
    assert len(analysis["environment_summary"]) == 3


def test_p1000_96_gravimetric_analysis_sample():
    result = analyze_file_paths([str(P1000_96_SAMPLE_PATH)])

    assert result["errors"] == []
    assert result["summary"]["analyzed"] == 1
    analysis = result["analyses"][0]
    assert analysis["analyzer_key"] == "gravimetric.p1000_96"
    assert analysis["product"] == "P1000-96"
    assert analysis["volumes"] == [5.0, 50.0, 200.0, 1000.0]
    assert analysis["result"] == "Fail"
    assert len(analysis["trial_series"]) == 36
    assert analysis["summary"]["trial_count"] == 36
    assert len(analysis["single_channel_trial_matrices"]) == 4
    assert len(analysis["environment_summary"]) == 4


def test_p50s_volume_analysis_sample():
    result = analyze_file_paths([str(P50S_VOLUME_SAMPLE_PATH)])

    assert result["errors"] == []
    assert result["summary"]["analyzed"] == 1
    analysis = result["analyses"][0]
    assert analysis["analyzer_key"] == "gravimetric.p50_single"
    assert analysis["product"] == "P50S"
    assert analysis["volumes"] == [1.0, 50.0]
    assert analysis["result"] == "Pass"
    assert len(analysis["trial_series"]) == 20
    assert len(analysis["single_channel_trial_matrices"]) == 2
    min_matrix = analysis["single_channel_trial_matrices"][0]
    assert min_matrix["volume"] == 1.0
    assert len(min_matrix["rows"]) == 10
    assert min_matrix["rows"][0]["aspirate_time_s"] == 1054.2
    assert min_matrix["rows"][0]["aspirate_travel"] == -2.138


def test_p1ks_gravimetric_analysis_sample():
    result = analyze_file_paths([str(P1KS_GRAV_SAMPLE_PATH)])

    assert result["errors"] == []
    assert result["summary"]["analyzed"] == 1
    analysis = result["analyses"][0]
    assert analysis["analyzer_key"] == "gravimetric.p1000_single"
    assert analysis["product"] == "P1000S"
    assert analysis["volumes"] == [5.0, 1000.0]
    assert analysis["result"] == "Pass"
    assert len(analysis["trial_series"]) == 20
    assert len(analysis["single_channel_trial_matrices"]) == 2
    min_matrix = analysis["single_channel_trial_matrices"][0]
    assert min_matrix["volume"] == 5.0
    assert len(min_matrix["rows"]) == 10
    assert min_matrix["rows"][0]["aspirate_time_s"] == 952.6
    assert min_matrix["rows"][0]["aspirate_travel"] == -0.437


def test_p50m_gravimetric_analysis_sample():
    result = analyze_file_paths([str(P50M_GRAV_SAMPLE_PATH)])

    assert result["errors"] == []
    assert result["summary"]["analyzed"] == 1
    analysis = result["analyses"][0]
    assert analysis["analyzer_key"] == "gravimetric.p50_multi"
    assert analysis["view_key"] == "pipette_gravimetric"
    assert analysis["product"] == "P50M"
    assert analysis["volumes"] == [1.0, 50.0]
    assert analysis["result"] == "Pass"
    assert len(analysis["trial_series"]) == 160
    assert analysis["summary"]["trial_count"] == 160
    assert len(analysis["environment_series"]) == 480
    assert analysis["summary"]["environment_point_count"] == 480
    first_environment = analysis["environment_series"][0]
    assert first_environment["celsius_pipette"] is not None
    assert first_environment["humidity_pipette"] is not None
    assert first_environment["celsius_air"] is not None
    assert first_environment["humidity_air"] is not None


def test_p1km_gravimetric_analysis_sample():
    result = analyze_file_paths([str(P1KM_GRAV_SAMPLE_PATH)])

    assert result["errors"] == []
    assert result["summary"]["analyzed"] == 1
    analysis = result["analyses"][0]
    assert analysis["analyzer_key"] == "gravimetric.p1000_multi"
    assert analysis["view_key"] == "pipette_gravimetric"
    assert analysis["product"] == "P1000M"
    assert analysis["volumes"] == [5.0, 1000.0]
    assert analysis["result"] == "Pass"
    assert len(analysis["trial_series"]) == 160
    assert analysis["summary"]["trial_count"] == 160
    assert len(analysis["environment_series"]) == 480
    assert analysis["summary"]["environment_point_count"] == 480
    assert len(analysis["channel_trial_matrices"]) == 4


def test_pipette_assembly_qc_analysis_sample():
    result = analyze_file_paths([str(PIPETTE_ASSEMBLY_QC_SAMPLE_PATH)])

    assert result["errors"] == []
    assert result["summary"]["analyzed"] == 1
    analysis = result["analyses"][0]
    assert analysis["analyzer_key"] == "pipette_assembly_qc"
    assert analysis["view_key"] == "pipette_assembly_qc"
    assert analysis["product"] == "P1000S"
    assert analysis["result"] == "Pass"
    assert analysis["summary"]["check_count"] == 49


def test_p2hh_assembly_qc_rawdata_analysis_sample():
    result = analyze_file_paths([str(P2HH_ASSEMBLY_QC_RAWDATA_SAMPLE_PATH)])

    assert result["errors"] == []
    assert result["summary"]["analyzed"] == 1
    analysis = result["analyses"][0]
    assert analysis["analyzer_key"] == "pipette_assembly_qc"
    assert analysis["view_key"] == "pipette_assembly_qc"
    assert analysis["product"] == "P200-96"
    assert analysis["sn"] == "P2HHV3220260612A03"
    assert analysis["result"] == "Pass"
    assert len(analysis["metadata_table"]) == 9
    assert len(analysis["section_results"]) == 8
    assert len(analysis["test_sections"]) == 8
    assert analysis["summary"]["check_count"] == 63
    assert analysis["summary"]["matrix_count"] == 2
    capacitance = next(section for section in analysis["test_sections"] if section["section"] == "CAPACITANCE")
    assert capacitance["rows"][0]["spec"] == {"min": 4, "max": 10, "target": None, "expected": None}
    plunger_matrix = next(matrix for matrix in analysis["test_matrices"] if matrix["key"] == "plunger")
    assert [column["label"] for column in plunger_matrix["columns"]] == [
        "current-0.6-speed-5",
        "current-0.6-speed-15",
        "current-0.6-speed-22",
        "current-0.7-speed-5",
        "current-0.7-speed-15",
        "current-0.7-speed-22",
        "current-0.8-speed-5",
        "current-0.8-speed-15",
        "current-0.8-speed-22",
    ]
    assert [row["label"] for row in plunger_matrix["rows"]] == ["Down-start", "Down-end", "Up-start", "Up-end", "Results"]
    assert all(cell["status"] == "PASS" for row in plunger_matrix["rows"] for cell in row["values"])
    jaws_matrix = next(matrix for matrix in analysis["test_matrices"] if matrix["key"] == "jaws")
    assert [column["label"] for column in jaws_matrix["columns"]] == [
        "current-0.7-speed-8",
        "current-0.7-speed-12",
        "current-1.5-speed-8",
        "current-1.5-speed-12",
    ]
    assert all(cell["status"] == "PASS" for cell in jaws_matrix["rows"][0]["values"])


def test_p2hh_assembly_qc_unit_tracker_standard_row():
    row = build_assembly_qc_standard_row(
        csv_path=str(P2HH_ASSEMBLY_QC_RAWDATA_SAMPLE_PATH),
        csv_link="https://docs.google.com/spreadsheets/d/example",
    )

    assert row["location"] == "SZ"
    assert row["firmware"] == "60"
    assert row["sn"] == "P2HHV3220260612A03"
    assert row["operator_name"] == "xiongjian"
    assert row["current_plunger"] == "PASS"
    assert row["current_jaws"] == "PASS"
    assert row["capacitance"] == "PASS"
    assert row["pressure"] == "PASS"
    assert row["environment_sensor"] == "None"
    assert row["tip_sensor"] == "PASS"
    assert row["droplets"] == "PASS"
    assert row["plunger_current_0_6_speed_5"] == "PASS"
    assert row["jaws_current_0_7_speed_8"] == "PASS"
    assert row["capacitance_primary_air"] == 6.37739563
    assert row["pressure_primary_aspirate"] == -1055.910022
    assert row["environment_s0_celsius"] == 27.895
    assert row["environment_s0_humidity"] == 59.3825
    assert row["tip_empty"] == "PASS"
    assert row["tip_with_tip"] == "PASS"
    assert row["droplets_96_tips"] == "PASS"
    assert row["file_path"] == str(P2HH_ASSEMBLY_QC_RAWDATA_SAMPLE_PATH)


def test_p2hh_assembly_qc_unit_tracker_standard_columns_from_mapping():
    columns = resolve_standard_columns("P2HH", "Assembly QC")

    assert columns[0] == {
        "key": "location",
        "label": "Location",
        "group": "Info",
        "group_key": "info",
    }
    assert columns[12] == {
        "key": "plunger_current_0_6_speed_5",
        "label": "0.6-5",
        "group": "Plunger Current Speed",
        "group_key": "plunger_current_speed",
    }
    assert columns[-1] == {
        "key": "file_path",
        "label": "File Path",
        "group": "Others",
        "group_key": "others",
    }
    assert len(columns) == 47


def test_robot_assembly_qc_analysis_sample():
    result = analyze_file_paths([str(ROBOT_ASSEMBLY_QC_SAMPLE_PATH)])

    assert result["errors"] == []
    assert result["summary"]["analyzed"] == 1
    analysis = result["analyses"][0]
    assert analysis["analyzer_key"] == "robot_assembly_qc"
    assert analysis["view_key"] == "robot_assembly_qc"
    assert analysis["product"] == "Flex"
    assert analysis["result"] == "Pass"
    assert analysis["summary"]["check_count"] == 70


def test_p200_96_gravimetric_analysis_handles_missing_middle_volume(tmp_path):
    partial_path = tmp_path / "P2HHV3220250331A02-qc-1ul-200ul.csv"
    write_csv_without_volume(SAMPLE_PATH, partial_path, "50.0")

    result = analyze_file_paths([str(partial_path)])

    assert result["errors"] == []
    assert result["summary"]["analyzed"] == 1
    analysis = result["analyses"][0]
    assert analysis["product"] == "P200-96"
    assert analysis["volumes"] == [1.0, 200.0]
    assert len(analysis["trial_series"]) == 18
    assert {row["volume"] for row in analysis["trial_series"]} == {1.0, 200.0}
    assert {row["volume"] for row in analysis["environment_summary"]} == {1.0, 200.0}
    assert all(result_item["volume"] in {1.0, 200.0} for result_item in analysis["summary"]["volume_results"])
    assert not any("50 uL" in failure for failure in analysis["summary"]["failures"])


def test_gravimetric_spec_json_fallback_overrides_default(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_ANALYSIS_SPEC_JSON_PATH", str(tmp_path / "specs.json"))

    result = save_gravimetric_spec(
        {
            "product": "P2HH",
            "product_name": "P2HH",
            "analysis_product": "P200-96",
            "test_type": "gravimetric",
            "test_name": "Gravimetric",
            "volumes": [
                {"volume": 1, "cv": 99, "d": 7},
                {"volume": 200, "cv": 88, "d": 0.7},
            ],
        }
    )

    spec = get_gravimetric_spec("P200-96")

    assert result["storage"] == "json"
    assert spec[1.0] == {"cv": 99.0, "d": 7.0}
    assert spec[200.0] == {"cv": 88.0, "d": 0.7}


def test_upload_product_stats_filters_na_models():
    records = [
        {"status": "failed", "result": {"model": "NA"}},
        {"status": "failed", "result": {"model": "N/A"}},
        {"status": "success", "result": {"model": "P2HH"}},
        {"status": "failed", "result": {"model": "P50M"}},
    ]

    products = summarize_product_stats(records)

    assert [item["model"] for item in products] == ["P2HH", "P50M"]
    assert products[0]["success_rate"] == 100.0
    assert products[1]["success_rate"] == 0.0


def write_csv_without_volume(source: Path, destination: Path, volume: str) -> None:
    volume_key_pattern = re.compile(
        rf"^(volume-(aspirate|dispense)-{re.escape(volume)}-|"
        rf"trial-\d+-(aspirate|dispense|liquid_height)-{re.escape(volume)}-ul-|"
        rf"MeasurementType\.[A-Z]+-{re.escape(volume)}-ul-)"
    )

    with source.open("r", encoding="utf-8-sig", newline="") as source_file:
        rows = [
            row
            for row in csv.reader(source_file)
            if not (len(row) > 1 and volume_key_pattern.match(row[1]))
        ]

    with destination.open("w", encoding="utf-8", newline="") as destination_file:
        csv.writer(destination_file).writerows(rows)
