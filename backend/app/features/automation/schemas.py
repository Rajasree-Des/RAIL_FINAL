"""Pydantic schemas for automation API."""

from typing import Any

from pydantic import BaseModel, Field


class ReportSequenceItem(BaseModel):
    name: str
    report_path: str = "/reports"
    filters: dict[str, Any] = Field(default_factory=dict)


class AutomationProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    slug: str = Field(..., min_length=1, max_length=64)
    portal_url: str
    username: str
    password: str
    download_folder: str = "downloads/railmadad"
    browser: str = "chromium"
    headless: bool = True
    timeout_ms: int = 60000
    retry_count: int = 3
    delay_seconds: int = 5
    report_sequence: list[ReportSequenceItem] = Field(default_factory=list)
    is_enabled: bool = True


class AutomationProfileUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    portal_url: str | None = None
    username: str | None = None
    password: str | None = None
    download_folder: str | None = None
    browser: str | None = None
    headless: bool | None = None
    timeout_ms: int | None = None
    retry_count: int | None = None
    delay_seconds: int | None = None
    report_sequence: list[ReportSequenceItem] | None = None
    is_enabled: bool | None = None


class AutomationProfileResponse(BaseModel):
    id: str
    name: str
    slug: str
    portal_url: str
    username_masked: str
    download_folder: str
    browser: str
    headless: bool
    timeout_ms: int
    retry_count: int
    delay_seconds: int
    report_sequence: list[ReportSequenceItem]
    is_enabled: bool
    created_at: str
    updated_at: str


class AutomationProfileListResponse(BaseModel):
    profiles: list[AutomationProfileResponse]
    total: int


class AutomationRunRequest(BaseModel):
    profile_id: str | None = None


class AutomationRunResponse(BaseModel):
    run_id: str
    status: str
    message: str


class AutomationControlResponse(BaseModel):
    success: bool
    run_id: str | None = None
    status: str
    message: str


class AutomationLogEntry(BaseModel):
    id: str
    level: str
    message: str
    created_at: str


class AutomationArtifactEntry(BaseModel):
    id: str
    artifact_type: str
    file_path: str
    file_size_bytes: int | None
    report_name: str | None
    created_at: str


class AutomationRunSummary(BaseModel):
    id: str
    profile_id: str
    profile_name: str
    status: str
    trigger_type: str
    success_count: int
    failure_count: int
    error_message: str | None
    started_at: str | None
    completed_at: str | None
    created_at: str


class AutomationStatusResponse(BaseModel):
    active_run: AutomationRunSummary | None = None
    last_run: AutomationRunSummary | None = None
    next_scheduled_at: str | None = None
    success_rate: float
    total_runs: int
    total_failures: int
    is_paused: bool = False


class AutomationHistoryResponse(BaseModel):
    runs: list[AutomationRunSummary]
    total: int


class AutomationLogsResponse(BaseModel):
    run_id: str | None
    logs: list[AutomationLogEntry]
    total: int


class AutomationCallbackRequest(BaseModel):
    run_id: str
    status: str
    success_count: int = 0
    failure_count: int = 0
    current_report_index: int = 0
    error_message: str | None = None
    log_message: str | None = None
    log_level: str = "info"
    artifact: dict[str, Any] | None = None
    session_state: str | None = None
