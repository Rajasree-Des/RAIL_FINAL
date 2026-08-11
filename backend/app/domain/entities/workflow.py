from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SettingOption:
    label: str
    value: str


@dataclass(frozen=True)
class WorkflowSetting:
    id: str
    label: str
    type: str
    required: bool = False
    placeholder: str | None = None
    default_value: Any = None
    options: tuple[SettingOption, ...] = field(default_factory=tuple)
    help_text: str | None = None


@dataclass(frozen=True)
class ColumnMapping:
    key: str
    label: str
    column_type: str
    required: bool = False
    source_column: str | None = None


@dataclass(frozen=True)
class BusinessRule:
    id: str
    name: str
    rule_type: str
    expression: str
    severity: str = "error"
    enabled: bool = True


@dataclass(frozen=True)
class ReportTemplate:
    id: str
    name: str
    template_type: str
    content: str
    output_format: str


@dataclass(frozen=True)
class Workflow:
    id: str
    name: str
    order: int
    description: str
    variant: str
    icon: str
    upload_label: str | None = None
    report_source_id: str | None = None
    accepted_files: tuple[str, ...] = field(default_factory=tuple)
    settings: tuple[WorkflowSetting, ...] = field(default_factory=tuple)
    column_mappings: tuple[ColumnMapping, ...] = field(default_factory=tuple)
    business_rules: tuple[BusinessRule, ...] = field(default_factory=tuple)
    templates: tuple[ReportTemplate, ...] = field(default_factory=tuple)
