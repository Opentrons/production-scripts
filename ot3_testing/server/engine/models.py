from typing import Optional, Union, Dict, List
from pydantic import BaseModel


class DeviceName(BaseModel):
    ip: str
    name: str


class Axis(BaseModel):
    mount: Union[None, str] = None
    target: Union[None, str] = None


class MovePoint(BaseModel):
    mount: str
    point: Dict[str, float]
    target: Union[None, str] = None


class OTAxis(BaseModel):
    axis: List[str]
