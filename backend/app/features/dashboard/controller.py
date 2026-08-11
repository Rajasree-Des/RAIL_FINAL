"""Authenticated dashboard summary API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import User
from app.features.auth.dependencies import get_current_active_user
from app.features.dashboard.analytics import DashboardAnalyticsService
from app.features.dashboard.schemas import (
    DashboardAnalyticsResponse,
    DashboardSummaryResponse,
)
from app.features.dashboard.service import DashboardService
from app.infrastructure.database.session import get_db_session

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
async def dashboard_summary(
    user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardSummaryResponse:
    """Live Home dashboard data derived from runs, artifacts, and the catalog."""
    return await DashboardService(session).summary(user.id)


@router.get("/analytics", response_model=DashboardAnalyticsResponse)
async def dashboard_analytics(
    _user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardAnalyticsResponse:
    """Operational insights aggregated from the latest completed run's outputs."""
    return await DashboardAnalyticsService(session).analytics()
