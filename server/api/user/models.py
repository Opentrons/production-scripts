from pydantic import BaseModel, Field


class Registers(BaseModel):
    username: str = Field(..., description="login name")
    password: str = Field(..., description="login password")


class UserMessage(BaseModel):
    params: Registers = Field(
        ..., description=" username and password"
    )
