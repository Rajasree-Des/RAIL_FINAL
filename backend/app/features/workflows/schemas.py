from typing import Any

from pydantic import BaseModel, Field


class SettingOptionSchema(BaseModel):
    label: str
    value: str


class WorkflowSettingSchema(BaseModel):
    id: str
    label: str
    type: str
    required: bool = False
    placeholder: str | None = None
    default_value: Any = None
    options: list[SettingOptionSchema] = Field(default_factory=list)
    help_text: str | None = None


class ColumnMappingSchema(BaseModel):
    key: str
    label: str
    type: str
    required: bool = False
    source_column: str | None = None


class BusinessRuleSchema(BaseModel):
    id: str
    name: str
    rule_type: str
    expression: str
    severity: str = "error"
    enabled: bool = True


class ReportTemplateSchema(BaseModel):
    id: str
    name: str
    template_type: str
    content: str
    output_format: str


class WorkflowResponse(BaseModel):
    id: str
    name: str
    order: int
    description: str
    variant: str
    icon: str
    upload_label: str | None = None
    report_source_id: str | None = None
    accepted_files: list[str] = Field(default_factory=list)
    settings: list[WorkflowSettingSchema] = Field(default_factory=list)
    preview_columns: list[ColumnMappingSchema] = Field(default_factory=list)
    business_rules: list[BusinessRuleSchema] = Field(default_factory=list)
    templates: list[ReportTemplateSchema] = Field(default_factory=list)


class WorkflowListResponse(BaseModel):
    workflows: list[WorkflowResponse]
