"""Dashboard summary derivation from automation runs, artifacts, and catalog."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.automation.reports import catalog
from app.core.config import settings
from app.features.activity.service import ActivityService
from app.features.dashboard.schemas import (
    DashboardReportStatus,
    DashboardSummaryResponse,
)
from app.infrastructure.database.models import (
    AutomationArtifactModel,
    AutomationRunModel,
)

logger = logging.getLogger(__name__)

CDP_TRIGGER = "cdp_in_process"

ACTIVE_STATUSES = frozenset({"pending", "running", "cancel_requested"})
PAUSED_STATUSES = frozenset({"paused", "pause_requested"})
TERMINAL_STATUSES = frozenset({"completed", "failed", "stopped"})

ROLLING_AVG_RUNS = 5
RUN_SCAN_LIMIT = 25
# An unfinalized "running" run older than this is treated as stale (crashed)
STALE_ACTIVE_SECONDS = 30 * 60


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes despite DateTime(timezone=True)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def canonical_run_status(run: AutomationRunModel) -> str:
    """Map a run row to the canonical status vocabulary."""
    if run.status in ACTIVE_STATUSES:
        return "running"
    if run.status in PAUSED_STATUSES:
        return "paused"
    if run.status == "stopped":
        return "stopped"
    if run.status == "failed":
        return "failed"
    if run.status == "completed":
        if run.failure_count > 0 and run.success_count > 0:
            return "partial_success"
        if run.failure_count > 0 and run.success_count == 0:
            return "failed"
        return "success"
    return "pending"


def _parse_result_reports(result_json: str | None) -> dict[str, dict[str, Any]]:
    """Parse result_json into a slug-keyed report map (never array position)."""
    if not result_json:
        return {}
    try:
        data = json.loads(result_json)
    except (json.JSONDecodeError, TypeError):
        return {}
    reports = data.get("reports") if isinstance(data, dict) else None
    if not isinstance(reports, list):
        return {}
    by_slug: dict[str, dict[str, Any]] = {}
    for item in reports:
        if isinstance(item, dict) and item.get("slug"):
            by_slug[str(item["slug"])] = item
    return by_slug


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _recent_runs(self) -> list[AutomationRunModel]:
        stmt = (
            select(AutomationRunModel)
            .where(AutomationRunModel.trigger_type == CDP_TRIGGER)
            .order_by(AutomationRunModel.created_at.desc())
            .limit(RUN_SCAN_LIMIT)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def _ready_artifact_count(self, run_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(AutomationArtifactModel)
            .where(
                AutomationArtifactModel.run_id == run_id,
                AutomationArtifactModel.status == "ready",
                AutomationArtifactModel.artifact_type.in_(["excel", "pdf"]),
            )
        )
        return int((await self._session.execute(stmt)).scalar_one())

    def _estimated_duration(self, runs: list[AutomationRunModel]) -> float | None:
        durations: list[float] = []
        for run in runs:
            if run.status != "completed" or run.failure_count > 0:
                continue
            started = _aware(run.started_at)
            completed = _aware(run.completed_at)
            if started is None or completed is None or completed <= started:
                continue
            durations.append((completed - started).total_seconds())
            if len(durations) >= ROLLING_AVG_RUNS:
                break
        if not durations:
            return None
        return round(sum(durations) / len(durations), 1)

    def _report_statuses(
        self,
        reference_run: AutomationRunModel | None,
    ) -> list[DashboardReportStatus]:
        by_slug = (
            _parse_result_reports(reference_run.result_json) if reference_run else {}
        )
        out: list[DashboardReportStatus] = []
        for definition in catalog.reports:
            item = by_slug.get(definition.slug)
            if item is None:
                out.append(
                    DashboardReportStatus(
                        slug=definition.slug,
                        name=definition.name,
                        status="pending",
                    )
                )
                continue
            raw_status = str(item.get("status") or "pending")
            if raw_status not in {"success", "partial_success", "failed", "skipped"}:
                raw_status = "pending"
            error = item.get("error")
            if raw_status == "success":
                # Successful reports must not retain old warning/error messages
                error = None
            out.append(
                DashboardReportStatus(
                    slug=definition.slug,
                    name=definition.name,
                    status=raw_status,  # type: ignore[arg-type]
                    error=str(error) if error else None,
                    last_duration_seconds=item.get("duration_seconds"),
                )
            )
        return out

    async def summary(self, user_id: str) -> DashboardSummaryResponse:
        runs = await self._recent_runs()

        # Only the newest run can be active: stale "running" rows from older,
        # never-finalized runs must not overwrite the latest terminal outcome.
        active_run = None
        if runs and runs[0].status in ACTIVE_STATUSES | PAUSED_STATUSES:
            started = _aware(runs[0].started_at) or _aware(runs[0].created_at)
            age = (
                (datetime.now(UTC) - started).total_seconds()
                if started is not None
                else None
            )
            if age is None or age < STALE_ACTIVE_SECONDS:
                active_run = runs[0]
        latest_terminal = next(
            (r for r in runs if r.status in TERMINAL_STATUSES), None
        )
        last_completed = next((r for r in runs if r.status == "completed"), None)

        if active_run is not None:
            current_status = canonical_run_status(active_run)
        elif latest_terminal is not None:
            current_status = canonical_run_status(latest_terminal)
        else:
            current_status = "ready"

        reference_run = active_run or latest_terminal
        generated_report_count = (
            await self._ready_artifact_count(reference_run.id)
            if reference_run is not None
            else 0
        )

        last_generated_at = None
        if last_completed is not None:
            completed_at = _aware(last_completed.completed_at)
            last_generated_at = completed_at.isoformat() if completed_at else None

        recent = await ActivityService(self._session).recent(user_id, limit=10)

        return DashboardSummaryResponse(
            current_status=current_status,  # type: ignore[arg-type]
            active_run_id=active_run.id if active_run else None,
            last_run_id=latest_terminal.id if latest_terminal else None,
            last_run_status=(
                canonical_run_status(latest_terminal)  # type: ignore[arg-type]
                if latest_terminal
                else None
            ),
            last_generated_at=last_generated_at,
            successful_report_count=(
                reference_run.success_count if reference_run else 0
            ),
            failed_report_count=reference_run.failure_count if reference_run else 0,
            generated_report_count=generated_report_count,
            total_enabled_reports=len(catalog.reports),
            estimated_duration_seconds=self._estimated_duration(runs),
            default_expected_duration_seconds=(
                settings.dashboard_expected_minutes_default * 60
            ),
            reports=self._report_statuses(reference_run),
            recent_activity=recent.items,
        )
