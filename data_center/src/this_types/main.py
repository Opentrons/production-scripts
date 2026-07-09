from enum import Enum
from dataclasses import dataclass
from typing import Optional, Union, Literal
from ..product_name import normalize_product_name


class OS(Enum):
    Windows = 'windows'
    Mac = 'mac'
    Linux = 'linux'


@dataclass(kw_only=True)
class TestPlanInterface:
    _id: str
    date: str
    product: str
    test_name: list[str]
    barcode: str
    fixture_name: str
    fixture_ip: str
    auto_upload: Union[bool, int]
    link: str


@dataclass()
class UploadResult:
    success: bool
    test_result: Optional[str]
    zip_success: bool
    sheet_link: str
    move_success: Union[str, bool]
    test_all_items: Optional[bool]
    tracking_sheet: str

class ProductionName(Enum):
    Robot = "Robot"
    PVTRobot = "PVTRobot"
    PVTRobotUltima = "PVTRobotUltima"
    PVTPipette = "PVTPipette"
    P50S = "P50S"
    P1000S = "P1000S"
    P50M = "P50M"
    P1000M = "P1000M"
    P50S_Millipore = "P50S Millipore"
    P1000S_Millipore = "P1000S Millipore"
    P50M_Ultima = "P50M Ultima"
    P1000M_Ultima = "P1000M Ultima"
    P50M_Millipore = "P50M Millipore"
    P1000M_Millipore = "P1000M Millipore"

    @classmethod
    def get_production_by_value(cls, value: str):
        """根据字符串值获取对应的枚举成员

        Args:
            value: 要查找的字符串值

        Returns:
            对应的枚举成员，如果找不到则返回 None
        """
        try:
            return cls(normalize_product_name(value))
        except ValueError:
            # 如果直接使用 cls(value) 失败，尝试不区分大小写或去除空格的匹配
            value_normalized = normalize_product_name(value)

            # 方式1: 遍历所有枚举成员进行匹配
            for member in cls:
                if normalize_product_name(member.value) == value_normalized:
                    return member

            # 方式2: 如果不区分大小写匹配
            value_lower = value_normalized.lower()
            for member in cls:
                if member.value.lower() == value_lower:
                    return member

            return None


class TestName(Enum):
    AssemblyQC = 1
    GantryStress = 2
    XY_BeltCalibration = 3
    SpeedAndCurrent = 4
    Gravimetric = 5

    @classmethod
    def get_test_name_by_value(cls, value: str):
        if 'assembly' in value:
            return cls.AssemblyQC
        elif 'stress' in value:
            return cls.GantryStress
        elif 'belt_calibration' in value:
            return cls.XY_BeltCalibration
        elif 'speed' in value:
            return cls.SpeedAndCurrent
        else:
            return None

UploadEnv = Literal['debug', 'production']

@dataclass()
class UploadOneUnitInterface:
    file_local: str
    file_local_path: str
    production_name: ProductionName
    test_name: TestName
    sn: str
    csv_id: Optional[str] = None
    zip_path: Optional[str] = None
