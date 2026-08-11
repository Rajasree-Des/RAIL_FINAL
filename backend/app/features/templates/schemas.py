"""Pydantic schemas for Report Configuration Templates."""

from typing import Any

from pydantic import BaseModel, Field

# =============================================================================
# Input Configuration Schemas
# =============================================================================


class InputConfigBase(BaseModel):
    """Base schema for input configuration."""

    accepted_file_types: list[str] = Field(default_factory=lambda: [".xlsx", ".xls", ".csv"])
    required_sheets: list[str] | None = None
    header_row: int = Field(default=1, ge=1)
    validation_rules: dict[str, Any] = Field(default_factory=dict)


class InputConfigCreate(InputConfigBase):
    """Schema for creating input configuration."""

    pass


class InputConfigResponse(InputConfigBase):
    """Schema for input configuration response."""

    id: str


# =============================================================================
# Column Mapping Schemas
# =============================================================================


class ColumnMappingBase(BaseModel):
    """Base schema for column mapping."""

    source_column: str = Field(..., min_length=1, max_length=128)
    internal_field: str = Field(..., min_length=1, max_length=64)
    output_column: str = Field(..., min_length=1, max_length=128)
    data_type: str = Field(default="text", pattern="^(text|number|date|boolean)$")
    is_required: bool = False
    default_value: str | None = Field(default=None, max_length=256)
    transform: str = Field(default="none", pattern="^(none|uppercase|lowercase|trim)$")
    sort_order: int = Field(default=0, ge=0)


class ColumnMappingCreate(ColumnMappingBase):
    """Schema for creating column mapping."""

    pass


class ColumnMappingResponse(ColumnMappingBase):
    """Schema for column mapping response."""

    id: str


# =============================================================================
# Sorting Rule Schemas
# =============================================================================


class SortingRuleBase(BaseModel):
    """Base schema for sorting rule."""

    column_name: str = Field(..., min_length=1, max_length=128)
    direction: str = Field(default="asc", pattern="^(asc|desc)$")
    priority: int = Field(default=1, ge=1)


class SortingRuleCreate(SortingRuleBase):
    """Schema for creating sorting rule."""

    pass


class SortingRuleResponse(SortingRuleBase):
    """Schema for sorting rule response."""

    id: str


# =============================================================================
# Filtering Rule Schemas
# =============================================================================


class FilteringRuleBase(BaseModel):
    """Base schema for filtering rule."""

    column_name: str = Field(..., min_length=1, max_length=128)
    operator: str = Field(
        ...,
        pattern="^(equals|not_equals|contains|gt|lt|gte|lte|in|not_in|is_null|is_not_null)$",
    )
    value: str | None = None
    value_type: str = Field(default="string", pattern="^(string|number|date|boolean)$")
    logic_group: str = Field(default="AND", pattern="^(AND|OR)$")


class FilteringRuleCreate(FilteringRuleBase):
    """Schema for creating filtering rule."""

    pass


class FilteringRuleResponse(FilteringRuleBase):
    """Schema for filtering rule response."""

    id: str


# =============================================================================
# Row Rule Schemas
# =============================================================================


class RowRuleBase(BaseModel):
    """Base schema for row rule."""

    rule_type: str = Field(default="none", pattern="^(none|top_n|bottom_n|custom)$")
    limit_value: int | None = Field(default=None, ge=1)
    limit_column: str | None = Field(default=None, max_length=128)
    custom_expression: str | None = None


class RowRuleCreate(RowRuleBase):
    """Schema for creating row rule."""

    pass


class RowRuleResponse(RowRuleBase):
    """Schema for row rule response."""

    id: str


# =============================================================================
# Highlight Rule Schemas
# =============================================================================


class HighlightRuleBase(BaseModel):
    """Base schema for highlight rule."""

    column_name: str = Field(..., min_length=1, max_length=128)
    condition_type: str = Field(..., pattern="^(equals|gt|lt|gte|lte|contains|between)$")
    condition_value: str | None = None
    highlight_color: str = Field(default="#FFFF00", pattern="^#[0-9A-Fa-f]{6}$")
    text_color: str | None = Field(default=None, pattern="^#[0-9A-Fa-f]{6}$")
    is_bold: bool = False
    priority: int = Field(default=1, ge=1)


