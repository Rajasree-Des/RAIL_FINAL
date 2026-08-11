"""Dependency injection for rules feature."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.rules.repository import RuleRepository
from app.features.rules.service import RuleService
from app.infrastructure.database.session import get_db_session


async def get_rule_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RuleRepository:
    """Get rule repository instance."""
    return RuleRepository(session)


async def get_rule_service(
    repository: Annotated[RuleRepository, Depends(get_rule_repository)],
) -> RuleService:
    """Get rule service instance."""
    return RuleService(repository)
