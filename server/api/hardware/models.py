from pydantic import BaseModel, Field


class BuilderValue(BaseModel):
    ip: str = Field(..., description="device address")


class BuilderParam(BaseModel):
    params: BuilderValue = Field(..., description="device address")


class HomeValue(BaseModel):
    device: int = Field(..., description="device index")
    axis: str = Field(..., description="home axis")


class HomeParam(BaseModel):
    params: HomeValue = Field(..., description="device address")


class MoveToValue(BaseModel):
    device: int = Field(..., description="device index")
    mount: str = Field(..., description="mount")
    point: dict = Field(..., description="target point")


class MoveToParam(BaseModel):
    params: MoveToValue = Field(..., description="move to")


class MoveRelValue(BaseModel):
    device: int = Field(..., description="device index")
    mount: str = Field(..., description="mount")
    point: dict = Field(..., description="target point")


class MoveRelParam(BaseModel):
    params: MoveToValue = Field(..., description="move rel")




class TestOnlineValue(BaseModel):
    ipaddress: str = Field(..., description="target ip address")


class TestOnlineParam(BaseModel):
    params: TestOnlineValue = Field(..., description="target ip address")
