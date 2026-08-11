"""Dependency injection for summary feature."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.summary.repository import SummaryRepository
from app.features.summary.service import SummaryService
from app.infrastructure.database.session import get_db_session


async def get_summary_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SummaryRepository:
    return SummaryRepository(session)


async def get_summary_service(
    repository: Annotated[SummaryRepository, Depends(get_summary_repository)],
) -> SummaryService:
    return SummaryService(repository)
