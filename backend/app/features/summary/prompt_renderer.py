"""Jinja2-based prompt rendering for summary generation."""

from typing import Any

from jinja2 import BaseLoader, Environment, StrictUndefined


class PromptRenderer:
    """Render prompt templates with statistics and metadata."""

    SYSTEM_GUARDRAILS = """You are a railway report summarization assistant.
RULES:
- Use ONLY the statistics and facts provided below.
- Do NOT perform any calculations, estimates, or infer new numbers.
- If a metric is not provided, state "not available" rather than guessing.
- Format output according to the template instructions."""

    def __init__(self):
        self._env = Environment(
            loader=BaseLoader(),
            undefined=StrictUndefined,
            autoescape=False,
        )

    def render_system_prompt(self, template_system: str) -> str:
        """Combine guardrails with template-specific system prompt."""
        return f"{self.SYSTEM_GUARDRAILS}\n\n{template_system.strip()}"

    def render_user_prompt(
        self,
        user_template: str,
        statistics: dict[str, Any],
        metadata: dict[str, Any],
        preview: str | list[dict[str, Any]],
    ) -> str:
        """Render user prompt with context variables."""
        context = {
            "statistics": statistics,
            "metadata": metadata,
            "preview": preview,
        }
        template = self._env.from_string(user_template)
        return template.render(**context)
