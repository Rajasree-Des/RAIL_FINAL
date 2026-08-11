"""API controller for centralized application settings."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.domain.entities.user import User
from app.features.auth.dependencies import (
    get_current_active_user,
    require_admin,
    require_officer_or_admin,
    validate_csrf_token,
)
from app.features.settings.dependencies import get_settings_service
from app.features.settings.schemas import (
    DisplaySettingsResponse,
    SettingsExportResponse,
    SettingsImportRequest,
    SettingsImportResponse,
    SettingsResponse,
    SettingsUpdateRequest,
    SettingsUpdateResponse,
)
from app.features.settings.service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get(
    "",
    response_model=SettingsResponse,
    dependencies=[Depends(require_officer_or_admin)],
)
async def get_settings(
    service: Annotated[SettingsService, Depends(get_settings_service)],
    _user: Annotated[User, Depends(require_officer_or_admin)],
    category: str | None = Query(None),
    search: str | None = Query(None),
) -> SettingsResponse:
    """Get all settings grouped by category, optionally filtered."""
    return await service.get_settings(category=category, search=search)


@router.get("/display", response_model=DisplaySettingsResponse)
async def get_display_settings(
    service: Annotated[SettingsService, Depends(get_settings_service)],
    _user: Annotated[User, Depends(get_current_active_user)],
) -> DisplaySettingsResponse:
    """Resolved display/notification preferences for any signed-in user."""
    return await service.get_display_settings()


@router.put(
    "",
    response_model=SettingsUpdateResponse,
    dependencies=[Depends(require_admin), Depends(validate_csrf_token)],
)
async def update_settings(
    data: SettingsUpdateRequest,
    service: Annotated[SettingsService, Depends(get_settings_service)],
    user: Annotated[User, Depends(require_admin)],
) -> SettingsUpdateResponse:
    """Update one or more settings."""
    updates = [item.model_dump() for item in data.settings]
    return await service.update_settings(updates, user_id=user.id)


@router.post(
    "/reset/{category}",
    dependencies=[Depends(require_admin), Depends(validate_csrf_token)],
)
async def reset_category_settings(
    category: str,
    service: Annotated[SettingsService, Depends(get_settings_service)],
    user: Annotated[User, Depends(require_admin)],
) -> dict:
    """Reset a category to default values."""
    count = await service.reset_category(category, user_id=user.id)
    return {"success": True, "reset_count": count, "category": category}


@router.get(
    "/export",
    response_model=SettingsExportResponse,
    dependencies=[Depends(require_admin)],
)
async def export_settings(
    service: Annotated[SettingsService, Depends(get_settings_service)],
    _user: Annotated[User, Depends(require_admin)],
) -> SettingsExportResponse:
    """Export all effective settings as JSON."""
    return await service.export_settings()


@router.post(
    "/import",
    response_model=SettingsImportResponse,
    dependencies=[Depends(require_admin), Depends(validate_csrf_token)],
)
async def import_settings(
    data: SettingsImportRequest,
    service: Annotated[SettingsService, Depends(get_settings_service)],
    user: Annotated[User, Depends(require_admin)],
) -> SettingsImportResponse:
    """Import settings from JSON payload."""
    return await service.import_settings(
        data.settings,
        merge=data.merge,
        user_id=user.id,
    )
