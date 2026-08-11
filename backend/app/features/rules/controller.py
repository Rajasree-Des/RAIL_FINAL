"""API controller for Business Rules Engine."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.domain.entities.user import User
from app.features.auth.dependencies import require_admin, validate_csrf_token
from app.features.rules.dependencies import get_rule_repository, get_rule_service
from app.features.rules.engine.context import Dataset
from app.features.rules.engine.executor import RuleExecutor
from app.features.rules.repository import RuleRepository
from app.features.rules.schemas import (
    CategoryInfo,
    ExecuteRulesRequest,
    ExecuteRulesResult,
    FunctionInfo,
    HighlightInfo,
    ReorderRulesRequest,
    RuleCreate,
    RuleListItem,
    RuleListResponse,
    RuleResponse,
    RuleTestRequest,
    RuleTestResult,
    RuleUpdate,
    RuleValidationRequest,
    RuleValidationResult,
    StyleConfig,
)
from app.features.rules.service import RuleService

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("/", response_model=RuleListResponse, dependencies=[Depends(require_admin)])
async def list_rules(
    service: Annotated[RuleService, Depends(get_rule_service)],
    template_id: str | None = Query(None),
    category: str | None = Query(None),
    is_enabled: bool | None = Query(None),
) -> RuleListResponse:
    """List all rules with optional filters."""
    rules = await service.list_rules(
        template_id=template_id,
        category=category,
        is_enabled=is_enabled,
    )
    return RuleListResponse(rules=rules, total=len(rules))


@router.get("/categories", response_model=list[CategoryInfo], dependencies=[Depends(require_admin)])
async def get_categories(
    service: Annotated[RuleService, Depends(get_rule_service)],
) -> list[CategoryInfo]:
    """Get available rule categories and types."""
    return service.get_categories()


@router.get("/functions", response_model=list[FunctionInfo], dependencies=[Depends(require_admin)])
async def get_functions(
    service: Annotated[RuleService, Depends(get_rule_service)],
) -> list[FunctionInfo]:
    """Get available expression functions."""
    return service.get_functions()


@router.get("/templates/{template_id}", response_model=list[RuleListItem], dependencies=[Depends(require_admin)])
async def get_rules_for_template(
    template_id: str,
    service: Annotated[RuleService, Depends(get_rule_service)],
) -> list[RuleListItem]:
    """Get all rules for a specific template."""
    return await service.list_rules(template_id=template_id)


@router.get("/{rule_id}", response_model=RuleResponse, dependencies=[Depends(require_admin)])
async def get_rule(
    rule_id: str,
    service: Annotated[RuleService, Depends(get_rule_service)],
) -> RuleResponse:
    """Get a rule by ID."""
    return await service.get_rule(rule_id)


@router.post(
    "/",
    response_model=RuleResponse,
    dependencies=[Depends(require_admin), Depends(validate_csrf_token)],
)
async def create_rule(
    data: RuleCreate,
    service: Annotated[RuleService, Depends(get_rule_service)],
    user: Annotated[User, Depends(require_admin)],
) -> RuleResponse:
    """Create a new rule."""
    return await service.create_rule(
        data.model_dump(),
        user_id=user.id,
    )


@router.put(
    "/{rule_id}",
    response_model=RuleResponse,
    dependencies=[Depends(require_admin), Depends(validate_csrf_token)],
)
async def update_rule(
    rule_id: str,
    data: RuleUpdate,
    service: Annotated[RuleService, Depends(get_rule_service)],
    user: Annotated[User, Depends(require_admin)],
) -> RuleResponse:
    """Update an existing rule."""
    return await service.update_rule(
        rule_id,
        data.model_dump(exclude_unset=True),
        user_id=user.id,
    )


@router.delete(
    "/{rule_id}",
    dependencies=[Depends(require_admin), Depends(validate_csrf_token)],
)
async def delete_rule(
    rule_id: str,
    service: Annotated[RuleService, Depends(get_rule_service)],
    user: Annotated[User, Depends(require_admin)],
) -> dict:
    """Delete a rule."""
    await service.delete_rule(rule_id, user_id=user.id)
    return {"success": True, "message": "Rule deleted"}


@router.patch(
    "/{rule_id}/toggle",
    response_model=RuleResponse,
    dependencies=[Depends(require_admin), Depends(validate_csrf_token)],
)
async def toggle_rule(
    rule_id: str,
    service: Annotated[RuleService, Depends(get_rule_service)],
    user: Annotated[User, Depends(require_admin)],
) -> RuleResponse:
    """Toggle rule enabled status."""
    return await service.toggle_rule(rule_id, user_id=user.id)


@router.post(
    "/{rule_id}/duplicate",
    response_model=RuleResponse,
    dependencies=[Depends(require_admin), Depends(validate_csrf_token)],
)
async def duplicate_rule(
    rule_id: str,
    service: Annotated[RuleService, Depends(get_rule_service)],
    user: Annotated[User, Depends(require_admin)],
    new_name: str = Query(...),
) -> RuleResponse:
    """Duplicate a rule with a new name."""
    return await service.duplicate_rule(
        rule_id,
        new_name,
        user_id=user.id,
    )


@router.post("/validate", response_model=RuleValidationResult, dependencies=[Depends(require_admin)])
async def validate_rule(
    data: RuleValidationRequest,
    service: Annotated[RuleService, Depends(get_rule_service)],
) -> RuleValidationResult:
    """Validate a rule configuration."""
    return service.validate_rule_config(
        data.category,
        data.rule_type,
        data.config,
    )


@router.post("/test", response_model=RuleTestResult, dependencies=[Depends(require_admin)])
async def test_rule(
    data: RuleTestRequest,
    repository: Annotated[RuleRepository, Depends(get_rule_repository)],
    service: Annotated[RuleService, Depends(get_rule_service)],
) -> RuleTestResult:
    """Test a rule against sample data."""
    executor = RuleExecutor(repository)

    if data.rule_id:
        rule_response = await service.get_rule(data.rule_id)
        result = await executor.test_rule_config(
            category=rule_response.category,
            rule_type=rule_response.rule_type,
            config=rule_response.config,
            sample_data=data.sample_data,
            conditions=rule_response.conditions.model_dump() if rule_response.conditions else None,
        )
    elif data.rule_config:
        result = await executor.test_rule_config(
            category=data.rule_config.category,
            rule_type=data.rule_config.rule_type,
            config=data.rule_config.config,
            sample_data=data.sample_data,
            conditions=data.rule_config.conditions.model_dump() if data.rule_config.conditions else None,
        )
    else:
        return RuleTestResult(
            success=False,
            output_data=[],
            row_count=0,
            column_count=0,
            execution_time_ms=0,
            errors=["Either rule_id or rule_config must be provided"],
        )

    return RuleTestResult(
        success=result.success,
        output_data=result.dataset.to_dict_list(),
        row_count=result.dataset.row_count,
        column_count=result.dataset.column_count,
        execution_time_ms=result.execution_time_ms,
        errors=[e.message for e in result.errors],
        warnings=result.warnings,
    )


@router.post("/execute", response_model=ExecuteRulesResult, dependencies=[Depends(require_admin)])
async def execute_rules(
    data: ExecuteRulesRequest,
    repository: Annotated[RuleRepository, Depends(get_rule_repository)],
) -> ExecuteRulesResult:
    """Execute all rules for a template against provided data."""
    executor = RuleExecutor(repository)
    dataset = Dataset.from_dict_list(data.data, name="input")

    from app.features.rules.engine.context import ExecutionContext

    context = ExecutionContext(
        template_id=data.template_id,
        variables=data.variables,
    )

    result = await executor.execute(dataset, data.template_id, context)

    highlights = [
        HighlightInfo(
            row=h.row_index,
            column=h.column,
            style=StyleConfig(
                background_color=h.background_color,
                text_color=h.text_color,
                bold=h.bold,
                italic=h.italic,
            ),
        )
        for h in result.highlights
    ]

    return ExecuteRulesResult(
        success=result.success,
        output_data=result.dataset.to_dict_list(),
        highlights=highlights,
        row_count=result.dataset.row_count,
        column_count=result.dataset.column_count,
        execution_time_ms=result.execution_time_ms,
        rules_executed=result.rules_executed,
        execution_log=[e.message for e in result.execution_log],
        errors=[e.message for e in result.errors],
        warnings=result.warnings,
    )


@router.post("/reorder", dependencies=[Depends(require_admin), Depends(validate_csrf_token)])
async def reorder_rules(
    data: ReorderRulesRequest,
    service: Annotated[RuleService, Depends(get_rule_service)],
    user: Annotated[User, Depends(require_admin)],
) -> dict:
    """Update rule priorities for reordering."""
    updated = await service.reorder_rules(
        data.rule_priorities,
        user_id=user.id,
    )
    return {"success": True, "updated_count": updated}
