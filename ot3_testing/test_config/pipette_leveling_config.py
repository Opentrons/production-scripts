import enum
from ot3_testing.ot_type import Point


class CalibrateMethod(enum.Enum):
    Approach = "approach"
    Dichotomy = "dichotomy"


SlotLocationCH96 = {"C1-Y": Point(223, 203, 318),
                    "C3-Y": Point(207, 203, 318),
                    "A2-Y": Point(387, 421, 318),
                    "C1-X": Point(50, 91, 300),
                    "C3-X": Point(382, 91, 300),
                    "A2-X": Point(213, 305, 300),
                    "D1-Z": Point(51, 99, 318),
                    # "B2-Z": Point(213, 324, 317),
                    "D3-Z": Point(377, 99, 318),
                    "C2-Z": Point(214, 210, 318),
                    "A2-Z": Point(218, 424, 390.5),
                    "UninstallPos": Point(223, 203, 500)
                    }

ChannelDefinitionCH96 = {"left_front": {"device_addr": 1, "channel": 4},
                         "left_rear": {"device_addr": 1, "channel": 5},
                         "right_front": {"device_addr": 1, "channel": 3},
                         "right_rear": {"device_addr": 1, "channel": 2},
                         "rear_right": {"device_addr": 1, "channel": 0},
                         "rear_left": {"device_addr": 1, "channel": 1},
                         "below_front_left": {"device_addr": 2, "channel": 1},
                         "below_front_right": {"device_addr": 2, "channel": 0},
                         "below_rear_left": {"device_addr": 2, "channel": 3},
                         "below_rear_right": {"device_addr": 2, "channel": 2},
                         }

ChannelOffsetsCH96 = {"left_front": 0,
                      "left_rear": 0,
                      "right_front": 0,
                      "right_rear": 0,
                      "rear_right": 0,
                      "rear_left": 0,
                      "below_front_left": 0,
                      "below_front_right": 0,
                      "below_rear_left": 0,
                      "below_rear_right": 0,
                      }

ChannelDefinitionCH8 = {"left_front": {"device_addr": 1, "channel": 0},
                        "left_rear": {"device_addr": 1, "channel": 1},
                        "right_front": {"device_addr": 1, "channel": 0},
                        "right_rear": {"device_addr": 1, "channel": 1},
                        }

SlotLocationCH8 = {"Y-C1-Left": Point(198.42, 198.33, 299.16),
                   "Y-C1-Right": Point(172.07, 197.18, 299.16),
                   "Y-C3-Right": Point(499.83, 197.18, 299.16),
                   "Y-A2-Right": Point(335.94, 412.22, 299.16),
                   "UninstallPos": Point(223, 203, 500)
                   }


# ChannelOffsetsCH8 = {"left_front": 0,
#                      "left_rear": -0.05074,
#                      "right_front": 0,
#                      "right_rear": 0.01876}

ChannelOffsetsCH8 = {"left_front": 0,
                     "left_rear": 0,
                     "right_front": 0,
                     "right_rear": 0}
