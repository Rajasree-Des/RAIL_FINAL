"""Dependency injection for automation feature."""

import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.features.automation.engine_client import AutomationEngineClient
from app.features.automation.repository import AutomationRepository
from app.features.automation.service import AutomationService
from app.infrastructure.database.session import get_db_session


def get_automation_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AutomationRepository:
    return AutomationRepository(session)


def get_automation_engine_client() -> AutomationEngineClient:
    return AutomationEngineClient()


def get_automation_service(
    repository: Annotated[AutomationRepository, Depends(get_automation_repository)],
    engine: Annotated[AutomationEngineClient, Depends(get_automation_engine_client)],
) -> AutomationService:
    return AutomationService(repository, engine)


async def verify_service_token(
    authorization: str | None = Header(None),
) -> None:
    """Verify automation-engine service token for callback endpoints."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Service token required")
    token = authorization[7:]
    if not secrets.compare_digest(token, settings.automation_service_token):
        raise HTTPException(status_code=403, detail="Invalid service token")
