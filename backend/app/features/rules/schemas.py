"""Pydantic schemas for Business Rules Engine."""

from typing import Any, Literal

from pydantic import BaseModel, Field


# =============================================================================
# Rule Categories
# =============================================================================

RuleCategory = Literal[
    "column",
    "conditional",
    "sorting",
    "filter",
    "top",
    "highlight",
    "calculation",
    "merge",
]

# =============================================================================
# Condition Schemas (used across multiple rule types)
# =============================================================================

ConditionOperator = Literal[
    "equals",
    "not_equals",
    "contains",
    "not_contains",
    "starts_with",
    "ends_with",
    "gt",
    "lt",
    "gte",
    "lte",
    "in",
    "not_in",
    "is_null",
    "is_not_null",
    "between",
    "regex",
]


class Condition(BaseModel):
    """A single condition for filtering or conditional logic."""

    field: str = Field(..., min_length=1)
    operator: ConditionOperator
    value: Any = None
    value_type: Literal["string", "number", "date", "boolean"] = "string"


class ConditionGroup(BaseModel):
    """A group of conditions with logical operator."""

    logic: Literal["AND", "OR"] = "AND"
    conditions: list[Condition] = Field(default_factory=list)
    nested: list["ConditionGroup"] = Field(default_factory=list)


# =============================================================================
# Style Schema (for highlight rules)
# =============================================================================


class StyleConfig(BaseModel):
    """Style configuration for highlighting."""

    background_color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    text_color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    bold: bool = False
    italic: bool = False
    border: Literal["none", "thin", "medium", "thick"] | None = None


# =============================================================================
# Column Rule Configs
# =============================================================================


class ColumnRenameConfig(BaseModel):
    """Config for renaming a column."""

    source: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)


class ColumnHideConfig(BaseModel):
    """Config for hiding columns."""

    columns: list[str] = Field(..., min_length=1)


class ColumnCreateConfig(BaseModel):
    """Config for creating a computed column."""

    name: str = Field(..., min_length=1)
    expression: str = Field(..., min_length=1)
    data_type: Literal["text", "number", "date", "boolean"] = "text"
    format: str | None = None


class ColumnDeleteConfig(BaseModel):
    """Config for deleting columns."""

    columns: list[str] = Field(..., min_length=1)


class ColumnReorderConfig(BaseModel):
    """Config for reordering columns."""

    order: list[str] = Field(..., min_length=1)


class ColumnCopyConfig(BaseModel):
    """Config for copying a column."""

    source: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)


# =============================================================================
# Conditional Rule Configs
# =============================================================================


class ConditionalIncludeColumnConfig(BaseModel):
    """Config for conditionally including a column."""

    condition: ConditionGroup
    column: str = Field(..., min_length=1)


class ConditionalExcludeColumnConfig(BaseModel):
    """Config for conditionally excluding a column."""

    condition: ConditionGroup
    column: str = Field(..., min_length=1)


class ConditionalSetValueConfig(BaseModel):
    """Config for conditionally setting a value."""

    condition: ConditionGroup
    column: str = Field(..., min_length=1)
    value: Any


class ConditionalApplyFormatConfig(BaseModel):
    """Config for conditionally applying format."""

    condition: ConditionGroup
    column: str = Field(..., min_length=1)
    format: str = Field(..., min_length=1)


# =============================================================================
# Sorting Rule Configs
# =============================================================================


class SortColumn(BaseModel):
    """A single sort specification."""

    column: str = Field(..., min_length=1)
    direction: Literal["asc", "desc"] = "asc"
    priority: int = Field(default=1, ge=1)


class SortingSingleConfig(BaseModel):
    """Config for single column sort."""

    column: str = Field(..., min_length=1)
    direction: Literal["asc", "desc"] = "asc"


class SortingMultiConfig(BaseModel):
    """Config for multi-column sort."""

    sorts: list[SortColumn] = Field(..., min_length=1)


class SortingCustomConfig(BaseModel):
    """Config for custom sort expression."""

    expression: str = Field(..., min_length=1)


# =============================================================================
# Filter Rule Configs
# =============================================================================


class FilterIncludeConfig(BaseModel):
    """Config for include filter."""

    logic: Literal["AND", "OR"] = "AND"
    conditions: list[Condition] = Field(..., min_length=1)


