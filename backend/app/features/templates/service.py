"""Service layer for Report Configuration Templates."""

import json
from dataclasses import dataclass, field
from typing import Any

from app.core.exceptions import AppException
from app.core.slug import generate_slug
from app.features.templates.repository import TemplateRepository
from app.infrastructure.database.models import ReportConfigTemplateModel


@dataclass
class TemplateResponse:
    """Response DTO for a template."""

    id: str
    name: str
    slug: str
    description: str | None
    source_report_id: str | None
    is_enabled: bool
    version: int
    metadata: dict[str, Any]
    created_at: str
    updated_at: str
    created_by: str | None
    updated_by: str | None
    input_config: dict[str, Any] | None = None
    column_mappings: list[dict[str, Any]] = field(default_factory=list)
    sorting_rules: list[dict[str, Any]] = field(default_factory=list)
    filtering_rules: list[dict[str, Any]] = field(default_factory=list)
    row_rule: dict[str, Any] | None = None
    highlight_rules: list[dict[str, Any]] = field(default_factory=list)
    output_config: dict[str, Any] | None = None


@dataclass
class TemplateListItem:
    """List item DTO for templates."""

    id: str
    name: str
    slug: str
    description: str | None
    source_report_id: str | None
    is_enabled: bool
    version: int
    created_at: str
    updated_at: str
    has_input_config: bool
    has_output_config: bool
    column_count: int


