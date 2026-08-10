"""Low-level OpenAI-compatible LLM integration used by production agents."""

from .service import LLMConfigurationError, LLMService, llm_service

__all__ = ["LLMConfigurationError", "LLMService", "llm_service"]
