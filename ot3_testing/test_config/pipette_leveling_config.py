import enum
from ot3_testing.ot_type import Point


class CalibrateMethod(enum.Enum):
    Approach = "approach"
    Dichotomy = "dichotomy"


SlotLocationCH96 = {"C1-Y": {"Point": Point(223, 203, 318), "compensation": 0.25},
                    "C3-Y": {"Point": Point(207, 203, 318), "compensation": 0.01},
                    "A2-Y": {"Point": Point(387, 421, 318), "compensation": 0.26},
                    "C1-X": {"Point": Point(50, 91, 300), "compensation": 0.30},
                    "C3-X": {"Point": Point(382, 91, 300), "compensation": 0.27},
                    "A2-X": {"Point": Point(213, 305, 300), "compensation": 0.3},
                    "D1-Z": {"Point": Point(51, 99, 318), "compensation": 0.5},
                    # "B2-Z": Point(213, 324, 317),
                    "D3-Z": {"Point": Point(377, 99, 318), "compensation": 0.44},
                    "C2-Z": {"Point": Point(214, 210, 318), "compensation": 0.46},
                    "A2-Z": {"Point": Point(218, 424, 390.5), "compensation": 0.31},
                    "UninstallPos": {"Point": Point(223, 203, 500)}
                    }

ChannelDefinitionCH96 = {"left_front": {"device_addr": 1, "channel": 4, "offset": 0},
                         "left_rear": {"device_addr": 1, "channel": 5, "offset": 0},
                         "right_front": {"device_addr": 1, "channel": 3, "offset": 0},
                         "right_rear": {"device_addr": 1, "channel": 2, "offset": 0},
                         "rear_right": {"device_addr": 1, "channel": 0, "offset": 0},
                         "rear_left": {"device_addr": 1, "channel": 1, "offset": 0},
                         "below_front_left": {"device_addr": 2, "channel": 1, "offset": 0},
                         "below_front_right": {"device_addr": 2, "channel": 0, "offset": 0},
                         "below_rear_left": {"device_addr": 2, "channel": 3, "offset": 0},
                         "below_rear_right": {"device_addr": 2, "channel": 2, "offset": 0},
                         }

# device addr are un-useful in ch8
ChannelDefinitionCH8 = {"left_front": {"device_addr": 1, "channel": 0, "offset": 0},
                        "left_rear": {"device_addr": 1, "channel": 1, "offset": 0},
                        "right_front": {"device_addr": 1, "channel": 4, "offset": 0},
                        "right_rear": {"device_addr": 1, "channel": 5, "offset": 0},
                        }

SlotLocationCH8 = {"Y-C1-Left": {"Point": Point(198.42, 198.33, 299.16), "compensation": -0.015},
                   "Y-C1-Right": {"Point": Point(172.07, 197.18, 299.16), "compensation": -0.03},
                   "Y-C3-Right": {"Point": Point(499.83, 197.18, 299.16), "compensation": -0.03},
                   "Y-A2-Right": {"Point": Point(335.94, 412.22, 299.16), "compensation": -0.03},
                   "UninstallPos": {"Point": Point(223, 203, 500), "compensation": 0}
                   }