class FilterExcludeConfig(BaseModel):
    """Config for exclude filter."""

    logic: Literal["AND", "OR"] = "AND"
    conditions: list[Condition] = Field(..., min_length=1)


class FilterDistinctConfig(BaseModel):
    """Config for distinct filter."""

    columns: list[str] = Field(..., min_length=1)


class FilterNotNullConfig(BaseModel):
    """Config for not null filter."""

    columns: list[str] = Field(..., min_length=1)


# =============================================================================
# Top/Limit Rule Configs
# =============================================================================


class TopNConfig(BaseModel):
    """Config for top N rows."""

    n: int = Field(..., ge=1)
    by_column: str = Field(..., min_length=1)
    direction: Literal["asc", "desc"] = "desc"


class BottomNConfig(BaseModel):
    """Config for bottom N rows."""

    n: int = Field(..., ge=1)
    by_column: str = Field(..., min_length=1)
    direction: Literal["asc", "desc"] = "asc"


class TopPercentConfig(BaseModel):
    """Config for top percent rows."""

    percent: float = Field(..., gt=0, le=100)
    by_column: str = Field(..., min_length=1)
    direction: Literal["asc", "desc"] = "desc"


class LimitConfig(BaseModel):
    """Config for limit/offset."""

    offset: int = Field(default=0, ge=0)
    limit: int = Field(..., ge=1)


# =============================================================================
# Highlight Rule Configs
# =============================================================================


class HighlightCellConfig(BaseModel):
    """Config for cell highlighting."""

    condition: ConditionGroup
    style: StyleConfig


class HighlightRowConfig(BaseModel):
    """Config for row highlighting."""

    condition: ConditionGroup
    style: StyleConfig


class HighlightColumnConfig(BaseModel):
    """Config for column highlighting."""

    column: str = Field(..., min_length=1)
    style: StyleConfig


class HighlightGradientConfig(BaseModel):
    """Config for gradient highlighting."""

    column: str = Field(..., min_length=1)
    min_color: str = Field(..., pattern=r"^#[0-9A-Fa-f]{6}$")
    max_color: str = Field(..., pattern=r"^#[0-9A-Fa-f]{6}$")


class HighlightDataBarConfig(BaseModel):
    """Config for data bar highlighting."""

    column: str = Field(..., min_length=1)
    color: str = Field(..., pattern=r"^#[0-9A-Fa-f]{6}$")


# =============================================================================
# Calculation Rule Configs
# =============================================================================

AggregateFunction = Literal["sum", "avg", "count", "min", "max", "median", "stddev", "variance"]


class CalcPercentageConfig(BaseModel):
    """Config for percentage calculation."""

    numerator: str = Field(..., min_length=1)
    denominator: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)
    decimal_places: int = Field(default=2, ge=0, le=10)


class CalcAggregateConfig(BaseModel):
    """Config for aggregate calculation."""

    function: AggregateFunction
    column: str = Field(..., min_length=1)
    group_by: list[str] = Field(default_factory=list)
    target: str = Field(..., min_length=1)


class CalcExpressionConfig(BaseModel):
    """Config for expression calculation."""

    expression: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)


class CalcRunningConfig(BaseModel):
    """Config for running calculation."""

    function: AggregateFunction
    column: str = Field(..., min_length=1)
    order_by: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)


class CalcDifferenceConfig(BaseModel):
    """Config for difference calculation."""

    column1: str = Field(..., min_length=1)
    column2: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)


class CalcTrendConfig(BaseModel):
    """Config for trend calculation."""

    column: str = Field(..., min_length=1)
    periods: int = Field(..., ge=1)
    target: str = Field(..., min_length=1)


# =============================================================================
# Merge Rule Configs
# =============================================================================

JoinType = Literal["inner", "left", "right", "outer", "cross"]


class MergeJoinConfig(BaseModel):
    """Config for join merge."""

    datasets: list[str] = Field(..., min_length=2)
    on: list[str] = Field(..., min_length=1)
    type: JoinType = "left"
    conflict_resolution: dict[str, Any] | None = None


class MergeUnionConfig(BaseModel):
    """Config for union merge."""

    datasets: list[str] = Field(..., min_length=2)
    dedupe: bool = True


class MergeCompareConfig(BaseModel):
    """Config for compare merge."""

    dataset1: str = Field(..., min_length=1)
    dataset2: str = Field(..., min_length=1)
    key_columns: list[str] = Field(..., min_length=1)
    compare_columns: list[str] = Field(..., min_length=1)


