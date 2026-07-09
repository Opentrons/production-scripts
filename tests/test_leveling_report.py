import csv

from test_cli.leveling_test.report.report import LevelingCSV
from test_cli.leveling_test.type import TestNameLeveling as LevelingTestName


def _set_start_time(monkeypatch, value: str) -> None:
    monkeypatch.setattr(
        LevelingCSV,
        "create_start_time",
        classmethod(lambda cls: value),
    )


def _read_rows(path) -> list[list[str]]:
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return list(csv.reader(handle))


def _result_status(rows: list[list[str]], test_name: LevelingTestName) -> str:
    for row in rows:
        if len(row) > 2 and row[0] == "0" and row[1] == test_name.value:
            return row[2]
    raise AssertionError(f"Missing result row for {test_name.value}")


def _section_count(rows: list[list[str]], test_name: LevelingTestName) -> int:
    return sum(1 for row in rows if len(row) > 2 and row[1] == "TEST" and row[2] == test_name.value)


def test_same_barcode_same_day_leveling_tests_share_one_csv(tmp_path, monkeypatch):
    robot_sn = "FLXA3020250805002"

    _set_start_time(monkeypatch, "2026-07-02-08-00-00")
    gantry_report = LevelingCSV(
        "Z_Leveling_Test.csv",
        str(tmp_path),
        LevelingTestName.Z_Leveling,
        robot_sn,
        "Andy",
    )
    gantry_report.create_csv_path()
    gantry_report.init_title()
    gantry_report.finish_test(passed=True)

    _set_start_time(monkeypatch, "2026-07-02-10-00-00")
    pipette_report = LevelingCSV(
        "CH8_Leveling_Test.csv",
        str(tmp_path),
        LevelingTestName.CH8_Leveling,
        robot_sn,
        "Andy",
    )
    pipette_report.create_csv_path()
    pipette_report.init_title()
    pipette_report.finish_test(passed=True)

    assert gantry_report.file_name == pipette_report.file_name
    assert gantry_report.csv_name == "FLXA3020250805002-leveling-report-2026-07-02.csv"
    assert len(list(tmp_path.glob("*.csv"))) == 1

    rows = _read_rows(gantry_report.file_name)
    assert _result_status(rows, LevelingTestName.Z_Leveling) == "PASS"
    assert _result_status(rows, LevelingTestName.CH8_Leveling) == "PASS"
    assert _result_status(rows, LevelingTestName.CH96_Leveling) == "NOT_RUN"
    assert _result_status(rows, LevelingTestName.Gripper_Leveling) == "NOT_RUN"
    assert _section_count(rows, LevelingTestName.Z_Leveling) == 1
    assert _section_count(rows, LevelingTestName.CH8_Leveling) == 1


def test_repeated_same_test_replaces_existing_section(tmp_path, monkeypatch):
    robot_sn = "FLXA3020250805002"

    _set_start_time(monkeypatch, "2026-07-02-08-00-00")
    first_report = LevelingCSV(
        "Z_Leveling_Test.csv",
        str(tmp_path),
        LevelingTestName.Z_Leveling,
        robot_sn,
        "Andy",
    )
    first_report.create_csv_path()
    first_report.init_title()
    first_report.finish_test(passed=False)

    _set_start_time(monkeypatch, "2026-07-02-14-30-00")
    second_report = LevelingCSV(
        "Z_Leveling_Test.csv",
        str(tmp_path),
        LevelingTestName.Z_Leveling,
        robot_sn,
        "Andy",
    )
    second_report.create_csv_path()
    second_report.init_title()
    second_report.finish_test(passed=True)

    rows = _read_rows(second_report.file_name)
    assert first_report.file_name == second_report.file_name
    assert _result_status(rows, LevelingTestName.Z_Leveling) == "PASS"
    assert _section_count(rows, LevelingTestName.Z_Leveling) == 1
    assert any(row[:2] == ["2026-07-02-14-30-00", robot_sn] for row in rows)
    assert not any(row[:2] == ["2026-07-02-08-00-00", robot_sn] for row in rows)
