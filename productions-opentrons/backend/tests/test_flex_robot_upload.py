from __future__ import annotations

import csv
from pathlib import Path

import yaml

from upload_handler.parsers.registry import extract_csv
from upload_handler.uploaders.common import UploadCommonMixin


FLEX_DATA_DIR = Path(__file__).resolve().parents[1] / "datas" / "Flex"
PRODUCTION_CONFIG = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "upload_handler"
    / "configs"
    / "upload_production.yaml"
)


def test_leveling_report_rejects_mismatched_robot_serial_numbers() -> None:
    report = FLEX_DATA_DIR / "FLXU3020260601004-leveling-report-2026-07-22.csv"

    result = extract_csv(str(report))

    assert result is not None
    assert result["upload_config_key"] == "robot_update_leveling"
    assert result["sn"] == "FLXU3020260601004"
    assert result["model"] == "Robot"
    assert "Leveling robot SN mismatch" in result["error"]
    assert "FLXA3020250805002" in result["error"]


def test_leveling_report_with_matching_serial_numbers_parses(tmp_path: Path) -> None:
    report = tmp_path / "leveling.csv"
    report.write_text(
        "0,RESULTS,\n"
        "0,overall-result,PASS\n"
        "0,--------,\n"
        "0,METADATA,\n"
        "0,test-name,test-cli-leveling\n"
        "0,operator-name,andy\n"
        "0,session-id,FLXU3020260601004\n"
        "0,robot,FLXU3020260601004\n"
        "0,-------------------,\n"
        "START_TIME,ROBOT_SN,RESULT_STATUS\n"
        "2026-07-23,FLXU3020260601004,PASS\n",
        encoding="utf-8",
    )

    result = extract_csv(str(report))

    assert result is not None
    assert result["upload_config_key"] == "robot_update_leveling"
    assert result["finished"] is True
    assert result["error"] == "False"


def test_gantry_stress_range_covers_all_nonempty_sample_columns() -> None:
    config = yaml.safe_load(PRODUCTION_CONFIG.read_text(encoding="utf-8"))
    configured_range = config["robot_update_gantry_stress"][0]["Range"]
    columns = UploadCommonMixin.normalize_csv_columns(configured_range)
    report = FLEX_DATA_DIR / "stress-test-qc-ot3_run-26-06-03-11-01-58.csv"
    with report.open(encoding="utf-8-sig", newline="") as csv_file:
        rows = list(csv.reader(csv_file))
    last_nonempty_column = max(
        max((index + 1 for index, value in enumerate(row) if value.strip()), default=0)
        for row in rows
    )

    assert columns[0] == "A"
    assert columns[-1] == "N"
    assert len(columns) >= last_nonempty_column
