from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterator, Optional

# 产品型号
class Productions(Enum):
    ROBOT = "Robot"
    P50S = "P50S"
    P1000S = "P1000S"
    P50M = "P50M"
    P1000M = "P1000M"
    P2HH = "P2HH"
    P1KH = "P1KH"
    GRIPPER = "Gripper"

    @classmethod
    def from_string(cls, value: str) -> Optional["Productions"]:
        if isinstance(value, cls):
            return value
        if not value or not isinstance(value, str):
            return None

        value = value.strip()

        for production in cls:
            if production.value == value:
                return production

        value_lower = value.lower()
        for production in cls:
            if production.value.lower() == value_lower:
                return production

        return None

# 产品类型，OEM厂商
class ProductionTypes(Enum):
    Ultima = "Ultima"
    Millipore = "Millipore"
    Opentrons = "Opentrons"
    Sophion = "Sophion"

# 测试类型
class TestTypes(Enum):
    Assembly_QC = "assembly_qc"
    Speed_Current_Test = "speed_current_test"
    Gravimetric = "gravimetric"
    BurnIn_Result = "burn_in_result_test"
    BurnIn_Record = "burn_in_record_test"
    Pressure_Leakage_Test = "pressure_leakage_test"
    ZStage_Test = "z_stage_test"
    Diagnostic = "diagnostic"
    XY_Calibration = "xy_calibration"
    Gantry_Stress = "gantry_stress_test"
    Leveling_Test = "leveling_test"

    @classmethod
    def from_string(cls, value: str) -> Optional["TestTypes"]:
        if isinstance(value, cls):
            return value
        if not value or not isinstance(value, str):
            return None

        value = value.strip()

        for test_type in cls:
            if test_type.value == value:
                return test_type

        value_lower = value.lower()
        for test_type in cls:
            if test_type.value.lower() == value_lower:
                return test_type

        return None


@dataclass
class FileDescription:
    file_path: str
    data: dict[str, Any]

    @classmethod
    def build(cls, file_path: str, meta: dict[str, Any] | None = None):
        from ..parsers import extract_csv

        raw_data = extract_csv(file_path, meta=meta)
        if not raw_data:
            return None
        return cls.from_raw(file_path=file_path, raw_data=raw_data)

    @classmethod
    def from_raw(cls, file_path: str, raw_data: dict[str, Any]) -> "FileDescription":
        data = {
            "metadata": {},
            "finished": False,
            "file_name": "",
            "sn": "",
            "model": "NA",
            "kind_stage_type": "NA",
            "kind_oem_type": "NA",
            "test_type": "NA",
            "error": "False",
            **raw_data,
        }
        data["file_path"] = file_path
        data["test_type"] = TestTypes.from_string(data.get("test_type")) or data.get("test_type")
        return cls(file_path=file_path, data=data)

    @property
    def test_type(self) -> Optional[TestTypes]:
        return TestTypes.from_string(self.data.get("test_type"))

    @property
    def model(self) -> Optional[Productions]:
        return Productions.from_string(self.data.get("model"))

    @property
    def is_parse_successful(self) -> bool:
        return self.data.get("error") == "False" and self.data.get("failed") is not True

    @property
    def error(self) -> Optional[str]:
        return self.data.get("error")

    @property
    def finished(self) -> bool:
        return bool(self.data.get("finished"))

    def attach_upload_context(self, zip_file=None) -> None:
        self.data["zip_file"] = zip_file

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def items(self):
        return self.data.items()

    def keys(self):
        return self.data.keys()

    def values(self):
        return self.data.values()

    def to_dict(self) -> dict[str, Any]:
        return dict(self.data)

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.data[key] = value

    def __contains__(self, key: object) -> bool:
        return key in self.data

    def __iter__(self) -> Iterator[str]:
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)
