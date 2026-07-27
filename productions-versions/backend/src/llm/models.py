from pydantic import BaseModel, Field


class SopTextChunkRequest(BaseModel):
    text: str = Field(min_length=1, max_length=120000)
    page_number: int | None = Field(default=None, ge=1)
    source: str = "sop"


class SopTextMaterial(BaseModel):
    part_number: str
    name: str = ""
    quantity: float | None = None
    unit: str | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)
    page_number: int | None = None
    source: str = "sop"


class SopTextChunkResponse(BaseModel):
    materials: list[SopTextMaterial] = Field(default_factory=list)
    model: str
    used_llm: bool = True
