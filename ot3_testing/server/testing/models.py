from typing import Optional, Union, Dict, List
from pydantic import BaseModel


class LifetimeCfg(BaseModel):
    ip: str
    robot_name: str
    current_speed_cycle: dict
    with_key: bool