class HighlightRuleCreate(HighlightRuleBase):
    """Schema for creating highlight rule."""

    pass


class HighlightRuleResponse(HighlightRuleBase):
    """Schema for highlight rule response."""

    id: str


# =============================================================================
# Output Configuration Schemas
# =============================================================================


class OutputConfigBase(BaseModel):
    """Base schema for output configuration."""

    excel_enabled: bool = True
    excel_config: dict[str, Any] = Field(default_factory=dict)
    pdf_enabled: bool = False
    pdf_config: dict[str, Any] = Field(default_factory=dict)
    ai_summary_enabled: bool = False
    ai_config: dict[str, Any] = Field(default_factory=dict)
    whatsapp_enabled: bool = False
    whatsapp_config: dict[str, Any] = Field(default_factory=dict)
    email_enabled: bool = False
    email_config: dict[str, Any] = Field(default_factory=dict)


class OutputConfigCreate(OutputConfigBase):
    """Schema for creating output configuration."""

    pass


class OutputConfigResponse(OutputConfigBase):
    """Schema for output configuration response."""

    id: str


# =============================================================================
# Template Schemas
# =============================================================================


class TemplateBase(BaseModel):
    """Base schema for template."""

    name: str = Field(..., min_length=1, max_length=128)
    slug: str | None = Field(default=None, max_length=64)
    description: str | None = None
    source_report_id: str | None = Field(default=None, max_length=64)
    is_enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class TemplateCreate(TemplateBase):
    """Schema for creating a template."""

    input_config: InputConfigCreate | None = None
    column_mappings: list[ColumnMappingCreate] = Field(default_factory=list)
    sorting_rules: list[SortingRuleCreate] = Field(default_factory=list)
    filtering_rules: list[FilteringRuleCreate] = Field(default_factory=list)
    row_rule: RowRuleCreate | None = None
    highlight_rules: list[HighlightRuleCreate] = Field(default_factory=list)
    output_config: OutputConfigCreate | None = None


class TemplateUpdate(BaseModel):
    """Schema for updating a template."""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    slug: str | None = Field(default=None, max_length=64)
    description: str | None = None
    source_report_id: str | None = None
    is_enabled: bool | None = None
    metadata: dict[str, Any] | None = None
    input_config: InputConfigCreate | None = None
    column_mappings: list[ColumnMappingCreate] | None = None
    sorting_rules: list[SortingRuleCreate] | None = None
    filtering_rules: list[FilteringRuleCreate] | None = None
    row_rule: RowRuleCreate | None = None
    highlight_rules: list[HighlightRuleCreate] | None = None
    output_config: OutputConfigCreate | None = None


class TemplateResponse(BaseModel):
    """Schema for template response."""

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
    input_config: InputConfigResponse | None = None
    column_mappings: list[ColumnMappingResponse] = Field(default_factory=list)
    sorting_rules: list[SortingRuleResponse] = Field(default_factory=list)
    filtering_rules: list[FilteringRuleResponse] = Field(default_factory=list)
    row_rule: RowRuleResponse | None = None
    highlight_rules: list[HighlightRuleResponse] = Field(default_factory=list)
    output_config: OutputConfigResponse | None = None


class TemplateListItem(BaseModel):
    """Schema for template list item."""

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


class TemplateListResponse(BaseModel):
    """Schema for template list response."""

    templates: list[TemplateListItem]
    total: int


# =============================================================================
# Action Schemas
# =============================================================================


class DuplicateTemplateRequest(BaseModel):
    """Schema for duplicating a template."""

    new_name: str = Field(..., min_length=1, max_length=128)


class ValidationResult(BaseModel):
    """Schema for validation result."""

    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ToggleResponse(BaseModel):
    """Schema for toggle response."""

    id: str
    is_enabled: bool
    message: str


class DeleteResponse(BaseModel):
    """Schema for delete response."""

    success: bool
    message: str
