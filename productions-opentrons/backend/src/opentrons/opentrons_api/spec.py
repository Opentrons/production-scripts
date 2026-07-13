from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

OPENAPI_RELATIVE_PATH = Path(__file__).resolve().parents[3] / "asserts" / "opentrons_openapi.json"

DEFAULT_OPENTRONS_VERSION = "3"
DEFAULT_PORT = 31950

# Common paths referenced by the control UI.
PATH_HEALTH = "/health"
PATH_INSTRUMENTS = "/instruments"
PATH_MODULES = "/modules"
PATH_ROBOT_HOME = "/robot/home"
PATH_ROBOT_MOVE = "/robot/move"
PATH_ROBOT_POSITIONS = "/robot/positions"
PATH_SETTINGS_RESET = "/settings/reset"
PATH_SETTINGS_RESET_OPTIONS = "/settings/reset/options"
PATH_SETTINGS_ROBOT = "/settings/robot"
PATH_PIPETTES = "/pipettes"
PATH_PROTOCOLS = "/protocols"
PATH_RUNS = "/runs"


@lru_cache(maxsize=1)
def load_openapi_spec() -> dict[str, Any]:
    with OPENAPI_RELATIVE_PATH.open(encoding="utf-8") as spec_file:
        return json.load(spec_file)


def get_openapi_paths() -> dict[str, Any]:
    return load_openapi_spec().get("paths", {})
