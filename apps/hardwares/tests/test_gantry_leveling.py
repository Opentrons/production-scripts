from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli.interface.operator_prompts import leveling_choices, test_choices
from leveling_testing import config as leveling_config
from leveling_testing.config import load_gantry_leveling_config
from leveling_testing.__main__ import _selected_answers
from leveling_testing.leveing_gantry import GantryLeveling
from leveling_testing.type import Mount, Point, TestNameLeveling as LevelingTestName
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
    def __init__(self) -> None:
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
    assert leveling_choices[:6] == [
        "1.gantry_leveling_test",
        "2.z_leveling_test",
        "3.ch8_leveling_test",
        "4.ch96_leveling_test",
        "5.gripper_leveling_test",
        "6.read-sensor",
    ]
    assert test_choices[:6] == [
        "1.leveling-gantry",
        "2.leveling-z-stage",
        "3.leveling-8ch",
        "4.leveling-96ch",
        "5.leveling-gripper",
        "6.leveling-reading-sensor",
    ]
    assert _selected_answers("all") == [
        LevelingTestName.Gantry_Leveling.value,
        LevelingTestName.Z_Leveling.value,
        LevelingTestName.CH8_Leveling.value,
        LevelingTestName.CH96_Leveling.value,
        LevelingTestName.Gripper_Leveling.value,
    ]


def test_loads_four_gantry_points_from_leveling_config(tmp_path: Path) -> None:
    config_path = tmp_path / "leveling_config.json"
    _write_config(config_path)

    config = load_gantry_leveling_config(config_path)

    assert config.mount is Mount.LEFT
    assert config.safe_z == 505.0
    assert config.points["A1"] == Point(23.5, 422.5, 397.0)
    assert config.points["D3"] == Point(465.5, 37.0, 397.3)
    assert config.heights == {"A1": None, "A3": None, "D1": None, "D3": None}


def test_unknown_heights_are_displayed_until_all_gauge_values_exist(
    tmp_path: Path,
    capsys,
) -> None:
    config_path = tmp_path / "leveling_config.json"
    _write_config(config_path)
    test = GantryLeveling("simulator", simulate=True, config_path=config_path)

    test._show_heights()

    assert capsys.readouterr().out.count("Unknown") == 5
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
    test = GantryLeveling("simulator", simulate=True, config_path=config_path)
    answers = iter(
        [
            "A1",
            "jog",
            ("z", 1),
            "back",
            "update",
            "back",
            "exit",
        ]
    )

    async def select_answer(_message, _choices):
        return next(answers)

    async def input_height(_message, _default=""):
        return "12.345"

    test._select = select_answer
    test._text = input_height

    await test.run()

    updated = load_gantry_leveling_config(config_path)
    assert updated.points["A1"] == Point(23.5, 422.5, 397.0)
    assert updated.heights["A1"] == 12.345
    assert test.height_diff is None
    assert test.api.run_id is None
