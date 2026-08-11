import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.entities.workflow import (
    BusinessRule,
    ColumnMapping,
    ReportTemplate,
    SettingOption,
    Workflow,
    WorkflowSetting,
)
from app.domain.interfaces.workflow_repository import IWorkflowRepository
from app.infrastructure.database.models import WorkflowModel

logger = logging.getLogger(__name__)


class WorkflowRepository(IWorkflowRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> list[Workflow]:
        logger.debug("Fetching all workflows")
        result = await self._session.execute(
            select(WorkflowModel)
            .options(
                selectinload(WorkflowModel.settings),
                selectinload(WorkflowModel.column_mappings),
                selectinload(WorkflowModel.business_rules),
                selectinload(WorkflowModel.templates),
            )
            .order_by(WorkflowModel.order)
        )
        workflows = [self._to_entity(model) for model in result.scalars().all()]
        logger.debug("Found %d workflows", len(workflows))
        return workflows

    async def get_by_id(self, workflow_id: str) -> Workflow | None:
        logger.debug("Fetching workflow by ID: %s", workflow_id)
        result = await self._session.execute(
            select(WorkflowModel)
            .where(WorkflowModel.id == workflow_id)
            .options(
                selectinload(WorkflowModel.settings),
                selectinload(WorkflowModel.column_mappings),
                selectinload(WorkflowModel.business_rules),
                selectinload(WorkflowModel.templates),
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            logger.debug("Workflow not found: %s", workflow_id)
            return None
        return self._to_entity(model)

    @staticmethod
    def _to_entity(model: WorkflowModel) -> Workflow:
        settings = tuple(
            WorkflowSetting(
                id=s.setting_id,
                label=s.label,
                type=s.type,
                required=s.required,
                placeholder=s.placeholder,
                default_value=json.loads(s.default_value) if s.default_value else None,
                options=tuple(
                    SettingOption(label=o["label"], value=o["value"])
                    for o in (json.loads(s.options_json) if s.options_json else [])
                ),
                help_text=s.help_text,
            )
            for s in sorted(model.settings, key=lambda x: x.sort_order)
        )

        column_mappings = tuple(
            ColumnMapping(
                key=c.key,
                label=c.label,
                column_type=c.column_type,
                required=c.required,
                source_column=c.source_column,
            )
            for c in sorted(model.column_mappings, key=lambda x: x.sort_order)
        )

        business_rules = tuple(
            BusinessRule(
                id=r.rule_id,
                name=r.name,
                rule_type=r.rule_type,
                expression=r.expression,
                severity=r.severity,
                enabled=r.enabled,
            )
            for r in model.business_rules
        )

        templates = tuple(
            ReportTemplate(
                id=t.template_id,
                name=t.name,
                template_type=t.template_type,
                content=t.content,
                output_format=t.output_format,
            )
            for t in model.templates
        )

        accepted_files = tuple(
            f.strip() for f in model.accepted_files.split(",") if f.strip()
        )

        return Workflow(
            id=model.id,
            name=model.name,
            order=model.order,
            description=model.description,
            variant=model.variant,
            icon=model.icon,
            upload_label=model.upload_label,
            report_source_id=model.report_source_id,
            accepted_files=accepted_files,
            settings=settings,
            column_mappings=column_mappings,
            business_rules=business_rules,
            templates=templates,
        )
