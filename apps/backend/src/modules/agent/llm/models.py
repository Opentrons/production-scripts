"""Domain models consumed by the LLM integration."""

from pydantic import BaseModel, Field


class SopSemanticDecision(BaseModel):
    event_id: str = ""
    page_numbers: list[int] = Field(default_factory=list)
    action: str = ""
    target: str = ""
    location: str = ""
    quantity_delta: float = 0
    accumulate: bool = False
    duplicate_of: str | None = None
    reason: str = ""
    evidence: str = ""


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
    quantity_explanation: str = ""
    quantity_decisions: list[SopSemanticDecision] = Field(default_factory=list)


class SopSemanticMaterial(BaseModel):
    part_number: str
    name: str = ""
    added_quantity: float = Field(default=0, ge=0)
    reference_quantity: float = Field(default=0, ge=0)
    final_quantity: float | None = Field(default=None, ge=0)
    confidence: float = Field(default=0.0, ge=0, le=1)
    reason: str = ""
    decisions: list[SopSemanticDecision] = Field(default_factory=list)


class SopTextChunkResponse(BaseModel):
    materials: list[SopTextMaterial] = Field(default_factory=list)
    model: str
    used_llm: bool = True
