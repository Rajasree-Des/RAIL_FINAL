"""Dependency injection for settings feature."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.settings.repository import SettingsRepository
from app.features.settings.service import SettingsService
from app.infrastructure.database.session import get_db_session


def get_settings_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SettingsRepository:
    return SettingsRepository(session)


def get_settings_service(
    repository: Annotated[SettingsRepository, Depends(get_settings_repository)],
) -> SettingsService:
    return SettingsService(repository)
