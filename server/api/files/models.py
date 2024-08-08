from pydantic import BaseModel, Field

class contentValue(BaseModel):
    path: str
    use_key: bool
    robot_address: str = Field(..., description="robot ip address")



class contentParams(BaseModel):
    params: contentValue = Field(..., description="create a new run command")



