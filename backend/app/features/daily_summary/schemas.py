"""Pydantic schemas for Daily Summary APIs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DailySummaryResponse(BaseModel):
    summary_id: str
    run_id: str | None = None
    user_id: str | None = None
    report_date: str | None = None
    status: str
    text: str
    source_reports: list[str] = Field(default_factory=list)
    source_row_counts: dict[str, int] = Field(default_factory=dict)
    missing_reports: list[str] = Field(default_factory=list)
    run_status: str | None = None
    error_message: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class DailySummaryListItem(BaseModel):
    summary_id: str
    run_id: str | None = None
    report_date: str | None = None
    status: str
    created_at: str | None = None
    updated_at: str | None = None
    missing_reports: list[str] = Field(default_factory=list)


class DailySummaryListResponse(BaseModel):
    items: list[DailySummaryListItem]
    total: int
