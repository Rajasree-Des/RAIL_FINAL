"""Dependency injection for templates feature."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.templates.repository import TemplateRepository
from app.features.templates.service import TemplateService
from app.infrastructure.database.session import get_db_session


async def get_template_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TemplateRepository:
    """Get template repository instance."""
    return TemplateRepository(session)


async def get_template_service(
    repository: Annotated[TemplateRepository, Depends(get_template_repository)],
) -> TemplateService:
    """Get template service instance."""
    return TemplateService(repository)
