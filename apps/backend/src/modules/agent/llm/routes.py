from fastapi import APIRouter, HTTPException

from modules.agent.llm.models import SopTextChunkRequest, SopTextChunkResponse
from modules.agent.llm.service import LLMConfigurationError, llm_service

router = APIRouter(prefix="/sop/ai", tags=["sop-ai"])


@router.post("/extract-materials", response_model=SopTextChunkResponse)
def extract_materials(payload: SopTextChunkRequest) -> SopTextChunkResponse:
    try:
        materials = llm_service.extract_sop_materials(payload)
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return SopTextChunkResponse(materials=materials, model=llm_service.model)
