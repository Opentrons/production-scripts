from ot3_testing.ot_type import Mount, Point
import enum


class CalibrateMethod(enum.Enum):
    Approach = "approach"
    Dichotomy = "dichotomy"


ZStagePoint = {

    Mount.LEFT: {
        "Z-A1": {"point": Point(214, 210, 418), "compensation": {"rear": 0, "front": 0},
                 "channel_definition": ["below_rear", "below_front"]},
        "Z-A2": {"point": Point(214, 210, 418), "compensation": {"rear": 0, "front": 0},
                 "channel_definition": ["below_rear", "below_front"]},
        "Z-A3": {"point": Point(214, 210, 418), "compensation": {"rear": 0, "front": 0},
                 "channel_definition": ["below_rear", "below_front"]},
        "Z-B1": {"point": Point(214, 210, 418), "compensation": {"rear": 0, "front": 0},
                 "channel_definition": ["below_rear", "below_front"]},
        "Z-B2": {"point": Point(214, 210, 418), "compensation": {"rear": 0, "front": 0},
                 "channel_definition": ["below_rear", "below_front"]},
        "Z-B3": {"point": Point(214, 210, 418), "compensation": {"rear": 0, "front": 0},
                 "channel_definition": ["below_rear", "below_front"]},
        "Z-C1": {"point": Point(214, 210, 418), "compensation": {"rear": 0, "front": 0},
                 "channel_definition": ["below_rear", "below_front"]},
        "Z-C2": {"point": Point(214, 210, 418), "compensation": {"rear": 0, "front": 0},
                 "channel_definition": ["below_rear", "below_front"]},
        "Z-C3": {"point": Point(214, 210, 418), "compensation": {"rear": 0, "front": 0},
                 "channel_definition": ["below_rear", "below_front"]},
        "Z-D1": {"point": Point(214, 210, 418), "compensation": {"rear": 0, "front": 0},
                 "channel_definition": ["below_rear", "below_front"]},
        "Z-D2": {"point": Point(214, 210, 418), "compensation": {"rear": 0, "front": 0},
                 "channel_definition": ["below_rear", "below_front"]},
        "Z-D3": {"point": Point(214, 210, 418), "compensation": {"rear": 0, "front": 0},
                 "channel_definition": ["below_rear", "below_front"]},
    },
    Mount.RIGHT: {
        "Z-C2": {"point": Point(177, 197, 357), "compensation": {"rear": 0, "front": 0},
                 "channel_definition": ["below_rear", "below_front"]}
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
        "below_rear": {"device_addr": 1, "channel": 7},
        "below_front": {"device_addr": 1, "channel": 6},
        "left_rear": {"device_addr": 1, "channel": 5},
        "left_front": {"device_addr": 1, "channel": 4}
    }
}