@dataclass
class ValidationResult:
    """Result of template validation."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class TemplateService:
    """Service for Report Configuration Template operations."""

    def __init__(self, repository: TemplateRepository):
        self.repository = repository

    @staticmethod
    def _model_to_response(model: ReportConfigTemplateModel) -> TemplateResponse:
        """Convert a model to a response DTO."""
        input_config = None
        if model.input_config:
            input_config = {
                "id": model.input_config.id,
                "accepted_file_types": json.loads(
                    model.input_config.accepted_file_types or "[]"
                ),
                "required_sheets": json.loads(model.input_config.required_sheets or "null"),
                "header_row": model.input_config.header_row,
                "validation_rules": json.loads(
                    model.input_config.validation_rules or "{}"
                ),
            }

        column_mappings = [
            {
                "id": m.id,
                "source_column": m.source_column,
                "internal_field": m.internal_field,
                "output_column": m.output_column,
                "data_type": m.data_type,
                "is_required": m.is_required,
                "default_value": m.default_value,
                "transform": m.transform,
                "sort_order": m.sort_order,
            }
            for m in model.column_mappings
        ]

        sorting_rules = [
            {
                "id": r.id,
                "column_name": r.column_name,
                "direction": r.direction,
                "priority": r.priority,
            }
            for r in model.sorting_rules
        ]

        filtering_rules = [
            {
                "id": r.id,
                "column_name": r.column_name,
                "operator": r.operator,
                "value": r.value,
                "value_type": r.value_type,
                "logic_group": r.logic_group,
            }
            for r in model.filtering_rules
        ]

        row_rule = None
        if model.row_rule:
            row_rule = {
                "id": model.row_rule.id,
                "rule_type": model.row_rule.rule_type,
                "limit_value": model.row_rule.limit_value,
                "limit_column": model.row_rule.limit_column,
                "custom_expression": model.row_rule.custom_expression,
            }

        highlight_rules = [
            {
                "id": r.id,
                "column_name": r.column_name,
                "condition_type": r.condition_type,
                "condition_value": r.condition_value,
                "highlight_color": r.highlight_color,
                "text_color": r.text_color,
                "is_bold": r.is_bold,
                "priority": r.priority,
            }
            for r in model.highlight_rules
        ]

        output_config = None
        if model.output_config:
            output_config = {
                "id": model.output_config.id,
                "excel_enabled": model.output_config.excel_enabled,
                "excel_config": json.loads(model.output_config.excel_config or "{}"),
                "pdf_enabled": model.output_config.pdf_enabled,
                "pdf_config": json.loads(model.output_config.pdf_config or "{}"),
                "ai_summary_enabled": model.output_config.ai_summary_enabled,
                "ai_config": json.loads(model.output_config.ai_config or "{}"),
                "whatsapp_enabled": model.output_config.whatsapp_enabled,
                "whatsapp_config": json.loads(model.output_config.whatsapp_config or "{}"),
                "email_enabled": model.output_config.email_enabled,
                "email_config": json.loads(model.output_config.email_config or "{}"),
            }

        return TemplateResponse(
            id=model.id,
            name=model.name,
            slug=model.slug,
            description=model.description,
            source_report_id=model.source_report_id,
            is_enabled=model.is_enabled,
            version=model.version,
            metadata=json.loads(model.metadata_json or "{}"),
            created_at=model.created_at.isoformat(),
            updated_at=model.updated_at.isoformat(),
            created_by=model.created_by,
            updated_by=model.updated_by,
            input_config=input_config,
            column_mappings=column_mappings,
            sorting_rules=sorting_rules,
            filtering_rules=filtering_rules,
            row_rule=row_rule,
            highlight_rules=highlight_rules,
            output_config=output_config,
        )

    @staticmethod
    def _model_to_list_item(model: ReportConfigTemplateModel) -> TemplateListItem:
        """Convert a model to a list item DTO."""
        return TemplateListItem(
            id=model.id,
            name=model.name,
            slug=model.slug,
            description=model.description,
            source_report_id=model.source_report_id,
            is_enabled=model.is_enabled,
            version=model.version,
            created_at=model.created_at.isoformat(),
            updated_at=model.updated_at.isoformat(),
            has_input_config=model.input_config is not None,
            has_output_config=model.output_config is not None,
            column_count=len(model.column_mappings) if model.column_mappings else 0,
        )

    async def list_templates(
        self,
        include_deleted: bool = False,
        enabled_only: bool = False,
    ) -> list[TemplateListItem]:
        """List all templates."""
        models = await self.repository.list_all(include_deleted, enabled_only)
        return [self._model_to_list_item(m) for m in models]

    async def get_template(self, template_id: str) -> TemplateResponse:
        """Get a template by ID."""
        model = await self.repository.get_by_id(template_id)
        if not model:
            raise AppException(
                status_code=404,
                message=f"Template not found: {template_id}",
                error_code="TEMPLATE_NOT_FOUND",
            )
        return self._model_to_response(model)

    async def get_template_by_slug(self, slug: str) -> TemplateResponse:
        """Get a template by slug."""
        model = await self.repository.get_by_slug(slug)
        if not model:
            raise AppException(
                status_code=404,
                message=f"Template not found: {slug}",
                error_code="TEMPLATE_NOT_FOUND",
            )
        return self._model_to_response(model)

    async def create_template(
        self,
        data: dict[str, Any],
        user_id: str | None = None,
    ) -> TemplateResponse:
        """Create a new template."""
        if "slug" not in data or not data["slug"]:
            data["slug"] = generate_slug(data["name"])

        if await self.repository.slug_exists(data["slug"]):
            raise AppException(
                status_code=400,
                message=f"Slug already exists: {data['slug']}",
                error_code="SLUG_EXISTS",
            )

        if "metadata" in data:
            data["metadata_json"] = json.dumps(data.pop("metadata"))

        model = await self.repository.create(data, user_id)
        return self._model_to_response(model)

    async def update_template(
        self,
        template_id: str,
        data: dict[str, Any],
        user_id: str | None = None,
    ) -> TemplateResponse:
        """Update an existing template."""
        if "slug" in data:
            if await self.repository.slug_exists(data["slug"], exclude_id=template_id):
                raise AppException(
                    status_code=400,
                    message=f"Slug already exists: {data['slug']}",
                    error_code="SLUG_EXISTS",
                )

        if "metadata" in data:
            data["metadata_json"] = json.dumps(data.pop("metadata"))

        model = await self.repository.update(template_id, data, user_id)
        if not model:
            raise AppException(
                status_code=404,
                message=f"Template not found: {template_id}",
                error_code="TEMPLATE_NOT_FOUND",
            )
        return self._model_to_response(model)

    async def delete_template(
        self,
        template_id: str,
        user_id: str | None = None,
    ) -> bool:
        """Delete a template (soft delete)."""
        success = await self.repository.delete(template_id, user_id)
        if not success:
            raise AppException(
                status_code=404,
                message=f"Template not found: {template_id}",
                error_code="TEMPLATE_NOT_FOUND",
            )
        return True

    async def toggle_template(
        self,
        template_id: str,
        user_id: str | None = None,
    ) -> TemplateResponse:
        """Toggle template enabled status."""
        model = await self.repository.toggle_enabled(template_id, user_id)
        if not model:
            raise AppException(
                status_code=404,
                message=f"Template not found: {template_id}",
                error_code="TEMPLATE_NOT_FOUND",
            )
        return self._model_to_response(model)

    async def duplicate_template(
        self,
        template_id: str,
        new_name: str,
        user_id: str | None = None,
    ) -> TemplateResponse:
        """Duplicate an existing template."""
        new_slug = generate_slug(new_name)

        counter = 1
        base_slug = new_slug
        while await self.repository.slug_exists(new_slug):
            new_slug = f"{base_slug}-{counter}"
            counter += 1

        model = await self.repository.duplicate(template_id, new_name, new_slug, user_id)
        if not model:
            raise AppException(
                status_code=404,
                message=f"Template not found: {template_id}",
                error_code="TEMPLATE_NOT_FOUND",
            )
        return self._model_to_response(model)

    async def validate_template(self, template_id: str) -> ValidationResult:
        """Validate a template configuration."""
        model = await self.repository.get_by_id(template_id)
        if not model:
            raise AppException(
                status_code=404,
                message=f"Template not found: {template_id}",
                error_code="TEMPLATE_NOT_FOUND",
            )

        errors: list[str] = []
        warnings: list[str] = []

        if not model.name:
            errors.append("Template name is required")

        if not model.slug:
            errors.append("Template slug is required")

        if not model.input_config:
            warnings.append("No input configuration defined")
        else:
            file_types = json.loads(model.input_config.accepted_file_types or "[]")
            if not file_types:
                warnings.append("No accepted file types defined")

        if not model.column_mappings:
            errors.append("At least one column mapping is required")
        else:
            required_columns = [m for m in model.column_mappings if m.is_required]
            if not required_columns:
                warnings.append("No required columns defined")

            internal_fields = [m.internal_field for m in model.column_mappings]
            if len(internal_fields) != len(set(internal_fields)):
                errors.append("Duplicate internal field names detected")

        if not model.output_config:
            warnings.append("No output configuration defined")
        else:
            any_enabled = (
                model.output_config.excel_enabled
                or model.output_config.pdf_enabled
                or model.output_config.ai_summary_enabled
                or model.output_config.whatsapp_enabled
                or model.output_config.email_enabled
            )
            if not any_enabled:
                warnings.append("No output formats enabled")

        if model.sorting_rules:
            column_names = {m.internal_field for m in model.column_mappings}
            for rule in model.sorting_rules:
                if rule.column_name not in column_names:
                    warnings.append(
                        f"Sorting rule references unknown column: {rule.column_name}"
                    )

        if model.filtering_rules:
            column_names = {m.internal_field for m in model.column_mappings}
            for rule in model.filtering_rules:
                if rule.column_name not in column_names:
                    warnings.append(
                        f"Filtering rule references unknown column: {rule.column_name}"
                    )

        if model.row_rule and model.row_rule.rule_type != "none":
            if model.row_rule.rule_type in ("top_n", "bottom_n"):
                if not model.row_rule.limit_value:
                    errors.append("Row limit value is required for top_n/bottom_n rules")
                if not model.row_rule.limit_column:
                    errors.append("Row limit column is required for top_n/bottom_n rules")

        if model.highlight_rules:
            column_names = {m.internal_field for m in model.column_mappings}
            for rule in model.highlight_rules:
                if rule.column_name not in column_names:
                    warnings.append(
                        f"Highlight rule references unknown column: {rule.column_name}"
                    )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
