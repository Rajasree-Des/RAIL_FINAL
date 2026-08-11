"""Pydantic schemas for in-process automation API responses."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class AutomationStartResult(BaseModel):
    """Outcome of a CDP attach, navigation, filter, generation, and download attempt."""

    success: bool
    connected: bool
    tab_found: bool
    url: str | None = None
    title: str | None = None
    error: str | None = None
    error_code: str | None = None
    report_reached: bool = False
    report_name: str | None = None
    screenshot_path: str | None = None
    report_generated: bool = False
    filters_applied: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int | None = None
    screenshot_before_path: str | None = None
    screenshot_after_path: str | None = None
    download_success: bool = False
    download_file_path: str | None = None
    download_file_size: int | None = None
    download_error: str | None = None
    ingestion_success: bool = False
    ingestion_attempted: bool = False
    ingestion_source: str | None = None
    ingestion_file_path: str | None = None
    screenshot_before_download_path: str | None = None
    screenshot_after_download_path: str | None = None
    html_extracted: bool = False
    extracted_data_path: str | None = None
    feedback_extracted: bool = False
    feedback_csv_path: str | None = None
    pdf_archived: bool = False
    pdf_archive_path: str | None = None
    pdf_archive_error: str | None = None
    pdf_archive_source: str | None = None
    processing_attempted: bool = False
    processing_success: bool = False
    processor_used: str | None = None
    input_row_count: int | None = None
    processed_row_count: int | None = None
    excel_path: str | None = None
    pdf_path: str | None = None
    processing_error: str | None = None
    source_a_path: str | None = None
    source_b_path: str | None = None
    source_a_rows: int | None = None
    source_b_rows: int | None = None
    # Phase 9 reliability fields
    session_valid: bool = True
    session_error_code: str | None = None
    table_valid: bool = True
    table_validation_error: str | None = None
    extraction_retry_attempted: bool = False
    extraction_retry_succeeded: bool = False


class ReportResult(BaseModel):
    """Outcome of a single report execution within a multi-report run."""

    slug: str
    status: Literal["success", "partial_success", "failed", "skipped"]
    dataset_key: str | None = None
    source_paths: list[str] = Field(default_factory=list)
    source_csv_path: str | None = None
    source_row_count: int | None = None
    row_counts: dict[str, int | float] = Field(default_factory=dict)
    ingestion_success: bool = False
    excel_path: str | None = None
    pdf_path: str | None = None
    pdf_download_url: str | None = None
    excel_download_url: str | None = None
    pdf_preview_url: str | None = None
    archive_path: str | None = None
    error: str | None = None
    processing_attempted: bool = False
    processing_success: bool = False
    processor_used: str | None = None
    input_row_count: int | None = None
    processed_row_count: int | None = None
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float | None = None
    extraction_seconds: float | None = None
    processing_seconds: float | None = None
    row_count: int | None = None
    output_columns: list[str] | None = None
    visible_columns: list[str] | None = None
    selected_column_ids: list[str] | None = None
    column_order: list[str] | None = None
    configuration_source: str | None = None


class MultiReportResult(BaseModel):
    """Outcome of a multi-report automation run."""

    success: bool
    connected: bool
    tab_found: bool = True
    reports: list[ReportResult] = Field(default_factory=list)
    stopped_early: bool = False
    stop_reason: str | None = None
    error: str | None = None
    error_code: str | None = None
    session_valid: bool = True
    run_id: str | None = None
    total_duration_seconds: float | None = None
    reports_successful: int = 0
    reports_failed: int = 0
    download_pdf_all_url: str | None = None
    download_excel_all_url: str | None = None
