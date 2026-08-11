"""LLM client adapters for summary generation."""

from app.features.summary.llm.base import LLMClient, LLMResponse
from app.features.summary.llm.openai_client import OpenAICompatibleClient

__all__ = ["LLMClient", "LLMResponse", "OpenAICompatibleClient"]
