"""Seed default AI prompt templates."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.summary.seeds.default_prompts import DEFAULT_PROMPT_TEMPLATES
from app.infrastructure.database.models import AiPromptTemplateModel


async def seed_prompt_templates(session: AsyncSession) -> None:
    """Seed default prompt templates if none exist."""
    result = await session.execute(select(AiPromptTemplateModel.id).limit(1))
    if result.scalar_one_or_none():
        return

    for template_data in DEFAULT_PROMPT_TEMPLATES:
        template = AiPromptTemplateModel(**template_data)
        session.add(template)

    await session.commit()
