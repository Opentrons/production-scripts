from ot3_testing.leveling_test.type import Point, TestNameLeveling, SlotName, Direction, Mount, FIXTURE1_LEFT_CHANNEL, \
    FIXTURE1_RIGHT_CHANNEL
from ot3_testing.leveling_test.config import LevelingSetting
from typing import Union, Dict, List
from dataclasses import dataclass, field

@dataclass(kw_only=True)
class SlotConfig:
    mount: Mount
    slot_name: SlotName
    point: Point
    compensation: Dict[str, float] = field(default_factory=dict)
    channel: Dict[str, int] = field(default_factory=dict)

"""
Fixture_1 is the fixture for z_leveling and 8ch leveling test
There are totally 2 of mount, and 4 channels per mount
"""


def get_channel_from_fixture1(channel_name: Union[FIXTURE1_LEFT_CHANNEL, FIXTURE1_RIGHT_CHANNEL]):
    return channel_name.value

def get_slot_config(test_name: TestNameLeveling,
                    mount: Mount,
                    slot_name: SlotName,
                    direction: Direction
                    ) -> SlotConfig:
    point = LevelingSetting[test_name][mount][slot_name][direction]["point"]
    compensation = LevelingSetting[test_name][mount][slot_name][direction]["compensation"]
    channel = LevelingSetting[test_name][mount][slot_name][direction]["channel_definition"]

    slot_config = SlotConfig(
        mount=mount,
        slot_name=slot_name,
        point=point,
        compensation=compensation,
        channel=channel
    )
    return slot_config