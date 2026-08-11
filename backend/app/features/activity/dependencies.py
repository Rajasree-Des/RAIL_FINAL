"""FastAPI dependencies for activity feature."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.activity.service import ActivityService
from app.infrastructure.database.session import get_db_session


async def get_activity_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ActivityService:
    return ActivityService(session)
