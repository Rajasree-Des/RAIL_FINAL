"""Schemas for manual report generation API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.automation.date_range import DateRangeValidationError, ReportDateRange


ManualUiStatus = Literal[
    "Waiting",
    "Extracting",
    "Ingesting",
    "Processing",
    "Generating Excel/PDF",
    "Completed",
    "Failed",
]


class ColumnSelectionRequest(BaseModel):
    selected_column_ids: list[str] = Field(default_factory=list)
    column_order: list[str] = Field(default_factory=list)

    @field_validator("selected_column_ids", "column_order", mode="before")
    @classmethod
    def _coerce_list(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value]
        return []


class ManualGenerateRequest(ColumnSelectionRequest):
    report_slug: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    export_format: Literal["xlsx", "pdf", "csv"] = "xlsx"
    requested_formats: list[Literal["xlsx", "pdf"]] = Field(default_factory=lambda: ["xlsx", "pdf"])
    config_overrides: dict[str, Any] = Field(default_factory=dict)
    filter_conditions: list[dict[str, Any]] = Field(default_factory=list)
    configuration_source: Literal["manual_snapshot"] = "manual_snapshot"
    force_fresh_extraction: bool = False
    sections: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_date_range(self) -> "ManualGenerateRequest":
        if self.date_from is None or self.date_to is None:
            raise ValueError("date_from and date_to are required")
        try:
            ReportDateRange.from_iso(self.date_from, self.date_to)
        except DateRangeValidationError as exc:
            raise ValueError(str(exc)) from exc
        return self


class OutputPreviewRequest(ColumnSelectionRequest):
    pass


class SectionPreview(BaseModel):
    title: str
    headers: list[str] = Field(default_factory=list)
    rows: list[dict[str, str | int | float]] = Field(default_factory=list)
    empty: bool = False


class OutputPreviewResponse(BaseModel):
    available: bool
    message: str | None = None
    report_slug: str | None = None
    visible_columns: list[str] = Field(default_factory=list)
    preview_rows: list[dict[str, str | int | float]] = Field(default_factory=list)
    sections: list[SectionPreview] = Field(default_factory=list)
    selected_count: int = 0
    selected_column_ids: list[str] = Field(default_factory=list)
    column_order: list[str] = Field(default_factory=list)
    preview_version: int = 0


class ManualGenerateResponse(BaseModel):
    run_id: str
    report_slug: str
    report_date: str
    status: ManualUiStatus
    message: str = "Manual report generation started"


class ManualRunStatusResponse(BaseModel):
    run_id: str
    report_slug: str
    report_date: str | None = None
    status: ManualUiStatus
    run_status: str
    source_row_count: int | None = None
    processed_row_count: int | None = None
    row_counts: dict[str, int | float] = Field(default_factory=dict)
    extraction_success: bool = False
    ingestion_success: bool = False
    processing_success: bool = False
    artifact_id: str | None = None
    preview_url: str | None = None
    download_url: str | None = None
    export_format: str = "xlsx"
    excel_artifact_id: str | None = None
    excel_download_url: str | None = None
    excel_filename: str | None = None
    excel_file_size: int | None = None
    pdf_artifact_id: str | None = None
    pdf_download_url: str | None = None
    pdf_preview_url: str | None = None
    pdf_filename: str | None = None
    pdf_file_size: int | None = None
    visible_columns: list[str] = Field(default_factory=list)
    preview_rows: list[dict[str, str | int | float]] = Field(default_factory=list)
    output_filename: str | None = None
    output_file_size: int | None = None
    generated_at: str | None = None
    error: str | None = None


class SaveReportConfigRequest(ColumnSelectionRequest):
    export_format: Literal["xlsx", "pdf", "csv"] = "xlsx"
    config_overrides: dict[str, Any] = Field(default_factory=dict)
    filter_conditions: list[dict[str, Any]] = Field(default_factory=list)
    sections: dict[str, Any] = Field(default_factory=dict)
    date_from: str | None = None
    date_to: str | None = None
    # User-editable defaults for Output Column Filters (optional on partial saves).
    default_selected_column_ids: list[str] | None = None
    # Per-section defaults for comprehensive reports 10–13.
    default_sections: dict[str, Any] | None = None

    @field_validator("default_selected_column_ids", mode="before")
    @classmethod
    def _coerce_default_ids(cls, value: object) -> list[str] | None:
        if value is None:
            return None
        if isinstance(value, list):
            return [str(item) for item in value]
        return None


class SaveReportConfigResponse(BaseModel):
    report_slug: str
    saved: bool = True
    message: str = "Configuration saved"


class ReportConfigResponse(BaseModel):
    report_slug: str
    available_columns: list[dict[str, Any]] = Field(default_factory=list)
    selected_column_ids: list[str] = Field(default_factory=list)
    column_order: list[str] = Field(default_factory=list)
    default_column_ids: list[str] = Field(default_factory=list)
    default_selected_column_ids: list[str] = Field(default_factory=list)
    default_sections: dict[str, Any] = Field(default_factory=dict)
    has_saved_configuration: bool = False
    export_format: Literal["xlsx", "pdf", "csv"] = "xlsx"
    config_overrides: dict[str, Any] = Field(default_factory=dict)
    filter_conditions: list[dict[str, Any]] = Field(default_factory=list)
    sections: dict[str, Any] = Field(default_factory=dict)
    date_from: str | None = None
    date_to: str | None = None
