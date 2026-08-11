"""Tests for prompt renderer."""

from app.features.summary.prompt_renderer import PromptRenderer


class TestPromptRenderer:
    def setup_method(self):
        self.renderer = PromptRenderer()

    def test_render_user_prompt(self):
        template = "Total: {{ statistics.total_complaints }}"
        result = self.renderer.render_user_prompt(
            template,
            {"total_complaints": 100},
            {"report_name": "Test"},
            "preview text",
        )
        assert "100" in result

    def test_render_system_includes_guardrails(self):
        result = self.renderer.render_system_prompt("Custom instruction.")
        assert "Do NOT perform any calculations" in result
        assert "Custom instruction" in result
