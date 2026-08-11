"""Repository for AI prompt templates and generated summaries."""

import json
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import AiPromptTemplateModel, GeneratedSummaryModel


class SummaryRepository:
    """Data access for summary feature."""

    def __init__(self, session: AsyncSession):
        self._session = session

    # -------------------------------------------------------------------------
    # Prompt Templates
    # -------------------------------------------------------------------------

    async def list_templates(
        self,
        summary_type: str | None = None,
        is_enabled: bool | None = None,
        include_deleted: bool = False,
    ) -> list[AiPromptTemplateModel]:
        query = select(AiPromptTemplateModel)
        if not include_deleted:
            query = query.where(AiPromptTemplateModel.is_deleted == False)  # noqa: E712
        if summary_type:
            query = query.where(AiPromptTemplateModel.summary_type == summary_type)
        if is_enabled is not None:
            query = query.where(AiPromptTemplateModel.is_enabled == is_enabled)
        query = query.order_by(
            AiPromptTemplateModel.summary_type,
            AiPromptTemplateModel.is_default.desc(),
            AiPromptTemplateModel.name,
        )
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_template_by_id(self, template_id: str) -> AiPromptTemplateModel | None:
        query = (
            select(AiPromptTemplateModel)
            .where(AiPromptTemplateModel.id == template_id)
            .where(AiPromptTemplateModel.is_deleted == False)  # noqa: E712
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def get_template_by_slug(self, slug: str) -> AiPromptTemplateModel | None:
        query = (
            select(AiPromptTemplateModel)
            .where(AiPromptTemplateModel.slug == slug)
            .where(AiPromptTemplateModel.is_deleted == False)  # noqa: E712
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def get_default_template(
        self,
        summary_type: str,
    ) -> AiPromptTemplateModel | None:
        query = (
            select(AiPromptTemplateModel)
            .where(AiPromptTemplateModel.summary_type == summary_type)
            .where(AiPromptTemplateModel.is_default == True)  # noqa: E712
            .where(AiPromptTemplateModel.is_enabled == True)  # noqa: E712
            .where(AiPromptTemplateModel.is_deleted == False)  # noqa: E712
        )
        result = await self._session.execute(query)
        template = result.scalar_one_or_none()
        if template:
            return template

        query = (
            select(AiPromptTemplateModel)
            .where(AiPromptTemplateModel.summary_type == summary_type)
            .where(AiPromptTemplateModel.is_enabled == True)  # noqa: E712
            .where(AiPromptTemplateModel.is_deleted == False)  # noqa: E712
            .limit(1)
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def slug_exists(self, slug: str, exclude_id: str | None = None) -> bool:
        query = (
            select(AiPromptTemplateModel.id)
            .where(AiPromptTemplateModel.slug == slug)
            .where(AiPromptTemplateModel.is_deleted == False)  # noqa: E712
        )
        if exclude_id:
            query = query.where(AiPromptTemplateModel.id != exclude_id)
        result = await self._session.execute(query)
        return result.scalar_one_or_none() is not None

    async def create_template(
        self,
        data: dict[str, Any],
        user_id: str | None = None,
    ) -> AiPromptTemplateModel:
        if data.get("is_default"):
            await self._clear_default(data["summary_type"])

        template = AiPromptTemplateModel(
            **data,
            created_by=user_id,
            updated_by=user_id,
        )
        self._session.add(template)
        await self._session.commit()
        await self._session.refresh(template)
        return template

    async def update_template(
        self,
        template_id: str,
        data: dict[str, Any],
        user_id: str | None = None,
    ) -> AiPromptTemplateModel | None:
        template = await self.get_template_by_id(template_id)
        if not template:
            return None

        if data.get("is_default"):
            summary_type = data.get("summary_type", template.summary_type)
            await self._clear_default(summary_type, exclude_id=template_id)

        for key, value in data.items():
            if hasattr(template, key):
                setattr(template, key, value)
        template.updated_by = user_id

        await self._session.commit()
        await self._session.refresh(template)
        return template

    async def delete_template(self, template_id: str, user_id: str | None = None) -> bool:
        stmt = (
            update(AiPromptTemplateModel)
            .where(AiPromptTemplateModel.id == template_id)
            .where(AiPromptTemplateModel.is_deleted == False)  # noqa: E712
            .values(is_deleted=True, updated_by=user_id)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount > 0

    async def toggle_template(self, template_id: str, user_id: str | None = None) -> AiPromptTemplateModel | None:
        template = await self.get_template_by_id(template_id)
        if not template:
            return None
        template.is_enabled = not template.is_enabled
        template.updated_by = user_id
        await self._session.commit()
        await self._session.refresh(template)
        return template

    async def duplicate_template(
        self,
        template_id: str,
        new_name: str,
        new_slug: str,
        user_id: str | None = None,
    ) -> AiPromptTemplateModel | None:
        original = await self.get_template_by_id(template_id)
        if not original:
            return None

        new_template = AiPromptTemplateModel(
            name=new_name,
            slug=new_slug,
            summary_type=original.summary_type,
            description=original.description,
            system_prompt=original.system_prompt,
            user_prompt_template=original.user_prompt_template,
            output_format=original.output_format,
            max_tokens=original.max_tokens,
            temperature=original.temperature,
            is_enabled=False,
            is_default=False,
            template_id=original.template_id,
            created_by=user_id,
            updated_by=user_id,
        )
        self._session.add(new_template)
        await self._session.commit()
        await self._session.refresh(new_template)
        return new_template

    async def _clear_default(self, summary_type: str, exclude_id: str | None = None) -> None:
        stmt = (
            update(AiPromptTemplateModel)
            .where(AiPromptTemplateModel.summary_type == summary_type)
            .where(AiPromptTemplateModel.is_default == True)  # noqa: E712
        )
        if exclude_id:
            stmt = stmt.where(AiPromptTemplateModel.id != exclude_id)
        stmt = stmt.values(is_default=False)
        await self._session.execute(stmt)

    # -------------------------------------------------------------------------
    # Generated Summaries
    # -------------------------------------------------------------------------

    async def create_summary(
        self,
        data: dict[str, Any],
        user_id: str | None = None,
    ) -> GeneratedSummaryModel:
        summary = GeneratedSummaryModel(
            **data,
            created_by=user_id,
        )
        self._session.add(summary)
        await self._session.commit()
        await self._session.refresh(summary)
        return summary

    async def get_summary_by_id(self, summary_id: str) -> GeneratedSummaryModel | None:
        query = select(GeneratedSummaryModel).where(GeneratedSummaryModel.id == summary_id)
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    def serialize_json(data: dict[str, Any]) -> str:
        return json.dumps(data)

    @staticmethod
    def deserialize_json(data: str | None) -> dict[str, Any]:
        if not data:
            return {}
        return json.loads(data)
