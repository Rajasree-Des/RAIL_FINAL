"""OpenAI-compatible LLM client using httpx."""

import logging

import httpx

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.features.summary.llm.base import LLMClient, LLMResponse

logger = logging.getLogger(__name__)


class OpenAICompatibleClient(LLMClient):
    """HTTP client for OpenAI-compatible chat completion APIs."""

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> LLMResponse:
        if not settings.openai_api_key:
            raise ValidationError(
                "OpenAI API key not configured. Set OPENAI_API_KEY environment variable."
            )

        url = f"{settings.openai_api_base.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.openai_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": min(max_tokens, settings.summary_max_tokens),
            "temperature": temperature,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)

        if response.status_code != 200:
            logger.error("LLM API error: %s %s", response.status_code, response.text)
            raise ValidationError(f"LLM API error: {response.status_code}")

        data = response.json()
        choice = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        return LLMResponse(
            content=choice.strip(),
            model=data.get("model", settings.openai_model),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )


class MockLLMClient(LLMClient):
    """Mock LLM client for testing without API calls."""

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> LLMResponse:
        return LLMResponse(
            content=(
                "MOCK SUMMARY\n\n"
                "This is a mock summary generated for testing. "
                "The LLM was not called.\n\n"
                f"User prompt length: {len(user_prompt)} characters."
            ),
            model="mock-model",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        )
