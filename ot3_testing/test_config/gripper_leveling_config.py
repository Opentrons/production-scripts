from ot3_testing.ot_type import Point, Mount
import enum


class CalibrateMethod(enum.Enum):
    Approach = "approach"
    Dichotomy = "dichotomy"


GripperMiddlePosition = Point(200, 332.5, 550)

Gripper_Position = {
    Mount.LEFT: {
        "x": {"point": Point(52, 332.5, 550), "definition": ["rear_left", "rear_right"],
              "compensation": {"rear_left": -0.003, "rear_right": 0}},
        "y": {"point": Point(223.5, 181.7, 550), "definition": ["right_front", "right_rear"],
              "compensation": {"right_front": 0, "right_rear": -0.029}},
        "z": {"point": Point(202.5, 177, 550), "definition": ["below_rear", "below_front"],
              "compensation": {"below_rear": 0.04, "below_front": 0}},
    }

}

GripperChannel = {
    Mount.LEFT: {"right_front": {"device_addr": 1, "channel": 2, "offset": 0},
                 "right_rear": {"device_addr": 1, "channel": 3, "offset": 0},
                 "rear_left": {"device_addr": 1, "channel": 1, "offset": 0},
                 "rear_right": {"device_addr": 1, "channel": 0, "offset": 0},
                 "below_rear": {"device_addr": 1, "channel": 5, "offset": 0},
                 "below_front": {"device_addr": 1, "channel": 4, "offset": 0},
                 }
}
