import enum
from ot3_testing.ot_type import Point, Mount


class CalibrateMethod(enum.Enum):
    Approach = "approach"
    Dichotomy = "dichotomy"


SlotLocationCH96 = {"C1-Y": {"Point": Point(223, 203, 318), "compensation": {"left_rear": -0.189, "left_front": 0},
                             "definition": ["left_front", "left_rear"]},
                    "C3-Y": {"Point": Point(207, 203, 318), "compensation": {"right_rear": -0.028, "right_front": 0},
                             "definition": ["left_front", "left_rear"]},
                    "A2-Y": {"Point": Point(387, 421, 318), "compensation": {"left_rear": -0.208, "left_front": 0},
                             "definition": ["left_front", "left_rear"]},
                    "C1-X": {"Point": Point(50, 91, 300), "compensation": {"rear_left": 0, "rear_right": -0.078},
                             "definition": ["rear_left", "rear_right"]},
                    "C3-X": {"Point": Point(382, 91, 300), "compensation": {"rear_left": 0, "rear_right": 0.073},
                             "definition": ["rear_left", "rear_right"]},
                    "A2-X": {"Point": Point(213, 305, 300), "compensation": {"rear_left": 0, "rear_right": 0.102},
                             "definition": ["rear_left", "rear_right"]},
                    "D1-Z": {"Point": Point(51, 99, 318),
                             "compensation": {"below_rear_left": -0.008, "below_rear_right": 0.092,
                                              "below_front_left": 0,
                                              "below_front_right": 0.128},
                             "definition": ["below_rear_left", "below_rear_right",
                                            "below_front_left",
                                            "below_front_right"]},

                    "D3-Z": {"Point": Point(377, 99, 318),
                             "compensation": {"below_rear_left": -0.038, "below_rear_right": -0.042,
                                              "below_front_left": 0, "below_front_right": 0},
                             "definition": ["below_rear_left", "below_rear_right",
                                            "below_front_left", "below_front_right"]},
                    "C2-Z": {"Point": Point(214, 210, 318),
                             "compensation": {"below_rear_left": -0.047, "below_rear_right": -0.052,
                                              "below_front_left": 0.0,
                                              "below_front_right": 0.022},
                             "definition": ["below_rear_left", "below_rear_right",
                                            "below_front_left",
                                            "below_front_right"]},
                    "A2-Z": {"Point": Point(218, 424, 390.5),
                             "compensation": {"below_rear_left": -0.047, "below_rear_right": -0.052,
                                              "below_front_left": 0,
                                              "below_front_right": 0.022},
                             "definition": ["below_rear_left", "below_rear_right",
                                            "below_front_left",
                                            "below_front_right"]},
                    "UninstallPos": {"Point": Point(223, 203, 500)}
                    }

ChannelDefinitionCH96 = {
    Mount.LEFT: {
        "left_front": {"device_addr": 1, "channel": 0, "offset": 0},
        "left_rear": {"device_addr": 1, "channel": 1, "offset": 0},
        "right_front": {"device_addr": 1, "channel": 2, "offset": 0},
        "right_rear": {"device_addr": 1, "channel": 3, "offset": 0},
        "rear_right": {"device_addr": 1, "channel": 5, "offset": 0},
        "rear_left": {"device_addr": 1, "channel": 4, "offset": 0},
        "below_front_left": {"device_addr": 2, "channel": 8, "offset": 0},
        "below_front_right": {"device_addr": 2, "channel": 9, "offset": 0},
        "below_rear_left": {"device_addr": 2, "channel": 10, "offset": 0},
        "below_rear_right": {"device_addr": 2, "channel": 11, "offset": 0},

    },
    Mount.RIGHT: {

    }

}

# device addr are un-useful in ch8
ChannelDefinitionCH8 = {
    Mount.LEFT: {"left_front": {"device_addr": 1, "channel": 0, "offset": 0},
                 "left_rear": {"device_addr": 1, "channel": 1, "offset": 0}},
    Mount.RIGHT: {"right_front": {"device_addr": 1, "channel": 0, "offset": 0},
                  "right_rear": {"device_addr": 1, "channel": 1, "offset": 0}
                  }

}

SlotLocationCH8 = {
    "Y-C1-Left": {"Point": Point(215.42, 198.33, 299.16), "compensation": {"left_rear": 0, "left_front": 0}},
    "Y-C1-Right": {"Point": Point(172.07, 197.18, 299.16), "compensation": {"right_rear": 0.024, "right_front": 0}},
    "Y-C3-Right": {"Point": Point(499.83, 197.18, 299.16), "compensation": {"right_rear": -0.014, "right_front": 0}},
    "Y-A2-Right": {"Point": Point(335.94, 412.22, 299.16), "compensation": {"right_rear": -0.013, "right_front": 0}},
    "UninstallPos": {"Point": Point(223, 203, 500), "compensation": 0}
}
