import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import (
    BusinessRuleModel,
    ReportTemplateModel,
    WorkflowSettingModel,
)


def add_setting(
    session: AsyncSession,
    workflow_id: str,
    setting_id: str,
    label: str,
    setting_type: str,
    *,
    required: bool = False,
    default_value: object = None,
    options: list | None = None,
    sort_order: int = 0,
) -> None:
    session.add(
        WorkflowSettingModel(
            workflow_id=workflow_id,
            setting_id=setting_id,
            label=label,
            type=setting_type,
            required=required,
            default_value=json.dumps(default_value) if default_value is not None else None,
            options_json=json.dumps(options) if options else None,
            sort_order=sort_order,
        )
    )


def add_template(
    session: AsyncSession,
    workflow_id: str,
    template_id: str,
    name: str,
    template_type: str,
    content: str,
    output_format: str,
) -> None:
    session.add(
        ReportTemplateModel(
            workflow_id=workflow_id,
            template_id=template_id,
            name=name,
            template_type=template_type,
            content=content,
            output_format=output_format,
        )
    )


def add_rule(
    session: AsyncSession,
    workflow_id: str,
    rule_id: str,
    name: str,
    rule_type: str,
    expression: str,
) -> None:
    session.add(
        BusinessRuleModel(
            workflow_id=workflow_id,
            rule_id=rule_id,
            name=name,
            rule_type=rule_type,
            expression=expression,
            severity="error",
            enabled=True,
        )
    )
