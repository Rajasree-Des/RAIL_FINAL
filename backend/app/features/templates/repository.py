"""Repository layer for Report Configuration Templates."""

import json
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infrastructure.database.models import (
    FilteringRuleModel,
    HighlightRuleModel,
    InputConfigurationModel,
    OutputConfigurationModel,
    ReportConfigTemplateModel,
    RowRuleModel,
    SortingRuleModel,
    TemplateColumnMappingModel,
)

_TEMPLATE_DETAIL_EAGER_LOAD = (
    selectinload(ReportConfigTemplateModel.input_config),
    selectinload(ReportConfigTemplateModel.column_mappings),
    selectinload(ReportConfigTemplateModel.sorting_rules),
    selectinload(ReportConfigTemplateModel.filtering_rules),
    selectinload(ReportConfigTemplateModel.row_rule),
    selectinload(ReportConfigTemplateModel.highlight_rules),
    selectinload(ReportConfigTemplateModel.output_config),
)


class TemplateRepository:
    """Repository for Report Configuration Template CRUD operations."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_all(
        self,
        include_deleted: bool = False,
        enabled_only: bool = False,
    ) -> list[ReportConfigTemplateModel]:
        """List all templates with optional filtering."""
        query = select(ReportConfigTemplateModel).options(
            selectinload(ReportConfigTemplateModel.input_config),
            selectinload(ReportConfigTemplateModel.output_config),
            selectinload(ReportConfigTemplateModel.row_rule),
        )

        if not include_deleted:
            query = query.where(ReportConfigTemplateModel.is_deleted == False)  # noqa: E712

        if enabled_only:
            query = query.where(ReportConfigTemplateModel.is_enabled == True)  # noqa: E712

        query = query.order_by(ReportConfigTemplateModel.name)

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, template_id: str) -> ReportConfigTemplateModel | None:
        """Get a template by ID with all related configurations."""
        query = (
            select(ReportConfigTemplateModel)
            .options(*_TEMPLATE_DETAIL_EAGER_LOAD)
            .where(ReportConfigTemplateModel.id == template_id)
            .where(ReportConfigTemplateModel.is_deleted == False)  # noqa: E712
        )

        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> ReportConfigTemplateModel | None:
        """Get a template by slug."""
        query = (
            select(ReportConfigTemplateModel)
            .options(*_TEMPLATE_DETAIL_EAGER_LOAD)
            .where(ReportConfigTemplateModel.slug == slug)
            .where(ReportConfigTemplateModel.is_deleted == False)  # noqa: E712
        )

        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def slug_exists(self, slug: str, exclude_id: str | None = None) -> bool:
        """Check if a slug already exists."""
        query = select(ReportConfigTemplateModel.id).where(
            ReportConfigTemplateModel.slug == slug,
            ReportConfigTemplateModel.is_deleted == False,  # noqa: E712
        )

        if exclude_id:
            query = query.where(ReportConfigTemplateModel.id != exclude_id)

        result = await self._session.execute(query)
        return result.scalar_one_or_none() is not None

    async def create(
        self,
        template_data: dict[str, Any],
        user_id: str | None = None,
    ) -> ReportConfigTemplateModel:
        """Create a new template with all related configurations."""
        input_config_data = template_data.pop("input_config", None)
        column_mappings_data = template_data.pop("column_mappings", [])
        sorting_rules_data = template_data.pop("sorting_rules", [])
        filtering_rules_data = template_data.pop("filtering_rules", [])
        row_rule_data = template_data.pop("row_rule", None)
        highlight_rules_data = template_data.pop("highlight_rules", [])
        output_config_data = template_data.pop("output_config", None)

        template = ReportConfigTemplateModel(
            **template_data,
            created_by=user_id,
            updated_by=user_id,
        )
        self._session.add(template)
        await self._session.flush()

        if input_config_data:
            input_config = InputConfigurationModel(
                template_id=template.id,
                accepted_file_types=json.dumps(input_config_data.get("accepted_file_types", [])),
                required_sheets=json.dumps(input_config_data.get("required_sheets")),
                header_row=input_config_data.get("header_row", 1),
                validation_rules=json.dumps(input_config_data.get("validation_rules", {})),
            )
            self._session.add(input_config)

        for idx, mapping_data in enumerate(column_mappings_data):
            mapping = TemplateColumnMappingModel(
                template_id=template.id,
                sort_order=mapping_data.get("sort_order", idx),
                **{k: v for k, v in mapping_data.items() if k != "sort_order"},
            )
            self._session.add(mapping)

        for idx, sort_data in enumerate(sorting_rules_data):
            sort_rule = SortingRuleModel(
                template_id=template.id,
                priority=sort_data.get("priority", idx + 1),
                **{k: v for k, v in sort_data.items() if k != "priority"},
            )
            self._session.add(sort_rule)

        for filter_data in filtering_rules_data:
            filter_rule = FilteringRuleModel(
                template_id=template.id,
                **filter_data,
            )
            self._session.add(filter_rule)

        if row_rule_data:
            row_rule = RowRuleModel(
                template_id=template.id,
                **row_rule_data,
            )
            self._session.add(row_rule)

        for idx, highlight_data in enumerate(highlight_rules_data):
            highlight_rule = HighlightRuleModel(
                template_id=template.id,
                priority=highlight_data.get("priority", idx + 1),
                **{k: v for k, v in highlight_data.items() if k != "priority"},
            )
            self._session.add(highlight_rule)

        if output_config_data:
            output_config = OutputConfigurationModel(
                template_id=template.id,
                excel_enabled=output_config_data.get("excel_enabled", True),
                excel_config=json.dumps(output_config_data.get("excel_config", {})),
                pdf_enabled=output_config_data.get("pdf_enabled", False),
                pdf_config=json.dumps(output_config_data.get("pdf_config", {})),
                ai_summary_enabled=output_config_data.get("ai_summary_enabled", False),
                ai_config=json.dumps(output_config_data.get("ai_config", {})),
                whatsapp_enabled=output_config_data.get("whatsapp_enabled", False),
                whatsapp_config=json.dumps(output_config_data.get("whatsapp_config", {})),
                email_enabled=output_config_data.get("email_enabled", False),
                email_config=json.dumps(output_config_data.get("email_config", {})),
            )
            self._session.add(output_config)

        await self._session.commit()
        await self._session.refresh(template)

        return await self.get_by_id(template.id)  # type: ignore

    async def update(
        self,
        template_id: str,
        template_data: dict[str, Any],
        user_id: str | None = None,
    ) -> ReportConfigTemplateModel | None:
        """Update a template and its related configurations."""
        template = await self.get_by_id(template_id)
        if not template:
            return None

        input_config_data = template_data.pop("input_config", None)
        column_mappings_data = template_data.pop("column_mappings", None)
        sorting_rules_data = template_data.pop("sorting_rules", None)
        filtering_rules_data = template_data.pop("filtering_rules", None)
        row_rule_data = template_data.pop("row_rule", None)
        highlight_rules_data = template_data.pop("highlight_rules", None)
        output_config_data = template_data.pop("output_config", None)

        for key, value in template_data.items():
            setattr(template, key, value)
        template.updated_by = user_id
        template.version += 1

        if input_config_data is not None:
            if template.input_config:
                template.input_config.accepted_file_types = json.dumps(
                    input_config_data.get("accepted_file_types", [])
                )
                template.input_config.required_sheets = json.dumps(
                    input_config_data.get("required_sheets")
                )
                template.input_config.header_row = input_config_data.get("header_row", 1)
                template.input_config.validation_rules = json.dumps(
                    input_config_data.get("validation_rules", {})
                )
            else:
                input_config = InputConfigurationModel(
                    template_id=template.id,
                    accepted_file_types=json.dumps(input_config_data.get("accepted_file_types", [])),
                    required_sheets=json.dumps(input_config_data.get("required_sheets")),
                    header_row=input_config_data.get("header_row", 1),
                    validation_rules=json.dumps(input_config_data.get("validation_rules", {})),
                )
                self._session.add(input_config)

        if column_mappings_data is not None:
            for mapping in template.column_mappings:
                await self._session.delete(mapping)
            for idx, mapping_data in enumerate(column_mappings_data):
                mapping = TemplateColumnMappingModel(
                    template_id=template.id,
                    sort_order=mapping_data.get("sort_order", idx),
                    **{k: v for k, v in mapping_data.items() if k != "sort_order"},
                )
                self._session.add(mapping)

        if sorting_rules_data is not None:
            for rule in template.sorting_rules:
                await self._session.delete(rule)
            for idx, sort_data in enumerate(sorting_rules_data):
                sort_rule = SortingRuleModel(
                    template_id=template.id,
                    priority=sort_data.get("priority", idx + 1),
                    **{k: v for k, v in sort_data.items() if k != "priority"},
                )
                self._session.add(sort_rule)

        if filtering_rules_data is not None:
            for rule in template.filtering_rules:
                await self._session.delete(rule)
            for filter_data in filtering_rules_data:
                filter_rule = FilteringRuleModel(
                    template_id=template.id,
                    **filter_data,
                )
                self._session.add(filter_rule)

        if row_rule_data is not None:
            if template.row_rule:
                for key, value in row_rule_data.items():
                    setattr(template.row_rule, key, value)
            else:
                row_rule = RowRuleModel(
                    template_id=template.id,
                    **row_rule_data,
                )
                self._session.add(row_rule)

        if highlight_rules_data is not None:
            for rule in template.highlight_rules:
                await self._session.delete(rule)
            for idx, highlight_data in enumerate(highlight_rules_data):
                highlight_rule = HighlightRuleModel(
                    template_id=template.id,
                    priority=highlight_data.get("priority", idx + 1),
                    **{k: v for k, v in highlight_data.items() if k != "priority"},
                )
                self._session.add(highlight_rule)

        if output_config_data is not None:
            if template.output_config:
                template.output_config.excel_enabled = output_config_data.get("excel_enabled", True)
                template.output_config.excel_config = json.dumps(
                    output_config_data.get("excel_config", {})
                )
                template.output_config.pdf_enabled = output_config_data.get("pdf_enabled", False)
                template.output_config.pdf_config = json.dumps(
                    output_config_data.get("pdf_config", {})
                )
                template.output_config.ai_summary_enabled = output_config_data.get(
                    "ai_summary_enabled", False
                )
                template.output_config.ai_config = json.dumps(
                    output_config_data.get("ai_config", {})
                )
                template.output_config.whatsapp_enabled = output_config_data.get(
                    "whatsapp_enabled", False
                )
                template.output_config.whatsapp_config = json.dumps(
                    output_config_data.get("whatsapp_config", {})
                )
                template.output_config.email_enabled = output_config_data.get("email_enabled", False)
                template.output_config.email_config = json.dumps(
                    output_config_data.get("email_config", {})
                )
            else:
                output_config = OutputConfigurationModel(
                    template_id=template.id,
                    excel_enabled=output_config_data.get("excel_enabled", True),
                    excel_config=json.dumps(output_config_data.get("excel_config", {})),
                    pdf_enabled=output_config_data.get("pdf_enabled", False),
                    pdf_config=json.dumps(output_config_data.get("pdf_config", {})),
                    ai_summary_enabled=output_config_data.get("ai_summary_enabled", False),
                    ai_config=json.dumps(output_config_data.get("ai_config", {})),
                    whatsapp_enabled=output_config_data.get("whatsapp_enabled", False),
                    whatsapp_config=json.dumps(output_config_data.get("whatsapp_config", {})),
                    email_enabled=output_config_data.get("email_enabled", False),
                    email_config=json.dumps(output_config_data.get("email_config", {})),
                )
                self._session.add(output_config)

        await self._session.commit()
        return await self.get_by_id(template_id)

    async def delete(self, template_id: str, user_id: str | None = None) -> bool:
        """Soft delete a template."""
        stmt = (
            update(ReportConfigTemplateModel)
            .where(ReportConfigTemplateModel.id == template_id)
            .where(ReportConfigTemplateModel.is_deleted == False)  # noqa: E712
            .values(is_deleted=True, updated_by=user_id)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount > 0

    async def toggle_enabled(
        self, template_id: str, user_id: str | None = None
    ) -> ReportConfigTemplateModel | None:
        """Toggle the enabled status of a template."""
        template = await self.get_by_id(template_id)
        if not template:
            return None

        template.is_enabled = not template.is_enabled
        template.updated_by = user_id
        await self._session.commit()
        await self._session.refresh(template)
        return template

    async def duplicate(
        self,
        template_id: str,
        new_name: str,
        new_slug: str,
        user_id: str | None = None,
    ) -> ReportConfigTemplateModel | None:
        """Duplicate a template with a new name and slug."""
        original = await self.get_by_id(template_id)
        if not original:
            return None

        template_data = {
            "name": new_name,
            "slug": new_slug,
            "description": original.description,
            "source_report_id": original.source_report_id,
            "is_enabled": False,
            "metadata_json": original.metadata_json,
        }

        if original.input_config:
            template_data["input_config"] = {
                "accepted_file_types": json.loads(original.input_config.accepted_file_types or "[]"),
                "required_sheets": json.loads(original.input_config.required_sheets or "null"),
                "header_row": original.input_config.header_row,
                "validation_rules": json.loads(original.input_config.validation_rules or "{}"),
            }

        template_data["column_mappings"] = [
            {
                "source_column": m.source_column,
                "internal_field": m.internal_field,
                "output_column": m.output_column,
                "data_type": m.data_type,
                "is_required": m.is_required,
                "default_value": m.default_value,
                "transform": m.transform,
                "sort_order": m.sort_order,
            }
            for m in original.column_mappings
        ]

        template_data["sorting_rules"] = [
            {
                "column_name": r.column_name,
                "direction": r.direction,
                "priority": r.priority,
            }
            for r in original.sorting_rules
        ]

        template_data["filtering_rules"] = [
            {
                "column_name": r.column_name,
                "operator": r.operator,
                "value": r.value,
                "value_type": r.value_type,
                "logic_group": r.logic_group,
            }
            for r in original.filtering_rules
        ]

        if original.row_rule:
            template_data["row_rule"] = {
                "rule_type": original.row_rule.rule_type,
                "limit_value": original.row_rule.limit_value,
                "limit_column": original.row_rule.limit_column,
                "custom_expression": original.row_rule.custom_expression,
            }

        template_data["highlight_rules"] = [
            {
                "column_name": r.column_name,
                "condition_type": r.condition_type,
                "condition_value": r.condition_value,
                "highlight_color": r.highlight_color,
                "text_color": r.text_color,
                "is_bold": r.is_bold,
                "priority": r.priority,
            }
            for r in original.highlight_rules
        ]

        if original.output_config:
            template_data["output_config"] = {
                "excel_enabled": original.output_config.excel_enabled,
                "excel_config": json.loads(original.output_config.excel_config or "{}"),
                "pdf_enabled": original.output_config.pdf_enabled,
                "pdf_config": json.loads(original.output_config.pdf_config or "{}"),
                "ai_summary_enabled": original.output_config.ai_summary_enabled,
                "ai_config": json.loads(original.output_config.ai_config or "{}"),
                "whatsapp_enabled": original.output_config.whatsapp_enabled,
                "whatsapp_config": json.loads(original.output_config.whatsapp_config or "{}"),
                "email_enabled": original.output_config.email_enabled,
                "email_config": json.loads(original.output_config.email_config or "{}"),
            }

        return await self.create(template_data, user_id)
