from pydantic import BaseModel, Field

class newRunCommandValue(BaseModel):
    date: str
    auth: str
    robot_name: str = Field(..., description="create a new run command")
    device_ip: str
    use_key: bool
    description: str
    cmd: str
    type: list
    params: list
    production: str


class newRunCommandParam(BaseModel):
    params: newRunCommandValue = Field(..., description="create a new run command")



