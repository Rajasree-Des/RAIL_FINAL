"""Aggregate stored application events for administrative log export."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.features.activity.repository import ActivityRepository
from app.features.activity.service import scrub_message, scrub_metadata
from app.infrastructure.database.models import (
    AutomationLogModel,
    AutomationProfileModel,
    AutomationRunModel,
    UserActivityModel,
)

SENSITIVE_METADATA_KEYS = re.compile(
    r"(password|passwd|secret|token|cookie|authorization|api[_-]?key|csrf|"
    r"complaint|feedback|remarks|description|encrypted)",
    re.IGNORECASE,
)

MAX_EVENTS = 10_000


@dataclass
class AdminEvent:
    level: str
    created_at: datetime
    source: str
    event_id: str
    task_category: str
    message: str
    details: dict[str, str] = field(default_factory=dict)


def _event_id(raw_id: str | None) -> str:
    if not raw_id:
        return "N/A"
    return raw_id[:8].upper()


def _map_status_level(status: str | None) -> str:
    normalized = (status or "").lower()
    if normalized in {"error", "failed", "failure"}:
        return "Error"
    if normalized in {"warning", "warn"}:
        return "Warning"
    if normalized in {"success", "completed", "ok"}:
        return "Success"
    return "Information"


def _map_log_level(level: str | None) -> str:
    normalized = (level or "info").lower()
    if normalized in {"error", "critical", "fatal"}:
        return "Error"
    if normalized in {"warning", "warn"}:
        return "Warning"
    if normalized in {"success"}:
        return "Success"
    return "Information"


def _na(value: str | None) -> str:
    if value is None or str(value).strip() == "":
        return "N/A"
    return str(value)


def _ensure_utc(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.min.replace(tzinfo=UTC)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _scrub_export_metadata(metadata: Any) -> dict[str, str]:
    cleaned = scrub_metadata(metadata)
    if not isinstance(cleaned, dict):
        return {}
    result: dict[str, str] = {}
    for key, value in cleaned.items():
        if SENSITIVE_METADATA_KEYS.search(str(key)):
            continue
        if isinstance(value, (dict, list)):
            text = json.dumps(value, default=str)
        else:
            text = str(value)
        if len(text) > 500:
            text = text[:500] + "…"
        result[str(key)] = text
    return result


def _activity_event(row: UserActivityModel) -> AdminEvent:
    meta: dict[str, Any] = {}
    if row.metadata_json:
        try:
            meta = json.loads(row.metadata_json)
        except json.JSONDecodeError:
            meta = {}
    safe_meta = _scrub_export_metadata(meta)
    details: dict[str, str] = {}
    if row.run_id:
        details["Run ID"] = row.run_id
    if row.report_slug:
        details["Report"] = row.report_slug
    details["Status"] = _na(row.status)
    for key, value in safe_meta.items():
        details[key.replace("_", " ").title()] = value

    return AdminEvent(
        level=_map_status_level(row.status),
        created_at=_ensure_utc(row.created_at),
        source="Activity",
        event_id=_event_id(row.id),
        task_category=_na(row.action),
        message=scrub_message(row.message),
        details=details,
    )


def _automation_log_event(
    log: AutomationLogModel,
    run: AutomationRunModel | None,
    profile: AutomationProfileModel | None,
) -> AdminEvent:
    details: dict[str, str] = {"Run ID": log.run_id}
    if run is not None:
        details["Status"] = _na(run.status)
    if profile is not None:
        details["Report"] = _na(profile.slug)
        details["Profile"] = _na(profile.name)

    return AdminEvent(
        level=_map_log_level(log.level),
        created_at=_ensure_utc(log.created_at),
        source="Automation",
        event_id=_event_id(log.id),
        task_category="Run Log",
        message=scrub_message(log.message),
        details=details,
    )


def _failed_run_event(
    run: AutomationRunModel,
    profile: AutomationProfileModel | None,
) -> AdminEvent:
    details: dict[str, str] = {
        "Run ID": run.id,
        "Status": _na(run.status),
        "Failure Count": str(run.failure_count),
    }
    if profile is not None:
        details["Report"] = _na(profile.slug)
        details["Profile"] = _na(profile.name)
    if run.completed_at:
        details["Completed At"] = _ensure_utc(run.completed_at).isoformat()

    return AdminEvent(
        level="Error",
        created_at=_ensure_utc(run.completed_at or run.created_at),
        source="AutomationRun",
        event_id=_event_id(run.id),
        task_category="Run Failure",
        message=scrub_message(run.error_message or ""),
        details=details,
    )


async def collect_admin_events(session: AsyncSession) -> list[AdminEvent]:
    """Merge activity, automation logs, and failed runs; newest first."""
    events: list[AdminEvent] = []

    activity_rows, _ = await ActivityRepository(session).list_all(limit=MAX_EVENTS)
    events.extend(_activity_event(row) for row in activity_rows)

    log_stmt = (
        select(AutomationLogModel)
        .options(
            selectinload(AutomationLogModel.run).selectinload(AutomationRunModel.profile)
        )
        .order_by(AutomationLogModel.created_at.desc())
        .limit(MAX_EVENTS)
    )
    log_rows = list((await session.execute(log_stmt)).scalars().all())
    for log in log_rows:
        run = log.run
        profile = run.profile if run is not None else None
        events.append(_automation_log_event(log, run, profile))

    failed_stmt = (
        select(AutomationRunModel)
        .options(selectinload(AutomationRunModel.profile))
        .where(
            AutomationRunModel.status == "failed",
            AutomationRunModel.error_message.isnot(None),
            AutomationRunModel.error_message != "",
        )
        .order_by(AutomationRunModel.completed_at.desc())
        .limit(MAX_EVENTS)
    )
    failed_rows = list((await session.execute(failed_stmt)).scalars().all())
    events.extend(_failed_run_event(run, run.profile) for run in failed_rows)

    events.sort(key=lambda e: e.created_at, reverse=True)
    if len(events) > MAX_EVENTS:
        events = events[:MAX_EVENTS]
    return events
