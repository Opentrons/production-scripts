from enum import Enum
from dataclasses import dataclass
from typing import Optional


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
    auto_upload: bool
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
