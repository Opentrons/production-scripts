from ot3_testing.ot_type import Mount, Point
import enum


class CalibrateMethod(enum.Enum):
    Approach = "approach"
    Dichotomy = "dichotomy"


ZStagePoint = {

    Mount.LEFT: {

        "Z-C2": {"point": Point(215, 197, 357), "compensation": {"rear": 0.036, "front": 0},
                 "channel_definition": ["below_rear", "below_front"]},

    },
    Mount.RIGHT: {
        "Z-A1": {"point": Point(5, 410, 357), "compensation": {"rear": -0.008, "front": 0},
                 "channel_definition": ["below_rear", "below_front"]},
        "Z-A2": {"point": Point(175, 410, 357), "compensation": {"rear": 0.006, "front": 0},
                 "channel_definition": ["below_rear", "below_front"]},
        "Z-A3": {"point": Point(335, 410, 357), "compensation": {"rear": -0.01, "front": 0},
                 "channel_definition": ["below_rear", "below_front"]},
        "Z-B1": {"point": Point(5, 305, 357), "compensation": {"rear": -0.035, "front": 0},
                 "channel_definition": ["below_rear", "below_front"]},
        "Z-B2": {"point": Point(175, 305, 357), "compensation": {"rear": 0.022, "front": 0},
                 "channel_definition": ["below_rear", "below_front"]},
        "Z-B3": {"point": Point(335, 305, 357), "compensation": {"rear": -0.011, "front": 0},
                 "channel_definition": ["below_rear", "below_front"]},
        "Z-C1": {"point": Point(5, 197, 357), "compensation": {"rear": -0.007, "front": 0},
                 "channel_definition": ["below_rear", "below_front"]},
        "Z-C2": {"point": Point(175, 197, 357), "compensation": {"rear": 0.001, "front": 0},
                 "channel_definition": ["below_rear", "below_front"]},

        "Z-C3": {"point": Point(335, 197, 357), "compensation": {"rear": -0.034, "front": 0},
                 "channel_definition": ["below_rear", "below_front"]},
        "Z-D1": {"point": Point(5, 92, 357), "compensation": {"rear": 0.032, "front": 0},
                 "channel_definition": ["below_rear", "below_front"]},
        "Z-D2": {"point": Point(175, 92, 357), "compensation": {"rear": -0.003, "front": 0},
                 "channel_definition": ["below_rear", "below_front"]},
        "Z-D3": {"point": Point(335, 92, 357), "compensation": {"rear": -0.034, "front": 0},
                 "channel_definition": ["below_rear", "below_front"]},


    }
}

ZStageChannel = {
    Mount.LEFT: {
        "below_rear": {"device_addr": 1, "channel": 3},
        "below_front": {"device_addr": 1, "channel": 2},
        "left_rear": {"device_addr": 1, "channel": 1},
        "left_front": {"device_addr": 1, "channel": 0}
    },

    Mount.RIGHT: {
        "below_rear": {"device_addr": 1, "channel": 3},
        "below_front": {"device_addr": 1, "channel": 2},
        "left_rear": {"device_addr": 1, "channel": 1},
        "left_front": {"device_addr": 1, "channel": 0}
    }
}
