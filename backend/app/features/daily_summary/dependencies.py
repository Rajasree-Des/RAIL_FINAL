"""Dependency injection for daily summary feature."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.daily_summary.service import DailySummaryService
from app.infrastructure.database.session import get_db_session


async def get_daily_summary_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DailySummaryService:
    return DailySummaryService(session)
