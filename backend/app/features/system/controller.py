"""API controller for system info and maintenance actions (admin only)."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import User
from app.features.auth.dependencies import require_admin, validate_csrf_token
from app.features.system.schemas import ClearCacheResponse, SystemInfoResponse
from app.features.system.service import SystemService
from app.infrastructure.database.session import get_db_session

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/info", response_model=SystemInfoResponse)
async def get_system_info(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _user: Annotated[User, Depends(require_admin)],
) -> SystemInfoResponse:
    """Live status of backend, database, CDP browser, automation, and storage."""
    return await SystemService(session).info()


@router.get("/export-logs")
async def export_logs(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _user: Annotated[User, Depends(require_admin)],
) -> Response:
    """Download administrative events as PDF (admin only)."""
    pdf_bytes = await SystemService(session).export_logs_pdf()
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"RailMadad_Administrative_Logs_{timestamp}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.post(
    "/clear-cache",
    response_model=ClearCacheResponse,
    dependencies=[Depends(validate_csrf_token)],
)
async def clear_cache(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    user: Annotated[User, Depends(require_admin)],
) -> ClearCacheResponse:
    """Clear in-memory caches and whitelisted disposable filesystem cache."""
    service = SystemService(session)
    result = await service.clear_cache()

    try:
        from app.features.activity.emit import emit_activity

        await emit_activity(
            user_id=user.id,
            action="CACHE_CLEARED",
            message="Cleared application caches",
            status="info",
        )
    except Exception:
        pass

    return result
