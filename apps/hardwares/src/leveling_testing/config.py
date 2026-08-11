from leveling_testing.type import SlotName, Mount, Point, TestNameLeveling, Direction, FIXTURE1_LEFT_CHANNEL, \
    FIXTURE1_RIGHT_CHANNEL
from typing import Union, Dict, List
from dataclasses import dataclass, field
import json
from math import isfinite
import os
import sys
from pathlib import Path


@dataclass(kw_only=True)
class SlotConfig:
    mount: Mount
    slot_name: SlotName
    point: Point
    compensation: Dict[str, float] = field(default_factory=dict)
    channel: Dict[str, int] = field(default_factory=dict)


GANTRY_POINT_NAMES = ("A1", "A3", "D1", "D3")


@dataclass(kw_only=True)
class GantryLevelingConfig:
    mount: Mount
    safe_z: float
    points: Dict[str, Point]
    heights: Dict[str, float | None]
    deck_slot: str | None


def _leveling_config_path() -> Path:
    if hasattr(sys, '_MEIPASS'):
        external_path = Path(sys.executable).resolve().with_name("leveling_config.json")
        if external_path.exists():
            return external_path
        return Path(
            sys._MEIPASS,
            "leveling_testing",
            "leveling_config.json",
        )
    return Path(__file__).with_name("leveling_config.json")


def _leveling_config_write_path() -> Path:
    if hasattr(sys, '_MEIPASS'):
        return Path(sys.executable).resolve().with_name("leveling_config.json")
    return _leveling_config_path()


def _load_json_config(config_path: str | Path | None = None):
    resolved_path = Path(config_path) if config_path is not None else _leveling_config_path()
    abs_config_path = os.path.abspath(resolved_path)
    print(f"Loading leveling_config.json from: {abs_config_path}")
    with resolved_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_gantry_leveling_config(
    config_path: str | Path | None = None,
) -> GantryLevelingConfig:
    section = _load_json_config(config_path)["gantry_leveling_config"]
    points = {
        name: _convert_to_point(section["points"][name])
        for name in GANTRY_POINT_NAMES
    }
    if not all(isinstance(point, Point) for point in points.values()):
        raise ValueError("Gantry leveling points must contain X, Y, and Z")
    raw_heights = section.get("heights", {})
    heights = {
        name: _convert_gantry_height(raw_heights.get(name))
        for name in GANTRY_POINT_NAMES
    }
    return GantryLevelingConfig(
        mount=_convert_mount_key(section.get("mount", "left")),
        safe_z=float(section.get("safe_z", 505.0)),
        points=points,
        heights=heights,
        deck_slot=_convert_gantry_deck_slot(section.get("deck_slot")),
    )


