"""Pydantic schemas for user activity feed."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ActivityStatus = Literal["success", "error", "warning", "info"]


class ActivityEntry(BaseModel):
    id: str
    user_id: str
    action: str
    message: str
    status: ActivityStatus
    report_slug: str | None = None
    run_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class ActivityListResponse(BaseModel):
    items: list[ActivityEntry]
    total: int
    limit: int
    offset: int


class ActivityRecentResponse(BaseModel):
    items: list[ActivityEntry]
