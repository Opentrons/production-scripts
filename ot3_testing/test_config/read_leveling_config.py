import json
import os
from ot3_testing.ot_type import Point, Mount


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


def _parse_nested_dict(d):
    result = {}
    for key, value in d.items():
        new_key = _convert_mount_key(key)
        if isinstance(value, dict):
            if "Point" in value and isinstance(value["Point"], list):
                value["Point"] = _convert_to_point(value["Point"])
            if "point" in value and isinstance(value["point"], list):
                value["point"] = _convert_to_point(value["point"])
            result[new_key] = _parse_nested_dict(value)
        elif isinstance(value, list) and len(value) == 3:
            result[new_key] = _convert_to_point(value)
        else:
            result[new_key] = value
    return result


def read_leveling_config(config_type=None):
    config_path = os.path.join(os.path.dirname(__file__), "leveling_config.json")
    
    with open(config_path, "r") as f:
        config = json.load(f)
    
    if config_type is not None:
        if config_type not in config:
            raise ValueError(f"Invalid config_type: {config_type}. Must be one of: {list(config.keys())}")
        return _parse_nested_dict(config[config_type])
    
    return {
        key: _parse_nested_dict(value)
        for key, value in config.items()
    }


def read_pipette_leveling_config():
    return read_leveling_config("pipette_leveling_config")


def read_zstage_leveling_config():
    return read_leveling_config("zstage_leveling_config")


def read_gripper_leveling_config():
    return read_leveling_config("gripper_leveling_config")