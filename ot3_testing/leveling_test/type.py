from __future__ import annotations  # 必须放在文件开头
from typing import NamedTuple, Any
from math import isclose
from enum import Enum, auto


class Point(NamedTuple):
    x: float
    y: float
    z: float

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Point):
            return False
        else:
            pairs = ((self.x, other.x), (self.y, other.y), (self.z, other.z))
            return all(isclose(s, o, rel_tol=1e-05, abs_tol=1e-08) for s, o in pairs)

    def __add__(self, other: Any) -> Point:
        if not isinstance(other, Point):
            return NotImplemented  # 不可完成的操作
        return Point(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: Any) -> Point:
        if not isinstance(other, Point):
            return NotImplemented
        return Point(self.x - other.x, self.y - other.y, self.z - other.z)

    def replace(self, replace:dict[str, float]) -> Point:
        # 创建当前值的字典
        current_values = self._asdict()
        # 用新值更新
        current_values.update(replace)
        # 创建新的 Point 对象
        return Point(**current_values)


class SlotName(Enum):
    A1 = 0
    A2 = auto()
    A3 = auto()

    B1 = auto()
    B2 = auto()
    B3 = auto()

    C1 = auto()
    C2 = auto()
    C3 = auto()

    D1 = auto()
    D2 = auto()
    D3 = auto()


class Mount(Enum):
    LEFT = "left"
    RIGHT = "right"


class TestNameLeveling(Enum):
    Z_Leveling = "z_leveling_test"
    CH8_Leveling = "ch8_leveling_test"
    CH96_Leveling = "ch96_leveling_test"
    Gripper_Leveling = "gripper_leveling_test"


class Direction(Enum):
    Z = "z"
    X = "x"
    Y = "y"


class FIXTURE1_LEFT_CHANNEL(Enum):
    LEFT_FRONT = 0
    LEFT_REAR = 1
    BELOW_FRONT = 2
    BELOW_REAR = 3


class FIXTURE1_RIGHT_CHANNEL(Enum):
    LEFT_FRONT = 0
    LEFT_REAR = 1
    BELOW_FRONT = 2
    BELOW_REAR = 3
