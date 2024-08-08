from pydantic import BaseModel, Field


class addDeviceValue(BaseModel):
    date: str = Field(..., description="adding date")
    auth: str = Field(..., description="adding author")
    device_name: str = Field(..., description="adding device_name")
    device_address: str = Field(..., description="adding device address")
    device_tag: str = Field(..., description="adding device tag")
    online: str = Field(..., description="adding status")


class addDeviceParam(BaseModel):
    params: addDeviceValue = Field(..., description="device status")


class removeDeviceValue(BaseModel):
    device_address: str = Field(..., description="adding device address")


class removeDeviceParam(BaseModel):
    params: removeDeviceValue = Field(..., description="device status")