class MergeDedupeConfig(BaseModel):
    """Config for dedupe merge."""

    columns: list[str] = Field(..., min_length=1)
    keep: Literal["first", "last", "none"] = "first"


class MergeConflictConfig(BaseModel):
    """Config for conflict resolution."""

    strategy: Literal["prefer_first", "prefer_last", "error"] = "prefer_first"
    priority_dataset: str | None = None


# =============================================================================
# Rule Request/Response Schemas
# =============================================================================


class RuleBase(BaseModel):
    """Base schema for rules."""

    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    category: RuleCategory
    rule_type: str = Field(..., min_length=1, max_length=64)
    config: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=0, ge=0)
    group_id: str | None = Field(default=None, max_length=64)
    is_enabled: bool = True
    is_global: bool = False
    conditions: ConditionGroup | None = None


class RuleCreate(RuleBase):
    """Schema for creating a rule."""

    template_id: str | None = None


class RuleUpdate(BaseModel):
    """Schema for updating a rule."""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    category: RuleCategory | None = None
    rule_type: str | None = Field(default=None, min_length=1, max_length=64)
    config: dict[str, Any] | None = None
    priority: int | None = Field(default=None, ge=0)
    group_id: str | None = None
    is_enabled: bool | None = None
    is_global: bool | None = None
    conditions: ConditionGroup | None = None
    template_id: str | None = None


class RuleResponse(RuleBase):
    """Schema for rule response."""

    id: str
    template_id: str | None
    is_deleted: bool
    created_by: str | None
    updated_by: str | None
    created_at: str
    updated_at: str


class RuleListItem(BaseModel):
    """Schema for rule list item."""

    id: str
    name: str
    description: str | None
    category: str
    rule_type: str
    template_id: str | None
    priority: int
    group_id: str | None
    is_enabled: bool
    is_global: bool
    created_at: str
    updated_at: str


class RuleListResponse(BaseModel):
    """Schema for rule list response."""

    rules: list[RuleListItem]
    total: int


# =============================================================================
# Rule Testing Schemas
# =============================================================================


class RuleTestRequest(BaseModel):
    """Schema for testing a rule."""

    rule_id: str | None = None
    rule_config: RuleCreate | None = None
    sample_data: list[dict[str, Any]] = Field(..., min_length=1)


class RuleTestResult(BaseModel):
    """Schema for rule test result."""

    success: bool
    output_data: list[dict[str, Any]]
    row_count: int
    column_count: int
    execution_time_ms: float
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RuleValidationRequest(BaseModel):
    """Schema for validating rule config."""

    category: RuleCategory
    rule_type: str
    config: dict[str, Any]


class RuleValidationResult(BaseModel):
    """Schema for validation result."""

    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# =============================================================================
# Category/Function Info Schemas
# =============================================================================


class RuleTypeInfo(BaseModel):
    """Information about a rule type."""

    type: str
    name: str
    description: str
    config_schema: dict[str, Any]


class CategoryInfo(BaseModel):
    """Information about a rule category."""

    category: str
    name: str
    description: str
    rule_types: list[RuleTypeInfo]


class FunctionInfo(BaseModel):
    """Information about an expression function."""

    name: str
    description: str
    signature: str
    examples: list[str]


# =============================================================================
# Execution Schemas
# =============================================================================


class ExecuteRulesRequest(BaseModel):
    """Schema for executing rules."""

    template_id: str
    data: list[dict[str, Any]] = Field(..., min_length=1)
    variables: dict[str, Any] = Field(default_factory=dict)


class HighlightInfo(BaseModel):
    """Information about a highlight to apply."""

    row: int
    column: str
    style: StyleConfig


class ExecuteRulesResult(BaseModel):
    """Schema for rule execution result."""

    success: bool
    output_data: list[dict[str, Any]]
    highlights: list[HighlightInfo] = Field(default_factory=list)
    row_count: int
    column_count: int
    execution_time_ms: float
    rules_executed: int
    execution_log: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# =============================================================================
# Reorder Schema
# =============================================================================


class ReorderRulesRequest(BaseModel):
    """Schema for reordering rules."""

    rule_priorities: list[dict[str, Any]] = Field(
        ..., 
        description="List of {id: rule_id, priority: new_priority}",
        min_length=1,
    )
