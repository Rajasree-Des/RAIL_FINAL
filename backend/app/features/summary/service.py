"""Service layer for AI Summary Generator."""

import json
import time
from typing import Any

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.features.summary.llm.base import LLMClient
from app.features.summary.llm.openai_client import MockLLMClient, OpenAICompatibleClient
from app.features.summary.preview_builder import PreviewBuilder
from app.features.summary.prompt_renderer import PromptRenderer
from app.features.summary.repository import SummaryRepository
from app.features.summary.schemas import (
    GeneratedSummaryResponse,
    PromptTemplateListItem,
    PromptTemplateResponse,
    ReportStatisticsResponse,
    TestPromptResponse,
)
from app.features.summary.statistics_builder import StatisticsBuilder
from app.infrastructure.database.models import AiPromptTemplateModel, GeneratedSummaryModel


class SummaryService:
    """Orchestrates summary generation and prompt template management."""

    def __init__(self, repository: SummaryRepository, llm_client: LLMClient | None = None):
        self.repository = repository
        self.statistics_builder = StatisticsBuilder()
        self.preview_builder = PreviewBuilder()
        self.prompt_renderer = PromptRenderer()
        self._llm = llm_client or self._create_llm_client()

    @staticmethod
    def _create_llm_client() -> LLMClient:
        if settings.summary_use_mock_llm or not settings.openai_api_key:
            return MockLLMClient()
        return OpenAICompatibleClient()

    @staticmethod
    def _template_to_response(model: AiPromptTemplateModel) -> PromptTemplateResponse:
        return PromptTemplateResponse(
            id=model.id,
            name=model.name,
            slug=model.slug,
            summary_type=model.summary_type,
            description=model.description,
            system_prompt=model.system_prompt,
            user_prompt_template=model.user_prompt_template,
            output_format=model.output_format,
            max_tokens=model.max_tokens,
            temperature=model.temperature,
            is_enabled=model.is_enabled,
            is_default=model.is_default,
            template_id=model.template_id,
            is_deleted=model.is_deleted,
            created_by=model.created_by,
            updated_by=model.updated_by,
            created_at=model.created_at.isoformat(),
            updated_at=model.updated_at.isoformat(),
        )

    @staticmethod
    def _template_to_list_item(model: AiPromptTemplateModel) -> PromptTemplateListItem:
        return PromptTemplateListItem(
            id=model.id,
            name=model.name,
            slug=model.slug,
            summary_type=model.summary_type,
            description=model.description,
            is_enabled=model.is_enabled,
            is_default=model.is_default,
            max_tokens=model.max_tokens,
            temperature=model.temperature,
            created_at=model.created_at.isoformat(),
            updated_at=model.updated_at.isoformat(),
        )

    @staticmethod
    def _stats_to_response(stats) -> ReportStatisticsResponse:
        return ReportStatisticsResponse(**stats.to_dict())

    async def list_templates(
        self,
        summary_type: str | None = None,
        is_enabled: bool | None = None,
    ) -> list[PromptTemplateListItem]:
        models = await self.repository.list_templates(
            summary_type=summary_type,
            is_enabled=is_enabled,
        )
        return [self._template_to_list_item(m) for m in models]

    async def get_template(self, template_id: str) -> PromptTemplateResponse:
        model = await self.repository.get_template_by_id(template_id)
        if not model:
            raise NotFoundError("PromptTemplate", template_id)
        return self._template_to_response(model)

    async def create_template(
        self,
        data: dict[str, Any],
        user_id: str | None = None,
    ) -> PromptTemplateResponse:
        if await self.repository.slug_exists(data["slug"]):
            raise ValidationError(f"Slug already exists: {data['slug']}")
        model = await self.repository.create_template(data, user_id)
        return self._template_to_response(model)

    async def update_template(
        self,
        template_id: str,
        data: dict[str, Any],
        user_id: str | None = None,
    ) -> PromptTemplateResponse:
        if "slug" in data and data["slug"]:
            if await self.repository.slug_exists(data["slug"], exclude_id=template_id):
                raise ValidationError(f"Slug already exists: {data['slug']}")

        model = await self.repository.update_template(template_id, data, user_id)
        if not model:
            raise NotFoundError("PromptTemplate", template_id)
        return self._template_to_response(model)

    async def delete_template(self, template_id: str, user_id: str | None = None) -> bool:
        success = await self.repository.delete_template(template_id, user_id)
        if not success:
            raise NotFoundError("PromptTemplate", template_id)
        return True

    async def toggle_template(
        self,
        template_id: str,
        user_id: str | None = None,
    ) -> PromptTemplateResponse:
        model = await self.repository.toggle_template(template_id, user_id)
        if not model:
            raise NotFoundError("PromptTemplate", template_id)
        return self._template_to_response(model)

    async def duplicate_template(
        self,
        template_id: str,
        new_name: str,
        new_slug: str,
        user_id: str | None = None,
    ) -> PromptTemplateResponse:
        if await self.repository.slug_exists(new_slug):
            raise ValidationError(f"Slug already exists: {new_slug}")
        model = await self.repository.duplicate_template(
            template_id, new_name, new_slug, user_id
        )
        if not model:
            raise NotFoundError("PromptTemplate", template_id)
        return self._template_to_response(model)

    async def get_summary(self, summary_id: str) -> GeneratedSummaryResponse:
        model = await self.repository.get_summary_by_id(summary_id)
        if not model:
            raise NotFoundError("GeneratedSummary", summary_id)
        return self._summary_to_response(model)

    async def generate_summary(
        self,
        dataset: list[dict[str, Any]],
        metadata: dict[str, Any],
        prompt_template_id: str | None = None,
        summary_type: str | None = None,
        column_mapping: dict[str, str] | None = None,
        user_id: str | None = None,
    ) -> GeneratedSummaryResponse:
        if len(dataset) > settings.summary_max_input_rows:
            raise ValidationError(
                f"Dataset exceeds maximum of {settings.summary_max_input_rows} rows"
            )

        template = await self._resolve_template(prompt_template_id, summary_type)

        stats = self.statistics_builder.build(dataset, metadata, column_mapping)
        preview_text = self.preview_builder.build_text(dataset)
        stats_dict = stats.to_dict()
        meta_dict = dict(metadata)

        system_prompt = self.prompt_renderer.render_system_prompt(template.system_prompt)
        user_prompt = self.prompt_renderer.render_user_prompt(
            template.user_prompt_template,
            stats_dict,
            meta_dict,
            preview_text,
        )

        start = time.time()
        try:
            llm_response = await self._llm.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=template.max_tokens,
                temperature=template.temperature,
            )
            content = llm_response.content
            model_used = llm_response.model
            token_usage = {
                "prompt_tokens": llm_response.prompt_tokens,
                "completion_tokens": llm_response.completion_tokens,
                "total_tokens": llm_response.total_tokens,
            }
            status = "completed"
            error_message = None
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            await self.repository.create_summary(
                {
                    "prompt_template_id": template.id,
                    "summary_type": template.summary_type,
                    "content": "",
                    "metadata_json": json.dumps(meta_dict),
                    "statistics_json": json.dumps(stats_dict),
                    "generation_time_ms": elapsed,
                    "status": "failed",
                    "error_message": str(e),
                },
                user_id,
            )
            raise ValidationError(f"Summary generation failed: {e}") from e

        elapsed = (time.time() - start) * 1000

        saved = await self.repository.create_summary(
            {
                "prompt_template_id": template.id,
                "summary_type": template.summary_type,
                "content": content,
                "metadata_json": json.dumps(meta_dict),
                "statistics_json": json.dumps(stats_dict),
                "model_used": model_used,
                "token_usage_json": json.dumps(token_usage),
                "generation_time_ms": elapsed,
                "status": status,
                "error_message": error_message,
            },
            user_id,
        )

        return self._summary_to_response(saved, stats)

    async def test_template(
        self,
        template_id: str,
        sample_dataset: list[dict[str, Any]],
        sample_metadata: dict[str, Any],
        column_mapping: dict[str, str] | None = None,
    ) -> TestPromptResponse:
        template = await self.repository.get_template_by_id(template_id)
        if not template:
            raise NotFoundError("PromptTemplate", template_id)

        stats = self.statistics_builder.build(
            sample_dataset, sample_metadata, column_mapping
        )
        preview_text = self.preview_builder.build_text(sample_dataset)
        stats_dict = stats.to_dict()

        system_prompt = self.prompt_renderer.render_system_prompt(template.system_prompt)
        user_prompt = self.prompt_renderer.render_user_prompt(
            template.user_prompt_template,
            stats_dict,
            sample_metadata,
            preview_text,
        )

        start = time.time()
        llm_response = await self._llm.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=template.max_tokens,
            temperature=template.temperature,
        )
        elapsed = (time.time() - start) * 1000

        return TestPromptResponse(
            content=llm_response.content,
            statistics=self._stats_to_response(stats),
            rendered_user_prompt=user_prompt,
            generation_time_ms=elapsed,
            model_used=llm_response.model,
        )

    async def _resolve_template(
        self,
        prompt_template_id: str | None,
        summary_type: str | None,
    ) -> AiPromptTemplateModel:
        if prompt_template_id:
            template = await self.repository.get_template_by_id(prompt_template_id)
            if not template:
                raise NotFoundError("PromptTemplate", prompt_template_id)
            if not template.is_enabled:
                raise ValidationError("Prompt template is disabled")
            return template

        if summary_type:
            template = await self.repository.get_default_template(summary_type)
            if not template:
                raise NotFoundError("PromptTemplate", f"default:{summary_type}")
            return template

        raise ValidationError("Either prompt_template_id or summary_type is required")

    def _summary_to_response(
        self,
        model: GeneratedSummaryModel,
        stats=None,
    ) -> GeneratedSummaryResponse:
        stats_dict = self.repository.deserialize_json(model.statistics_json)
        if stats:
            stats_response = self._stats_to_response(stats)
        else:
            stats_response = ReportStatisticsResponse(**stats_dict)

        return GeneratedSummaryResponse(
            id=model.id,
            summary_type=model.summary_type,
            content=model.content,
            statistics=stats_response,
            prompt_template_id=model.prompt_template_id,
            generation_time_ms=model.generation_time_ms or 0.0,
            model_used=model.model_used,
            created_at=model.created_at.isoformat(),
        )
