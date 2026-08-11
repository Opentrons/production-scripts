from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from cli.interface.operator_prompts import leveling_choices, test_choices
from cli.main import ENTRY_TEST_CHOICES, build_parser
from leveling_testing import config as leveling_config
from leveling_testing.config import load_gantry_leveling_config
from leveling_testing.__main__ import _selected_answers
from leveling_testing.leveing_gantry import GantryLeveling
from leveling_testing.type import Mount, Point, TestNameLeveling as LevelingTestName
from opentonrs_api.maintenance_api import jog as maintenance_jog
from opentonrs_api.maintenance_api.jog import MaintenanceJog


def _write_config(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "gantry_leveling_config": {
                    "mount": "left",
                    "safe_z": 505.0,
                    "points": {
                        "A1": [23.5, 422.5, 397.0],
                        "A3": [465.5, 422.5, 397.1],
                        "D1": [23.5, 37.0, 397.2],
                        "D3": [465.5, 37.0, 397.3],
                    },
                }
            },
            indent=4,
        ),
        encoding="utf-8",
    )


class FakeMaintenanceApi:
    def __init__(self, _robot_ip_address: str | None = None) -> None:
        self.run_id: str | None = None
        self.moves: list[tuple[Point, Mount]] = []
        self.home_count = 0

    async def create_run(self) -> None:
        self.run_id = "fake-run"

    async def delete_run(self) -> None:
        self.run_id = None

    async def home(self) -> None:
        self.home_count += 1

    async def move_to(self, coordinate: dict[str, float], mount: Mount, speed=567.8) -> None:
        self.moves.append((Point(**coordinate), mount))


def test_leveling_menu_and_all_use_requested_order() -> None:
    assert ENTRY_TEST_CHOICES[:2] == (
        ("leveling", "Leveling Test"),
        ("jog", "Jog OT3"),
    )
    assert leveling_choices[:7] == [
        "1.gantry_leveling_test",
        "2.z_leveling_test",
        "3.ch8_leveling_test",
        "4.ch96_leveling_test",
        "5.gripper_leveling_test",
        "6.read-sensor",
        "7.exit.",
    ]
    assert test_choices[:7] == [
        "1.leveling-gantry",
        "2.leveling-z-stage",
        "3.leveling-8ch",
        "4.leveling-96ch",
        "5.leveling-gripper",
        "6.Jog OT3",
        "7.leveling-reading-sensor",
    ]
    assert _selected_answers("all") == [
        LevelingTestName.Gantry_Leveling.value,
        LevelingTestName.Z_Leveling.value,
        LevelingTestName.CH8_Leveling.value,
        LevelingTestName.CH96_Leveling.value,
        LevelingTestName.Gripper_Leveling.value,
    ]

    jog_args = build_parser().parse_args(["jog", "--robot-ip", "192.168.6.15", "--mount", "right"])
    assert jog_args.command == "jog"
    assert jog_args.robot_ip == "192.168.6.15"
    assert jog_args.mount == "right"


def test_loads_four_gantry_points_from_leveling_config(tmp_path: Path) -> None:
    config_path = tmp_path / "leveling_config.json"
    _write_config(config_path)

    config = load_gantry_leveling_config(config_path)

    assert config.mount is Mount.LEFT
    assert config.safe_z == 505.0
    assert config.points["A1"] == Point(23.5, 422.5, 397.0)
    assert config.points["D3"] == Point(465.5, 37.0, 397.3)
    assert config.heights == {"A1": None, "A3": None, "D1": None, "D3": None}
    assert config.deck_slot is None


def test_unknown_heights_are_displayed_until_all_gauge_values_exist(
    tmp_path: Path,
    capsys,
) -> None:
    config_path = tmp_path / "leveling_config.json"
    _write_config(config_path)
    test = GantryLeveling("simulator", simulate=True, config_path=config_path)

    test._show_heights()

    assert capsys.readouterr().out.count("Unknown") == 6
    assert test.height_diff is None

    test.config.heights.update({"A1": 12.1, "A3": 12.4, "D1": 12.2, "D3": 12.3})
    assert test.height_diff == 0.3


def test_packaged_config_update_persists_next_to_executable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    bundle_dir = tmp_path / "bundle"
    bundle_config = bundle_dir / "leveling_testing" / "leveling_config.json"
    bundle_config.parent.mkdir(parents=True)
    _write_config(bundle_config)
    executable = tmp_path / "productions-hardwares"
    executable.touch()
    monkeypatch.setattr(leveling_config.sys, "_MEIPASS", str(bundle_dir), raising=False)
    monkeypatch.setattr(leveling_config.sys, "executable", str(executable))

    leveling_config.save_gantry_leveling_point("A1", Point(23.5, 422.5, 398.0))

    external_config = tmp_path / "leveling_config.json"
    assert external_config.exists()
    assert load_gantry_leveling_config(external_config).points["A1"].z == 398.0


def test_saves_height_gauge_value_without_changing_movement_point(tmp_path: Path) -> None:
    config_path = tmp_path / "leveling_config.json"
    _write_config(config_path)

    leveling_config.save_gantry_leveling_height("A1", 12.345, config_path)

    config = load_gantry_leveling_config(config_path)
    assert config.heights["A1"] == 12.345
    assert config.points["A1"] == Point(23.5, 422.5, 397.0)


