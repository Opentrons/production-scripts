import enum
from typing import Any, NamedTuple, Iterable, Union
from math import sqrt, isclose
from dataclasses import dataclass

TipRackRowPositionDefinition = ["A", "B", "C", "D", "E", "F", "G", "H"]

SlOT_POSITION_DEFINITION = {
    "slot1": [0.0, 0.0, 0.0],
    "slot2": [132.5, 0.0, 0.0],
    "slot3": [265.0, 0.0, 0.0],
    "slot4": [0.0, 90.5, 0.0],
    "slot5": [132.5, 90.5, 0.0],
    "slot6": [265.0, 90.5, 0.0],
    "slot7": [0.0, 181.0, 0.0],
    "slot8": [132.5, 181.0, 0.0],
    "slot9": [265.0, 181.0, 0.0],
    "slot10": [0.0, 271.5, 0.0],
    "slot11": [132.5, 271.5, 0.0],
    "slot12": [265.0, 271.5, 0.0]
}


class CalibrationType(enum.Enum):
    CALIBRATION_CHECK = "calibrationCheck"
    DECK_CALIBRATION = "deckCalibration"
    PIPETTE_OFFSET_CALIBRATION = "pipetteOffsetCalibration"
    TIP_LENGTH_CALIBRATION = "tipLengthCalibration"


class ExcuseNameWithCalibrationDeck(enum.Enum):
    LOAD_LABWARE = "calibration.loadLabware"
    MOVE_TO_TIP_RACK = "calibration.moveToTipRack"
    CALIBRATION_JOG = "calibration.jog"
    PICK_UP = "calibration.pickUpTip"
    TRY_AGAIN = "calibration.invalidateTip"
    EXIT = "calibration.exitSession"
    MOVE_TO_DECK = "calibration.moveToDeck"
    SAVE_OFFSET = "calibration.saveOffset"
    MOVE_TO_POINT_ONE = "calibration.moveToPointOne"
    DECK_MOVE_TO_POINT_TWO = "calibration.deck.moveToPointTwo"
    DECK_MOVE_TO_POINT_THREE = "calibration.deck.moveToPointThree"

    MOVE_TO_REFERENCE_POINT = "calibration.moveToReferencePoint"


class Mount(enum.Enum):
    LEFT = "left"
    RIGHT = "right"


@dataclass
class LabwareResult:
    labware_id: str
    slot_name: str
    labware_name: str


@dataclass
class PipetteResult:
    pipette_id: str
    mount: Mount


class Target(enum.Enum):
    PIPETTE = "pipette"
    ROBOT = "robot"


class Axis(enum.Enum):
    X = "x"
    Y = "y"
    Z = "z"
    L_Z = "leftZ"
    R_Z = "rightZ"
    L_P = "leftPlunger"
    R_P = "rightPlunger"


class PositionSel(enum.Enum):
    MOUNT_LEFT = enum.auto()
    MOUNT_RIGHT = enum.auto()
    TIP = enum.auto()


class ModuleName(enum.Enum):
    MAGNETIC_MODULE_V2 = "magneticModuleV2"
    TEMPERATURE_MODULE_V2 = "temperatureModuleV2"
    TC_V1 = "thermocyclerModuleV1"
    TC_V2 = "thermocyclerModuleV2"
    HEATER_SHAKER_MODULE_V1 = "heaterShakerModuleV1"


class LabWare(enum.Enum):
    OPENTRONS_96_TIPRACK_300UL = "opentrons_96_tiprack_300ul"
    OPENTRONS_96_TIPRACK_20UL = "opentrons_96_tiprack_20ul"
    OPENTRONS_48_TIPRACK_20UL = "opentrons_48_tiprack_20ul"
    NEST_12_RESERVOIR_15ML = "nest_12_reservoir_15ml"
    NEST_96_WELLPLATE_200UL_FLAT = "nest_96_wellplate_200ul_flat"
    TRASH_1100ML_FIXED = "opentrons_1_trash_1100ml_fixed"
    # OPENTRONS_PCR_PLATE = "opentrons_96_wellplate_200ul_pcr_full_skirt"
    OPENTRONS_PCR_PLATE = "armadillo_96_wellplate_200ul_pcr_full_skirt"


class Instrument(enum.Enum):
    PIPETTE_P300_SIGNAL_GEN2 = "p300_single_gen2"
    PIPETTE_P20_SIGNAL_GEN2 = "p20_single_gen2"
    PIPETTE_P300_MULTI_GEN2 = "p300_multi_gen2"


class Point(NamedTuple):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Point):
            return False
        pairs = ((self.x, other.x), (self.y, other.y), (self.z, other.z))
        return all(isclose(s, o, rel_tol=1e-05, abs_tol=1e-08) for s, o in pairs)

    def __add__(self, other: Any):
        if not isinstance(other, Point):
            return NotImplemented
        return Point(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: Any):
        if not isinstance(other, Point):
            return NotImplemented
        return Point(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, other: Union[int, float]):
        if not isinstance(other, (float, int)):
            return NotImplemented
        return Point(self.x * other, self.y * other, self.z * other)

    def __rmul__(self, other: Union[int, float]):
        if not isinstance(other, (float, int)):
            return NotImplemented
        return Point(self.x * other, self.y * other, self.z * other)

    def __abs__(self):
        return Point(abs(self.x), abs(self.y), abs(self.z))

    def __str__(self) -> str:
        return "({}, {}, {})".format(self.x, self.y, self.z)

    def replace_x(self, value):
        return Point(value, self.y, self.z)

    def replace_y(self, value):
        return Point(self.x, value, self.z)

    def replace_z(self, value):
        return Point(self.x, self.y, value)


    def magnitude_to(self, other: Any) -> float:
        if not isinstance(other, Point):
            return NotImplemented
        x_diff = self.x - other.x
        y_diff = self.y - other.y
        z_diff = self.z - other.z
        return sqrt(x_diff ** 2 + y_diff ** 2 + z_diff ** 2)

    @classmethod
    def converse_to_point(cls, point: Union[list, tuple]):
        """
        converse to Point class
        :param point:
        :return: Point
        """
        _point_list = []
        for item in point:
            try:
                item = float(item.strip())
            except:
                pass
            _point_list.append(item)

        return Point(_point_list[0], _point_list[1], _point_list[2])


def get_labware_name_by_value(value):
    for item in LabWare:
        if item.value == value:
            return item


if __name__ == '__main__':
    a = Point(x=1, y=2, z=4)
    b = Point(2, 3, 4)
    c = a + b
    print(c)