def save_gantry_leveling_point(
    name: str,
    point: Point,
    config_path: str | Path | None = None,
) -> None:
    if name not in GANTRY_POINT_NAMES:
        raise ValueError(f"Unknown gantry leveling point: {name}")
    source_path = Path(config_path) if config_path is not None else _leveling_config_path()
    resolved_path = Path(config_path) if config_path is not None else _leveling_config_write_path()
    json_config = _load_json_config(source_path)
    json_config["gantry_leveling_config"]["points"][name] = list(point)
    temporary_path = resolved_path.with_name(f".{resolved_path.name}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as config_file:
            json.dump(json_config, config_file, indent=4, ensure_ascii=True)
            config_file.write("\n")
        os.replace(temporary_path, resolved_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def save_gantry_leveling_height(
    name: str,
    height: float,
    config_path: str | Path | None = None,
) -> None:
    if name not in GANTRY_POINT_NAMES:
        raise ValueError(f"Unknown gantry leveling point: {name}")
    if not isfinite(height):
        raise ValueError("Gantry leveling height must be finite")
    source_path = Path(config_path) if config_path is not None else _leveling_config_path()
    resolved_path = Path(config_path) if config_path is not None else _leveling_config_write_path()
    json_config = _load_json_config(source_path)
    section = json_config["gantry_leveling_config"]
    section.setdefault("heights", {})[name] = height
    temporary_path = resolved_path.with_name(f".{resolved_path.name}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as config_file:
            json.dump(json_config, config_file, indent=4, ensure_ascii=True)
            config_file.write("\n")
        os.replace(temporary_path, resolved_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def save_gantry_leveling_deck_slot(
    deck_slot: str,
    config_path: str | Path | None = None,
) -> None:
    if not isinstance(deck_slot, str):
        raise TypeError("Gantry leveling deck slot must be a string")
    normalized_deck_slot = deck_slot.strip()
    if not normalized_deck_slot:
        raise ValueError("Gantry leveling deck slot cannot be empty")
    source_path = Path(config_path) if config_path is not None else _leveling_config_path()
    resolved_path = Path(config_path) if config_path is not None else _leveling_config_write_path()
    json_config = _load_json_config(source_path)
    json_config["gantry_leveling_config"]["deck_slot"] = normalized_deck_slot
    temporary_path = resolved_path.with_name(f".{resolved_path.name}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as config_file:
            json.dump(json_config, config_file, indent=4, ensure_ascii=True)
            config_file.write("\n")
        os.replace(temporary_path, resolved_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _convert_gantry_height(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip().casefold() in {"", "unknown", "n/a"}:
        return None
    if isinstance(value, bool):
        raise ValueError(f"Invalid gantry leveling height: {value}")
    try:
        height = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid gantry leveling height: {value}") from exc
    if not isfinite(height):
        raise ValueError(f"Invalid gantry leveling height: {value}")
    return height


def _convert_gantry_deck_slot(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"Invalid gantry leveling deck slot: {value}")
    if isinstance(value, (int, float)):
        if not isfinite(value):
            raise ValueError(f"Invalid gantry leveling deck slot: {value}")
        return str(value)
    if not isinstance(value, str):
        raise ValueError(f"Invalid gantry leveling deck slot: {value}")
    normalized = value.strip()
    return normalized or None


def _convert_to_point(data):
    if isinstance(data, list) and len(data) == 3:
        return Point(data[0], data[1], data[2])
    return data


def _convert_mount_key(key):
    if key == "left":
        return Mount.LEFT
    elif key == "right":
        return Mount.RIGHT
    return key


def _convert_slot_name_key(key):
    slot_map = {
        "Z-A1": SlotName.A1, "Z-A2": SlotName.A2, "Z-A3": SlotName.A3,
        "Z-B1": SlotName.B1, "Z-B2": SlotName.B2, "Z-B3": SlotName.B3,
        "Z-C1": SlotName.C1, "Z-C2": SlotName.C2, "Z-C3": SlotName.C3,
        "Z-D1": SlotName.D1, "Z-D2": SlotName.D2, "Z-D3": SlotName.D3
    }
    return slot_map.get(key, key)


def _convert_direction_key(key):
    if key == "x":
        return Direction.X
    elif key == "y":
        return Direction.Y
    elif key == "z":
        return Direction.Z
    return key


def _parse_zstage_config(json_config):
    result = {}
    zstage_data = json_config["zstage_leveling_config"]["ZStagePoint"]
    channel_data = json_config["zstage_leveling_config"]["ZStageChannel"]
    
    for mount_key, slots in zstage_data.items():
        mount = _convert_mount_key(mount_key)
        result[mount] = {}
        for slot_key, slot_data in slots.items():
            slot_name = _convert_slot_name_key(slot_key)
            result[mount][slot_name] = {}
            direction = Direction.Z
            point = _convert_to_point(slot_data.get("point"))
            compensation = slot_data.get("compensation", {})
            channel_def_list = slot_data.get("channel_definition", [])
            channel_definition = {ch: channel_data[mount_key][ch]["channel"] for ch in channel_def_list}
            result[mount][slot_name][direction] = {
                "point": point,
                "compensation": compensation,
                "channel_definition": channel_definition
            }
            result[mount][slot_name][Direction.X] = {}
            result[mount][slot_name][Direction.Y] = {}
    return result


def _parse_ch8_config(json_config):
    result = {}
    ch8_data = json_config["pipette_leveling_config"]["SlotLocationCH8"]
    channel_data = json_config["pipette_leveling_config"]["ChannelDefinitionCH8"]
    
    for mount_key, slots in {"left": [SlotName.C1], "right": [SlotName.A2, SlotName.C1, SlotName.C3]}.items():
        mount = _convert_mount_key(mount_key)
        result[mount] = {}
        for slot_name in slots:
            result[mount][slot_name] = {}
            for direction in [Direction.X, Direction.Y, Direction.Z]:
                if direction == Direction.Y:
                    slot_key = f"Y-{slot_name.name}-{'Left' if mount == Mount.LEFT else 'Right'}"
                    if slot_key in ch8_data:
                        point = _convert_to_point(ch8_data[slot_key].get("Point"))
                        compensation = ch8_data[slot_key].get("compensation", {})
                        channel_def_list = ch8_data[slot_key].get("definition") or list(compensation.keys())
                        channel_definition = {ch: channel_data[mount_key][ch]["channel"] for ch in channel_def_list}
                        result[mount][slot_name][direction] = {
                            "point": point,
                            "compensation": compensation,
                            "channel_definition": channel_definition
                        }
                    else:
                        result[mount][slot_name][direction] = {}
                else:
                    result[mount][slot_name][direction] = {}
    return result


def _parse_ch96_config(json_config):
    result = {}
    ch96_data = json_config["pipette_leveling_config"]["SlotLocationCH96"]
    channel_data = json_config["pipette_leveling_config"]["ChannelDefinitionCH96"]
    
    for mount_key, slots in {"left": [SlotName.A2, SlotName.C1, SlotName.C3, SlotName.D1, SlotName.D3, SlotName.C2], "right": []}.items():
        mount = _convert_mount_key(mount_key)
        result[mount] = {}
        for slot_name in slots:
            result[mount][slot_name] = {}
            for direction in [Direction.X, Direction.Y, Direction.Z]:
                slot_key = f"{slot_name.name}-{direction.name}"
                if slot_key in ch96_data:
                    point = _convert_to_point(ch96_data[slot_key].get("Point"))
                    compensation = ch96_data[slot_key].get("compensation", {})
                    channel_def_list = ch96_data[slot_key].get("definition", [])
                    channel_definition = {ch: channel_data[mount_key][ch]["channel"] for ch in channel_def_list}
                    result[mount][slot_name][direction] = {
                        "point": point,
                        "compensation": compensation,
                        "channel_definition": channel_definition
                    }
                else:
                    result[mount][slot_name][direction] = {}
    return result


def _parse_gripper_config(json_config):
    result = {}
    gripper_data = json_config["gripper_leveling_config"]["Gripper_Position"]
    channel_data = json_config["gripper_leveling_config"]["GripperChannel"]
    
    for mount_key, slots in {"left": [SlotName.C2], "right": []}.items():
        mount = _convert_mount_key(mount_key)
        result[mount] = {}
        for slot_name in slots:
            result[mount][slot_name] = {}
            for direction_key, direction_data in gripper_data[mount_key].items():
                direction = _convert_direction_key(direction_key)
                point = _convert_to_point(direction_data.get("point"))
                compensation = direction_data.get("compensation", {})
                channel_def_list = direction_data.get("definition", [])
                channel_definition = {ch: channel_data[mount_key][ch]["channel"] for ch in channel_def_list}
                result[mount][slot_name][direction] = {
                    "point": point,
                    "compensation": compensation,
                    "channel_definition": channel_definition
                }
    return result


_leveling_config_cache = None

def get_leveling_setting():
    global _leveling_config_cache
    if _leveling_config_cache is None:
        json_config = _load_json_config()
        _leveling_config_cache = {
            TestNameLeveling.Z_Leveling: _parse_zstage_config(json_config),
            TestNameLeveling.CH8_Leveling: _parse_ch8_config(json_config),
            TestNameLeveling.CH96_Leveling: _parse_ch96_config(json_config),
            TestNameLeveling.Gripper_Leveling: _parse_gripper_config(json_config)
        }
    return _leveling_config_cache

LevelingSetting = get_leveling_setting()


def get_channel_from_fixture1(channel_name: Union[FIXTURE1_LEFT_CHANNEL, FIXTURE1_RIGHT_CHANNEL]):
    return channel_name.value


def get_slot_config(test_name: TestNameLeveling,
                    mount: Mount,
                    slot_name: SlotName,
                    direction: Direction
                    ) -> SlotConfig:
    point = LevelingSetting[test_name][mount][slot_name][direction]["point"]
    compensation = LevelingSetting[test_name][mount][slot_name][direction]["compensation"]
    channel = LevelingSetting[test_name][mount][slot_name][direction]["channel_definition"]

    slot_config = SlotConfig(
        mount=mount,
        slot_name=slot_name,
        point=point,
        compensation=compensation,
        channel=channel
    )
    return slot_config