def test_saves_gantry_deck_slot_value(tmp_path: Path) -> None:
    config_path = tmp_path / "leveling_config.json"
    _write_config(config_path)

    leveling_config.save_gantry_leveling_deck_slot(" Slot A1 / datum ", config_path)

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["gantry_leveling_config"]["deck_slot"] == "Slot A1 / datum"
    assert load_gantry_leveling_config(config_path).deck_slot == "Slot A1 / datum"


def test_loads_legacy_numeric_deck_slot_as_string(tmp_path: Path) -> None:
    config_path = tmp_path / "leveling_config.json"
    _write_config(config_path)
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    saved["gantry_leveling_config"]["deck_slot"] = 8.125
    config_path.write_text(json.dumps(saved), encoding="utf-8")

    assert load_gantry_leveling_config(config_path).deck_slot == "8.125"


@pytest.mark.asyncio
async def test_maintenance_jog_uses_current_maintenance_run() -> None:
    api = FakeMaintenanceApi()
    jog = MaintenanceJog(api, Mount.LEFT, Point(23.5, 422.5, 397.0))

    result = await jog.move("z", 0.5)

    assert result == Point(23.5, 422.5, 397.5)
    assert api.moves == [(result, Mount.LEFT)]


@pytest.mark.asyncio
async def test_maintenance_jog_rejects_out_of_range_target() -> None:
    api = FakeMaintenanceApi()
    jog = MaintenanceJog(api, Mount.LEFT, Point(23.5, 25.0, 397.0))

    with pytest.raises(ValueError, match="outside the allowed range"):
        await jog.move("y", -0.01)

    assert api.moves == []


@pytest.mark.asyncio
async def test_maintenance_jog_keyboard_controls_position_and_step() -> None:
    api = FakeMaintenanceApi()
    jog = MaintenanceJog(api, Mount.LEFT, Point(100.0, 100.0, 400.0))

    await jog.handle_key("+")
    assert jog.step == 1.0
    await jog.handle_key("w")
    await jog.handle_key("a")
    await jog.handle_key("i")
    await jog.handle_key("-")

    assert jog.step == 0.5
    assert jog.current_point == Point(99.0, 101.0, 401.0)
    assert (await jog.handle_key("q")).running is False


@pytest.mark.asyncio
async def test_jog_ot3_owns_and_releases_maintenance_run(monkeypatch) -> None:
    api = FakeMaintenanceApi()
    monkeypatch.setattr(maintenance_jog, "MaintenanceApi", lambda _address: api)
    keys = iter(["d", "+", "i", "q"])

    result = await maintenance_jog.jog_ot3(
        "192.168.6.15",
        mount=Mount.RIGHT,
        start_point=Point(100.0, 100.0, 400.0),
        key_reader=lambda: next(keys),
        render=False,
    )

    assert result == Point(100.5, 100.0, 401.0)
    assert [point for point, _mount in api.moves] == [
        Point(100.0, 100.0, 400.0),
        Point(100.5, 100.0, 400.0),
        Point(100.5, 100.0, 401.0),
    ]
    assert all(mount is Mount.RIGHT for _point, mount in api.moves)
    assert api.home_count == 2
    assert api.run_id is None


@pytest.mark.asyncio
async def test_moves_between_points_at_safe_z(tmp_path: Path) -> None:
    config_path = tmp_path / "leveling_config.json"
    _write_config(config_path)
    test = GantryLeveling("simulator", simulate=True, config_path=config_path)
    api = FakeMaintenanceApi()
    test.api = api

    await test.move_to_point("A1")
    await test.move_to_point("A3")

    assert [point for point, _mount in api.moves] == [
        Point(23.5, 422.5, 505.0),
        Point(23.5, 422.5, 397.0),
        Point(23.5, 422.5, 505.0),
        Point(465.5, 422.5, 505.0),
        Point(465.5, 422.5, 397.1),
    ]


@pytest.mark.asyncio
async def test_simulated_dialog_jogs_and_updates_selected_point(tmp_path: Path) -> None:
    config_path = tmp_path / "leveling_config.json"
    _write_config(config_path)
    test = GantryLeveling(
        "simulator",
        script_dir=str(tmp_path),
        simulate=True,
        config_path=config_path,
    )
    test.robot_sn = "SIMULATED-ROBOT"
    test.operator_name = "Tester"
    answers = iter(
        [
            "A1",
            "jog",
            "update",
            "back",
            "deck-slot",
            "exit",
        ]
    )
    jog_keys = iter(["i", "+", "q"])

    async def select_answer(_message, _choices):
        return next(answers)

    async def input_value(message, _default=""):
        return "D1 reference" if "deck slot" in message.casefold() else "12.345"

    test._select = select_answer
    test._text = input_value
    test.jog_key_reader = lambda: next(jog_keys)
    test.render_jog = False

    await test.run()

    updated = load_gantry_leveling_config(config_path)
    assert updated.points["A1"] == Point(23.5, 422.5, 397.0)
    assert updated.heights["A1"] == 12.345
    assert updated.deck_slot == "D1 reference"
    assert test.height_diff is None
    assert test.api.run_id is None

    reports = list((tmp_path / "testing_data").glob("*.csv"))
    assert len(reports) == 1
    with reports[0].open(encoding="utf-8", newline="") as report_file:
        rows = list(csv.reader(report_file))
    header = next(row for row in rows if row and row[0] == "START_TIME")
    data = rows[rows.index(header) + 1]
    assert "GANTRY_PARALLELISM_DIFF" in header
    assert data[1] == "SIMULATED-ROBOT"
    assert data[2] == "12.345"
    assert data[6] == "UNKNOWN"
    assert data[7] == "D1 reference"
