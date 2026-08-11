"""API controller for AI Summary Generator."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.domain.entities.user import User
from app.features.auth.dependencies import (
    require_admin,
    require_officer_or_admin,
    validate_csrf_token,
)
from app.core.slug import generate_slug
from app.features.summary.dependencies import get_summary_service
from app.features.summary.schemas import (
    DeletePromptResponse,
    GeneratedSummaryResponse,
    GenerateSummaryRequest,
    PromptTemplateCreate,
    PromptTemplateListResponse,
    PromptTemplateResponse,
    PromptTemplateUpdate,
    TestPromptRequest,
    TestPromptResponse,
    TogglePromptResponse,
)
from app.features.summary.service import SummaryService

router = APIRouter(prefix="/summary", tags=["summary"])


# Template routes MUST be registered before /{summary_id} to avoid path conflicts


@router.get(
    "/templates",
    response_model=PromptTemplateListResponse,
    dependencies=[Depends(require_officer_or_admin)],
)
async def list_prompt_templates(
    service: Annotated[SummaryService, Depends(get_summary_service)],
    _user: Annotated[User, Depends(require_officer_or_admin)],
    summary_type: str | None = Query(None),
    is_enabled: bool | None = Query(None),
) -> PromptTemplateListResponse:
    """List prompt templates (officers: read-only for summary generation UI)."""
    templates = await service.list_templates(
        summary_type=summary_type,
        is_enabled=is_enabled,
    )
    return PromptTemplateListResponse(templates=templates, total=len(templates))


@router.get(
    "/templates/{template_id}",
    response_model=PromptTemplateResponse,
    dependencies=[Depends(require_admin)],
)
async def get_prompt_template(
    template_id: str,
    service: Annotated[SummaryService, Depends(get_summary_service)],
    _user: Annotated[User, Depends(require_admin)],
) -> PromptTemplateResponse:
    """Get a prompt template by ID."""
    return await service.get_template(template_id)


@router.post(
    "/templates",
    response_model=PromptTemplateResponse,
    status_code=201,
    dependencies=[Depends(require_admin), Depends(validate_csrf_token)],
)
async def create_prompt_template(
    data: PromptTemplateCreate,
    service: Annotated[SummaryService, Depends(get_summary_service)],
    user: Annotated[User, Depends(require_admin)],
) -> PromptTemplateResponse:
    """Create a new prompt template."""
    return await service.create_template(data.model_dump(), user_id=user.id)


@router.put(
    "/templates/{template_id}",
    response_model=PromptTemplateResponse,
    dependencies=[Depends(require_admin), Depends(validate_csrf_token)],
)
async def update_prompt_template(
    template_id: str,
    data: PromptTemplateUpdate,
    service: Annotated[SummaryService, Depends(get_summary_service)],
    user: Annotated[User, Depends(require_admin)],
) -> PromptTemplateResponse:
    """Update a prompt template."""
    return await service.update_template(
        template_id,
        data.model_dump(exclude_unset=True),
        user_id=user.id,
    )


@router.delete(
    "/templates/{template_id}",
    response_model=DeletePromptResponse,
    dependencies=[Depends(require_admin), Depends(validate_csrf_token)],
)
async def delete_prompt_template(
    template_id: str,
    service: Annotated[SummaryService, Depends(get_summary_service)],
    user: Annotated[User, Depends(require_admin)],
) -> DeletePromptResponse:
    """Soft delete a prompt template."""
    await service.delete_template(template_id, user_id=user.id)
    return DeletePromptResponse(success=True, message="Prompt template deleted")


@router.patch(
    "/templates/{template_id}/toggle",
    response_model=TogglePromptResponse,
    dependencies=[Depends(require_admin), Depends(validate_csrf_token)],
)
async def toggle_prompt_template(
    template_id: str,
    service: Annotated[SummaryService, Depends(get_summary_service)],
    user: Annotated[User, Depends(require_admin)],
) -> TogglePromptResponse:
    """Toggle prompt template enabled status."""
    template = await service.toggle_template(template_id, user_id=user.id)
    return TogglePromptResponse(id=template.id, is_enabled=template.is_enabled)


@router.post(
    "/templates/{template_id}/duplicate",
    response_model=PromptTemplateResponse,
    status_code=201,
    dependencies=[Depends(require_admin), Depends(validate_csrf_token)],
)
async def duplicate_prompt_template(
    template_id: str,
    new_name: str = Query(...),
    new_slug: str | None = Query(None),
    service: Annotated[SummaryService, Depends(get_summary_service)] = None,
    user: Annotated[User, Depends(require_admin)] = None,
) -> PromptTemplateResponse:
    """Duplicate a prompt template."""
    slug = new_slug or generate_slug(new_name)
    return await service.duplicate_template(
        template_id, new_name, slug, user_id=user.id
    )


@router.post(
    "/templates/{template_id}/test",
    response_model=TestPromptResponse,
    dependencies=[Depends(require_admin), Depends(validate_csrf_token)],
)
async def test_prompt_template(
    template_id: str,
    data: TestPromptRequest,
    service: Annotated[SummaryService, Depends(get_summary_service)],
    _user: Annotated[User, Depends(require_admin)],
) -> TestPromptResponse:
    """Test a prompt template with sample data."""
    return await service.test_template(
        template_id,
        data.sample_dataset,
        data.sample_metadata.model_dump(),
        data.column_mapping,
    )


@router.post(
    "/generate",
    response_model=GeneratedSummaryResponse,
    dependencies=[Depends(require_officer_or_admin), Depends(validate_csrf_token)],
)
async def generate_summary(
    data: GenerateSummaryRequest,
    service: Annotated[SummaryService, Depends(get_summary_service)],
    user: Annotated[User, Depends(require_officer_or_admin)],
) -> GeneratedSummaryResponse:
    """Generate an AI summary from processed report data."""
    return await service.generate_summary(
        dataset=data.dataset,
        metadata=data.metadata.model_dump(),
        prompt_template_id=data.prompt_template_id,
        summary_type=data.summary_type,
        column_mapping=data.column_mapping,
        user_id=user.id,
    )


@router.get(
    "/{summary_id}",
    response_model=GeneratedSummaryResponse,
    dependencies=[Depends(require_officer_or_admin)],
)
async def get_summary(
    summary_id: str,
    service: Annotated[SummaryService, Depends(get_summary_service)],
    _user: Annotated[User, Depends(require_officer_or_admin)],
) -> GeneratedSummaryResponse:
    """Get a generated summary by ID."""
    return await service.get_summary(summary_id)
