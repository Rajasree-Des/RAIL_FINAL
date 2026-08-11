"""API controller for Report Configuration Templates."""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.domain.entities.user import User
from app.features.activity.emit import emit_activity
from app.features.auth.dependencies import require_admin, validate_csrf_token
from app.features.templates.dependencies import get_template_service
from app.features.templates.schemas import (
    DeleteResponse,
    DuplicateTemplateRequest,
    TemplateCreate,
    TemplateListResponse,
    TemplateResponse,
    TemplateUpdate,
    ToggleResponse,
    ValidationResult,
)
from app.features.templates.service import TemplateService

router = APIRouter(prefix="/admin/templates", tags=["templates"])


async def _emit_config_updated(user_id: str, message: str, slug: str | None = None) -> None:
    """Record CONFIG_UPDATED after the mutation transaction has committed."""
    await emit_activity(
        user_id=user_id,
        action="CONFIG_UPDATED",
        message=message,
        status="success",
        report_slug=slug,
    )


@router.get(
    "",
    response_model=TemplateListResponse,
    summary="List all templates",
    description="Get a list of all report configuration templates.",
)
async def list_templates(
    service: Annotated[TemplateService, Depends(get_template_service)],
    _user: Annotated[User, Depends(require_admin)],
    enabled_only: bool = False,
) -> TemplateListResponse:
    """List all templates."""
    templates = await service.list_templates(enabled_only=enabled_only)
    return TemplateListResponse(
        templates=[asdict(t) for t in templates],
        total=len(templates),
    )


@router.get(
    "/{template_id}",
    response_model=TemplateResponse,
    summary="Get template by ID",
    description="Get a single template with all its configurations.",
)
async def get_template(
    template_id: str,
    service: Annotated[TemplateService, Depends(get_template_service)],
    _user: Annotated[User, Depends(require_admin)],
) -> TemplateResponse:
    """Get a template by ID."""
    template = await service.get_template(template_id)
    return TemplateResponse(**asdict(template))


@router.post(
    "",
    response_model=TemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create template",
    description="Create a new report configuration template.",
    dependencies=[Depends(validate_csrf_token)],
)
async def create_template(
    data: TemplateCreate,
    service: Annotated[TemplateService, Depends(get_template_service)],
    user: Annotated[User, Depends(require_admin)],
) -> TemplateResponse:
    """Create a new template."""
    template = await service.create_template(data.model_dump(), user.id)
    await _emit_config_updated(
        user.id,
        f"Report configuration '{template.name}' created",
        getattr(template, "slug", None),
    )
    return TemplateResponse(**asdict(template))


@router.put(
    "/{template_id}",
    response_model=TemplateResponse,
    summary="Update template",
    description="Update an existing report configuration template.",
    dependencies=[Depends(validate_csrf_token)],
)
async def update_template(
    template_id: str,
    data: TemplateUpdate,
    service: Annotated[TemplateService, Depends(get_template_service)],
    user: Annotated[User, Depends(require_admin)],
) -> TemplateResponse:
    """Update a template."""
    template = await service.update_template(
        template_id,
        data.model_dump(exclude_unset=True),
        user.id,
    )
    await _emit_config_updated(
        user.id,
        f"Report configuration '{template.name}' updated",
        getattr(template, "slug", None),
    )
    return TemplateResponse(**asdict(template))


@router.delete(
    "/{template_id}",
    response_model=DeleteResponse,
    summary="Delete template",
    description="Soft delete a report configuration template.",
    dependencies=[Depends(validate_csrf_token)],
)
async def delete_template(
    template_id: str,
    service: Annotated[TemplateService, Depends(get_template_service)],
    user: Annotated[User, Depends(require_admin)],
) -> DeleteResponse:
    """Delete a template."""
    await service.delete_template(template_id, user.id)
    await _emit_config_updated(user.id, "Report configuration deleted")
    return DeleteResponse(success=True, message="Template deleted successfully")


@router.post(
    "/{template_id}/duplicate",
    response_model=TemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Duplicate template",
    description="Create a copy of an existing template with a new name.",
    dependencies=[Depends(validate_csrf_token)],
)
async def duplicate_template(
    template_id: str,
    data: DuplicateTemplateRequest,
    service: Annotated[TemplateService, Depends(get_template_service)],
    user: Annotated[User, Depends(require_admin)],
) -> TemplateResponse:
    """Duplicate a template."""
    template = await service.duplicate_template(template_id, data.new_name, user.id)
    await _emit_config_updated(
        user.id,
        f"Report configuration duplicated as '{template.name}'",
        getattr(template, "slug", None),
    )
    return TemplateResponse(**asdict(template))


@router.patch(
    "/{template_id}/toggle",
    response_model=ToggleResponse,
    summary="Toggle template enabled status",
    description="Enable or disable a report configuration template.",
    dependencies=[Depends(validate_csrf_token)],
)
async def toggle_template(
    template_id: str,
    service: Annotated[TemplateService, Depends(get_template_service)],
    user: Annotated[User, Depends(require_admin)],
) -> ToggleResponse:
    """Toggle template enabled status."""
    template = await service.toggle_template(template_id, user.id)
    status_text = "enabled" if template.is_enabled else "disabled"
    await _emit_config_updated(
        user.id,
        f"Report configuration '{template.name}' {status_text}",
        getattr(template, "slug", None),
    )
    return ToggleResponse(
        id=template.id,
        is_enabled=template.is_enabled,
        message=f"Template {status_text} successfully",
    )


@router.post(
    "/{template_id}/test",
    response_model=ValidationResult,
    summary="Test template configuration",
    description="Validate the template configuration and return any errors or warnings.",
)
async def test_template(
    template_id: str,
    service: Annotated[TemplateService, Depends(get_template_service)],
    _user: Annotated[User, Depends(require_admin)],
) -> ValidationResult:
    """Validate template configuration."""
    result = await service.validate_template(template_id)
    return ValidationResult(**asdict(result))
