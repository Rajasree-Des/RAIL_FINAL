"""Pydantic schemas for AI Summary Generator."""

from typing import Any, Literal

from pydantic import BaseModel, Field

SummaryType = Literal[
    "executive",
    "whatsapp",
    "email",
    "daily_highlights",
    "key_observations",
]

OutputFormat = Literal["markdown", "plain_text", "bullets"]


class ReportMetadata(BaseModel):
    """Metadata about the report being summarized."""

    report_name: str = Field(default="Railway Report")
    report_period: str = Field(default="")
    division: str | None = None
    included_reports: list[str] = Field(default_factory=list)
    generated_by: str | None = None


class ReportStatisticsResponse(BaseModel):
    """Pre-computed statistics returned with summary."""

    total_complaints: int = 0
    resolved_complaints: int = 0
    pending_complaints: int = 0
    resolution_rate: float = 0.0
    unsatisfactory_count: int = 0
    unsatisfactory_rate: float = 0.0
    top_complaint_types: list[dict[str, Any]] = Field(default_factory=list)
    top_divisions: list[dict[str, Any]] = Field(default_factory=list)
    top_trains: list[dict[str, Any]] = Field(default_factory=list)
    bottom_trains: list[dict[str, Any]] = Field(default_factory=list)
    scr_train_count: int = 0
    daily_highlights: list[str] = Field(default_factory=list)
    key_observations: list[str] = Field(default_factory=list)
    report_period: str = ""
    generated_at: str = ""


class GenerateSummaryRequest(BaseModel):
    """Request to generate an AI summary."""

    prompt_template_id: str | None = None
    summary_type: SummaryType | None = None
    dataset: list[dict[str, Any]] = Field(..., min_length=1)
    metadata: ReportMetadata = Field(default_factory=ReportMetadata)
    column_mapping: dict[str, str] | None = None
    regenerate: bool = False


class GeneratedSummaryResponse(BaseModel):
    """Response from summary generation."""

    id: str
    summary_type: str
    content: str
    statistics: ReportStatisticsResponse
    prompt_template_id: str | None
    generation_time_ms: float
    model_used: str | None = None
    created_at: str


class PromptTemplateBase(BaseModel):
    """Base schema for prompt templates."""

    name: str = Field(..., min_length=1, max_length=128)
    slug: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z0-9-]+$")
    summary_type: SummaryType
    description: str | None = None
    system_prompt: str = Field(..., min_length=10)
    user_prompt_template: str = Field(..., min_length=10)
    output_format: OutputFormat = "markdown"
    max_tokens: int = Field(default=1024, ge=100, le=4096)
    temperature: float = Field(default=0.3, ge=0.0, le=1.0)
    is_enabled: bool = True
    is_default: bool = False
    template_id: str | None = None


class PromptTemplateCreate(PromptTemplateBase):
    """Create prompt template request."""

    pass


class PromptTemplateUpdate(BaseModel):
    """Update prompt template request."""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    slug: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"^[a-z0-9-]+$")
    summary_type: SummaryType | None = None
    description: str | None = None
    system_prompt: str | None = Field(default=None, min_length=10)
    user_prompt_template: str | None = Field(default=None, min_length=10)
    output_format: OutputFormat | None = None
    max_tokens: int | None = Field(default=None, ge=100, le=4096)
    temperature: float | None = Field(default=None, ge=0.0, le=1.0)
    is_enabled: bool | None = None
    is_default: bool | None = None
    template_id: str | None = None


class PromptTemplateResponse(PromptTemplateBase):
    """Prompt template response."""

    id: str
    is_deleted: bool
    created_by: str | None
    updated_by: str | None
    created_at: str
    updated_at: str


class PromptTemplateListItem(BaseModel):
    """Prompt template list item."""

    id: str
    name: str
    slug: str
    summary_type: str
    description: str | None
    is_enabled: bool
    is_default: bool
    max_tokens: int
    temperature: float
    created_at: str
    updated_at: str


class PromptTemplateListResponse(BaseModel):
    """List of prompt templates."""

    templates: list[PromptTemplateListItem]
    total: int


class TestPromptRequest(BaseModel):
    """Test a prompt template with sample data."""

    sample_dataset: list[dict[str, Any]] = Field(..., min_length=1)
    sample_metadata: ReportMetadata = Field(default_factory=ReportMetadata)
    column_mapping: dict[str, str] | None = None


class TestPromptResponse(BaseModel):
    """Result of prompt template test."""

    content: str
    statistics: ReportStatisticsResponse
    rendered_user_prompt: str
    generation_time_ms: float
    model_used: str | None = None


class TogglePromptResponse(BaseModel):
    """Toggle prompt template response."""

    id: str
    is_enabled: bool


class DeletePromptResponse(BaseModel):
    """Delete prompt template response."""

    success: bool
    message: str
