import logging

from app.core.exceptions import NotFoundError
from app.domain.entities.workflow import Workflow
from app.domain.interfaces.workflow_repository import IWorkflowRepository
from app.features.workflows.schemas import (
    BusinessRuleSchema,
    ColumnMappingSchema,
    ReportTemplateSchema,
    SettingOptionSchema,
    WorkflowResponse,
    WorkflowSettingSchema,
)
from app.features.workflows.validation import validate_workflow_id

logger = logging.getLogger(__name__)


class WorkflowService:
    def __init__(self, repository: IWorkflowRepository) -> None:
        self._repository = repository

    async def list_workflows(self) -> list[WorkflowResponse]:
        logger.info("Listing all workflows")
        workflows = await self._repository.list_all()
        return [self._to_response(w) for w in workflows]

    async def get_workflow(self, workflow_id: str) -> WorkflowResponse:
        logger.info("Getting workflow: %s", workflow_id)
        validate_workflow_id(workflow_id)

        workflow = await self._repository.get_by_id(workflow_id)
        if workflow is None:
            raise NotFoundError("Workflow", workflow_id)

        return self._to_response(workflow)

    @staticmethod
    def _to_response(workflow: Workflow) -> WorkflowResponse:
        return WorkflowResponse(
            id=workflow.id,
            name=workflow.name,
            order=workflow.order,
            description=workflow.description,
            variant=workflow.variant,
            icon=workflow.icon,
            upload_label=workflow.upload_label,
            report_source_id=workflow.report_source_id,
            accepted_files=list(workflow.accepted_files),
            settings=[
                WorkflowSettingSchema(
                    id=s.id,
                    label=s.label,
                    type=s.type,
                    required=s.required,
                    placeholder=s.placeholder,
                    default_value=s.default_value,
                    options=[SettingOptionSchema(label=o.label, value=o.value) for o in s.options],
                    help_text=s.help_text,
                )
                for s in workflow.settings
            ],
            preview_columns=[
                ColumnMappingSchema(
                    key=c.key,
                    label=c.label,
                    type=c.column_type,
                    required=c.required,
                    source_column=c.source_column,
                )
                for c in workflow.column_mappings
            ],
            business_rules=[
                BusinessRuleSchema(
                    id=r.id,
                    name=r.name,
                    rule_type=r.rule_type,
                    expression=r.expression,
                    severity=r.severity,
                    enabled=r.enabled,
                )
                for r in workflow.business_rules
            ],
            templates=[
                ReportTemplateSchema(
                    id=t.id,
                    name=t.name,
                    template_type=t.template_type,
                    content=t.content,
                    output_format=t.output_format,
                )
                for t in workflow.templates
            ],
        )
