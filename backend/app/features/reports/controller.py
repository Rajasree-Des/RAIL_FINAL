"""API routes for manual report generation from configuration pages."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import User
from app.features.auth.dependencies import require_officer_or_admin, validate_csrf_token
from app.features.reports.schemas import (
    ManualGenerateRequest,
    ManualGenerateResponse,
    ManualRunStatusResponse,
    OutputPreviewRequest,
    OutputPreviewResponse,
    ReportConfigResponse,
    SaveReportConfigRequest,
    SaveReportConfigResponse,
)
from app.features.reports.service import ManualReportService
from app.features.reports.slug_map import resolve_manual_slug
from app.infrastructure.database.session import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


def get_manual_report_service() -> ManualReportService:
    return ManualReportService()


@router.post(
    "/{slug}/generate",
    response_model=ManualGenerateResponse,
    dependencies=[Depends(validate_csrf_token)],
)
async def generate_manual_report(
    slug: str,
    body: ManualGenerateRequest,
    user: Annotated[User, Depends(require_officer_or_admin)],
    service: Annotated[ManualReportService, Depends(get_manual_report_service)],
) -> ManualGenerateResponse:
    """Start a single-report CDP automation run using current page configuration."""
    return await service.generate(slug, body, user_id=user.id)


@router.get(
    "/runs/{run_id}",
    response_model=ManualRunStatusResponse,
)
async def get_manual_run_status(
    run_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(require_officer_or_admin)],
    service: Annotated[ManualReportService, Depends(get_manual_report_service)],
    report_slug: str | None = None,
) -> ManualRunStatusResponse:
    """Poll manual run progress and resolve current-run artifact URLs."""
    return await service.get_run_status(
        db,
        run_id,
        expected_slug=resolve_manual_slug(report_slug) if report_slug else None,
    )


@router.put(
    "/{slug}/config",
    response_model=SaveReportConfigResponse,
    dependencies=[Depends(validate_csrf_token)],
)
async def save_report_config(
    slug: str,
    body: SaveReportConfigRequest,
    user: Annotated[User, Depends(require_officer_or_admin)],
    service: Annotated[ManualReportService, Depends(get_manual_report_service)],
) -> SaveReportConfigResponse:
    """Persist configuration for future and daily runs."""
    return await service.save_config(slug, body, user_id=user.id)


@router.get("/{slug}/output-columns")
async def get_output_columns(
    slug: str,
    _user: Annotated[User, Depends(require_officer_or_admin)],
    service: Annotated[ManualReportService, Depends(get_manual_report_service)],
) -> dict[str, Any]:
    """Return selectable output columns for a report configuration page."""
    return await service.get_output_columns(slug)


@router.get("/{slug}/config", response_model=ReportConfigResponse)
async def get_report_config(
    slug: str,
    user: Annotated[User, Depends(require_officer_or_admin)],
    service: Annotated[ManualReportService, Depends(get_manual_report_service)],
) -> ReportConfigResponse:
    return await service.get_report_config(slug, user_id=user.id)


@router.post(
    "/{slug}/output-preview",
    response_model=OutputPreviewResponse,
)
async def output_preview(
    slug: str,
    body: OutputPreviewRequest,
    _user: Annotated[User, Depends(require_officer_or_admin)],
    service: Annotated[ManualReportService, Depends(get_manual_report_service)],
) -> OutputPreviewResponse:
    """Project cached processed data to the requested output columns (no CDP)."""
    return await service.output_preview(slug, body)


@router.post(
    "/{slug}/preview",
    response_model=OutputPreviewResponse,
)
async def preview_alias(
    slug: str,
    body: OutputPreviewRequest,
    _user: Annotated[User, Depends(require_officer_or_admin)],
    service: Annotated[ManualReportService, Depends(get_manual_report_service)],
) -> OutputPreviewResponse:
    """Canonical preview alias — same handler as output-preview."""
    return await service.output_preview(slug, body)
