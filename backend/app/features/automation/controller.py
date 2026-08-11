"""API controller for automation orchestration."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.domain.entities.user import User
from app.features.auth.dependencies import require_admin, validate_csrf_token
from app.features.automation.dependencies import (
    get_automation_service,
    verify_service_token,
)
from app.features.automation.schemas import (
    AutomationCallbackRequest,
    AutomationControlResponse,
    AutomationHistoryResponse,
    AutomationLogsResponse,
    AutomationProfileCreate,
    AutomationProfileListResponse,
    AutomationProfileResponse,
    AutomationProfileUpdate,
    AutomationRunRequest,
    AutomationRunResponse,
    AutomationStatusResponse,
)
from app.features.automation.service import AutomationService

router = APIRouter(prefix="/automation", tags=["automation"])


@router.get(
    "/status",
    response_model=AutomationStatusResponse,
    dependencies=[Depends(require_admin)],
)
async def get_automation_status(
    service: Annotated[AutomationService, Depends(get_automation_service)],
    _user: Annotated[User, Depends(require_admin)],
) -> AutomationStatusResponse:
    """Dashboard status: active run, last run, success rate."""
    return await service.get_status()


@router.get(
    "/history",
    response_model=AutomationHistoryResponse,
    dependencies=[Depends(require_admin)],
)
async def get_automation_history(
    service: Annotated[AutomationService, Depends(get_automation_service)],
    _user: Annotated[User, Depends(require_admin)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> AutomationHistoryResponse:
    """Past automation runs."""
    return await service.get_history(limit=limit, offset=offset)


@router.get(
    "/logs",
    response_model=AutomationLogsResponse,
    dependencies=[Depends(require_admin)],
)
async def get_automation_logs(
    service: Annotated[AutomationService, Depends(get_automation_service)],
    _user: Annotated[User, Depends(require_admin)],
    run_id: str | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
) -> AutomationLogsResponse:
    """Logs for active or specified run."""
    return await service.get_logs(run_id=run_id, limit=limit)


@router.post(
    "/run",
    response_model=AutomationRunResponse,
    dependencies=[Depends(require_admin), Depends(validate_csrf_token)],
)
async def run_automation(
    data: AutomationRunRequest,
    service: Annotated[AutomationService, Depends(get_automation_service)],
    user: Annotated[User, Depends(require_admin)],
) -> AutomationRunResponse:
    """Start automation run via standalone engine."""
    return await service.start_run(data.profile_id, user_id=user.id)


@router.post(
    "/stop",
    response_model=AutomationControlResponse,
    dependencies=[Depends(require_admin), Depends(validate_csrf_token)],
)
async def stop_automation(
    service: Annotated[AutomationService, Depends(get_automation_service)],
    _user: Annotated[User, Depends(require_admin)],
) -> AutomationControlResponse:
    """Stop active automation run."""
    return await service.stop_run()


@router.post(
    "/pause",
    response_model=AutomationControlResponse,
    dependencies=[Depends(require_admin), Depends(validate_csrf_token)],
)
async def pause_automation(
    service: Annotated[AutomationService, Depends(get_automation_service)],
    _user: Annotated[User, Depends(require_admin)],
) -> AutomationControlResponse:
    """Pause active automation run."""
    return await service.pause_run()


@router.post(
    "/resume",
    response_model=AutomationControlResponse,
    dependencies=[Depends(require_admin), Depends(validate_csrf_token)],
)
async def resume_automation(
    service: Annotated[AutomationService, Depends(get_automation_service)],
    _user: Annotated[User, Depends(require_admin)],
) -> AutomationControlResponse:
    """Resume paused automation run."""
    return await service.resume_run()


@router.post(
    "/callback",
    dependencies=[Depends(verify_service_token)],
)
async def automation_callback(
    data: AutomationCallbackRequest,
    service: Annotated[AutomationService, Depends(get_automation_service)],
) -> dict:
    """Internal callback from automation-engine (not for UI)."""
    await service.handle_callback(data.model_dump())
    return {"success": True}


# Profile management (admin configures automation)


@router.get(
    "/profiles",
    response_model=AutomationProfileListResponse,
    dependencies=[Depends(require_admin)],
)
async def list_profiles(
    service: Annotated[AutomationService, Depends(get_automation_service)],
    _user: Annotated[User, Depends(require_admin)],
) -> AutomationProfileListResponse:
    return await service.list_profiles()


@router.post(
    "/profiles",
    response_model=AutomationProfileResponse,
    status_code=201,
    dependencies=[Depends(require_admin), Depends(validate_csrf_token)],
)
async def create_profile(
    data: AutomationProfileCreate,
    service: Annotated[AutomationService, Depends(get_automation_service)],
    user: Annotated[User, Depends(require_admin)],
) -> AutomationProfileResponse:
    return await service.create_profile(data, user_id=user.id)


@router.put(
    "/profiles/{profile_id}",
    response_model=AutomationProfileResponse,
    dependencies=[Depends(require_admin), Depends(validate_csrf_token)],
)
async def update_profile(
    profile_id: str,
    data: AutomationProfileUpdate,
    service: Annotated[AutomationService, Depends(get_automation_service)],
    user: Annotated[User, Depends(require_admin)],
) -> AutomationProfileResponse:
    return await service.update_profile(profile_id, data, user_id=user.id)
