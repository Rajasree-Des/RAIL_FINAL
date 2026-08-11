"""Dashboard summary response schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.features.activity.schemas import ActivityEntry

# Canonical status vocabulary shared with the frontend
DashboardStatus = Literal[
    "ready",
    "pending",
    "running",
    "processing",
    "paused",
    "success",
    "partial_success",
    "failed",
    "stopped",
    "skipped",
]


class DashboardReportStatus(BaseModel):
    """Per-report live status derived from the reference run, keyed by slug."""

    slug: str
    name: str
    status: DashboardStatus = "pending"
    error: str | None = None
    last_duration_seconds: float | None = None


class AnalyticsTotals(BaseModel):
    """KPI totals derived from the zone-wise (all-India) report."""

    complaints_received: int
    feedback_received: int
    complaints_resolved: int
    resolution_rate: float


class ZoneRow(BaseModel):
    rank: int
    zone: str
    complaints: int
    feedback: int
    resolution_pct: float | None = None


class DivisionRow(BaseModel):
    rank: int
    division: str
    complaints: int
    feedback: int
    resolution_pct: float | None = None


class TrainRow(BaseModel):
    rank: int
    train_no: str
    train_name: str
    complaints: int
    resolution_pct: float | None = None


class ScrEntityRow(BaseModel):
    name: str
    label: str | None = None
    complaints: int
    complaint_types: list[str] = Field(default_factory=list)
    resolution_pct: float | None = None


class ComplaintTypeRow(BaseModel):
    type_name: str
    complaints: int
    percentage: float


class NameCount(BaseModel):
    name: str
    count: int


class FeedbackDistribution(BaseModel):
    total: int
    excellent: int
    satisfactory: int
    unsatisfactory: int


class ReportFileMeta(BaseModel):
    file_type: str
    file_size_bytes: int | None = None
    download_url: str | None = None
    preview_url: str | None = None


class ReportCardInfo(BaseModel):
    slug: str
    name: str
    status: DashboardStatus = "pending"
    generated_at: str | None = None
    duration_seconds: float | None = None
    sections_total: int | None = None
    row_count: int | None = None
    files: list[ReportFileMeta] = Field(default_factory=list)


class DashboardAnalyticsResponse(BaseModel):
    """Aggregations computed from the latest completed run's report outputs."""

    has_data: bool = False
    run_id: str | None = None
    generated_at: str | None = None
    totals: AnalyticsTotals | None = None
    zones: list[ZoneRow] = Field(default_factory=list)
    divisions: list[DivisionRow] = Field(default_factory=list)
    trains: list[TrainRow] = Field(default_factory=list)
    scr_trains: list[ScrEntityRow] = Field(default_factory=list)
    scr_stations: list[ScrEntityRow] = Field(default_factory=list)
    complaint_types: list[ComplaintTypeRow] = Field(default_factory=list)
    feedback_distribution: FeedbackDistribution | None = None
    top_causes: list[NameCount] = Field(default_factory=list)
    complaints_by_report: list[NameCount] = Field(default_factory=list)
    report_cards: list[ReportCardInfo] = Field(default_factory=list)


class DashboardSummaryResponse(BaseModel):
    current_status: DashboardStatus = "ready"
    active_run_id: str | None = None
    last_run_id: str | None = None
    last_run_status: DashboardStatus | None = None
    last_generated_at: str | None = None
    successful_report_count: int = 0
    failed_report_count: int = 0
    generated_report_count: int = 0
    total_enabled_reports: int = 0
    estimated_duration_seconds: float | None = None
    # Configured fallback estimate used when there is no run history
    default_expected_duration_seconds: float = 900
    reports: list[DashboardReportStatus] = Field(default_factory=list)
    recent_activity: list[ActivityEntry] = Field(default_factory=list)
