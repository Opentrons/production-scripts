from __future__ import annotations

import copy
import json
from pathlib import Path

from leveling_testing.convert_compensations import (
    find_and_update_compensation,
    load_json_config,
    read_excel_compensations,
)


APP_ROOT = Path(__file__).resolve().parents[1]
LEVELING_DIR = APP_ROOT / "src" / "leveling_testing"


def test_current_template_uses_workbook_channel_numbers_and_additive_correction() -> None:
    entries = read_excel_compensations(LEVELING_DIR / "Templete.xlsx")

    assert len(entries) == 27
    by_path = {entry.config_path: entry for entry in entries}

    c1 = by_path["pipette_leveling_config.SlotLocationCH96.C1-Y"]
    assert c1.channels == (1, 0)
    assert c1.definitions == ("left_rear", "left_front")
    assert c1.compensation == {"left_rear": -0.128, "left_front": 0.0}
    assert [c1.measurements[name] + c1.compensation[name] for name in c1.measurements] == [30.04, 30.04]

    c3 = by_path["pipette_leveling_config.SlotLocationCH96.C3-Y"]
    assert c3.channels == (3, 2)
    assert c3.definitions == ("right_rear", "right_front")
    assert c3.compensation == {"right_rear": -0.14, "right_front": 0.0}
    assert [c3.measurements[name] + c3.compensation[name] for name in c3.measurements] == [30.008, 30.008]


def test_legacy_formula_template_is_read_from_cached_or_simple_formulas() -> None:
    entries = read_excel_compensations(LEVELING_DIR / "Templete_2025_0828.xlsx")

    assert len(entries) == 27
    c1 = next(entry for entry in entries if entry.config_path.endswith("SlotLocationCH96.C1-Y"))
    assert c1.compensation["left_rear"] == -0.006
    assert c1.channels == (1, 0)


def test_generated_config_keeps_points_and_uses_runtime_channel_names() -> None:
    config = load_json_config(LEVELING_DIR / "leveling_config.json")
    before = copy.deepcopy(config)
    entries = read_excel_compensations(LEVELING_DIR / "Templete.xlsx")

    find_and_update_compensation(config, entries)

    assert config["pipette_leveling_config"]["SlotLocationCH96"]["C1-Y"]["Point"] == before[
        "pipette_leveling_config"
    ]["SlotLocationCH96"]["C1-Y"]["Point"]
    assert config["pipette_leveling_config"]["SlotLocationCH96"]["C1-Y"]["definition"] == [
        "left_rear",
        "left_front",
    ]
    assert config["pipette_leveling_config"]["SlotLocationCH96"]["C3-Y"]["definition"] == [
        "right_rear",
        "right_front",
    ]
    assert config["pipette_leveling_config"]["SlotLocationCH96"]["C3-Y"]["compensation"] == {
        "right_rear": -0.14,
        "right_front": 0.0,
    }
    assert config["zstage_leveling_config"]["ZStagePoint"]["left"]["Z-C2"]["channel_definition"] == [
        "below_rear",
        "below_front",
    ]
