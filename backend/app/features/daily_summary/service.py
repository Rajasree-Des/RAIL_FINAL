"""Daily Summary generation service."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.automation.utils import previous_day_report_date
from app.core.exceptions import NotFoundError, SummaryNotGeneratedError, ValidationError
from app.features.activity.emit import emit_activity
from app.features.daily_summary import SUMMARY_SOURCE_SLUGS
from app.features.daily_summary.builder import build_full_summary
from app.features.daily_summary.repository import DailySummaryRepository
from app.features.daily_summary.schemas import (
    DailySummaryListItem,
    DailySummaryListResponse,
    DailySummaryResponse,
)
from app.features.daily_summary.sources import resolve_run_sources
from app.infrastructure.database.models import AutomationRunModel, GeneratedSummaryModel

logger = logging.getLogger(__name__)


class DailySummaryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = DailySummaryRepository(session)

    async def generate(
        self,
        run_id: str,
        user_id: str,
        report_date: str | None = None,
        *,
        regenerated: bool = False,
    ) -> DailySummaryResponse:
        from app.features.daily_summary.schema_ensure import ensure_daily_summary_schema

        await ensure_daily_summary_schema()
        t0 = time.perf_counter()
        run = await self.session.get(AutomationRunModel, run_id)
        if run is None:
            raise NotFoundError("AutomationRun", run_id)
        if run.created_by and run.created_by != user_id:
            raise NotFoundError("AutomationRun", run_id)

        date_str = report_date or previous_day_report_date(fmt="%d.%m.%Y")

        await emit_activity(
            user_id=user_id,
            action="SUMMARY_GENERATION_STARTED",
            message=f"Daily summary generation started for run {run_id}",
            status="info",
            run_id=run_id,
            metadata={"report_date": date_str, "regenerated": regenerated},
            dedupe_key=f"summary_start:{run_id}:{int(t0)}" if regenerated else f"summary_start:{run_id}",
        )

        try:
            sources = resolve_run_sources(run)
            if not sources.all_terminal and run.status not in {
                "completed",
                "failed",
                "stopped",
            }:
                raise ValidationError(
                    "Summary can only be generated after the run reaches a terminal status"
                )

            text, row_counts, missing, notes = build_full_summary(sources, date_str)
            # Reconciliation notes are appended inside build_full_summary; persist all notes.
            source_reports = [
                slug
                for slug in SUMMARY_SOURCE_SLUGS
                if slug in sources.reports and sources.reports[slug].available
            ]
            source_paths = {
                slug: sources.reports[slug].source_csv_path
                for slug in source_reports
                if sources.reports[slug].source_csv_path
            }

            if not source_reports:
                status = "failed"
            else:
                required_missing = [
                    s for s in SUMMARY_SOURCE_SLUGS if s not in source_reports
                ]
                if required_missing:
                    status = "partial_success"
                    missing = list(dict.fromkeys(missing + required_missing))
                else:
                    status = "success"

            # R5 percent missing → partial when R5 otherwise present
            if (
                status == "success"
                and "scr-train" in source_reports
                and any("unsatisfactory_percent" in n for n in notes)
            ):
                status = "partial_success"

            metadata: dict[str, Any] = {
                "source_reports": source_reports,
                "source_row_counts": row_counts,
                "missing_reports": missing,
                "source_paths_used": source_paths,
                "validation_notes": notes,
                "run_status": run.status,
            }
            elapsed_ms = (time.perf_counter() - t0) * 1000
            row = await self.repository.upsert(
                run_id=run_id,
                user_id=user_id,
                report_date=date_str,
                content=text,
                status=status,
                metadata=metadata,
                error_message=None if status != "failed" else "; ".join(missing) or "No sources",
                generation_time_ms=round(elapsed_ms, 2),
            )

            action = (
                "SUMMARY_REGENERATED"
                if regenerated
                else (
                    "SUMMARY_GENERATED"
                    if status == "success"
                    else "SUMMARY_PARTIAL"
                    if status == "partial_success"
                    else "SUMMARY_GENERATION_FAILED"
                )
            )
            await emit_activity(
                user_id=user_id,
                action=action,
                message=f"Daily summary {status} for {date_str}",
                status=(
                    "success"
                    if status == "success"
                    else "warning"
                    if status == "partial_success"
                    else "error"
                ),
                run_id=run_id,
                metadata={
                    "summary_id": row.id,
                    "report_date": date_str,
                    "source_row_counts": row_counts,
                    "missing_reports": missing,
                },
                dedupe_key=f"summary_done:{run_id}:{row.id}:{action}",
            )
            return self._to_response(row, run_status=run.status)
        except (NotFoundError, ValidationError):
            raise
        except Exception as exc:
            logger.exception("daily_summary_generation_failed run_id=%s", run_id)
            await emit_activity(
                user_id=user_id,
                action="SUMMARY_GENERATION_FAILED",
                message=str(exc)[:500],
                status="error",
                run_id=run_id,
                metadata={"report_date": date_str},
                dedupe_key=f"summary_fail:{run_id}",
            )
            # Persist failed stub so UI can show error
            row = await self.repository.upsert(
                run_id=run_id,
                user_id=user_id,
                report_date=date_str,
                content="",
                status="failed",
                metadata={"error": str(exc)[:500]},
                error_message=str(exc)[:1000],
            )
            return self._to_response(row, run_status=run.status)

    async def get_for_run(self, run_id: str, user_id: str) -> DailySummaryResponse:
        run = await self.session.get(AutomationRunModel, run_id)
        if run is None:
            raise NotFoundError("AutomationRun", run_id)
        if run.created_by and run.created_by != user_id:
            raise NotFoundError("AutomationRun", run_id)
        row = await self.repository.get_by_run_and_user(run_id, user_id)
        if row is None:
            raise SummaryNotGeneratedError(run_id)
        return self._to_response(row, run_status=run.status)

    async def get_by_id(self, summary_id: str, user_id: str) -> DailySummaryResponse:
        row = await self.repository.get_by_id_for_user(summary_id, user_id)
        if row is None:
            raise NotFoundError("DailySummary", summary_id)
        run_status = None
        if row.run_id:
            run = await self.session.get(AutomationRunModel, row.run_id)
            run_status = run.status if run else None
        return self._to_response(row, run_status=run_status)

    async def list_summaries(
        self, user_id: str, *, limit: int = 30, offset: int = 0
    ) -> DailySummaryListResponse:
        rows, total = await self.repository.list_for_user(
            user_id, limit=limit, offset=offset
        )
        items = [self._to_list_item(r) for r in rows]
        return DailySummaryListResponse(items=items, total=total)

    @staticmethod
    def _parse_meta(row: GeneratedSummaryModel) -> dict[str, Any]:
        if not row.metadata_json:
            return {}
        try:
            data = json.loads(row.metadata_json)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _to_response(
        self, row: GeneratedSummaryModel, *, run_status: str | None
    ) -> DailySummaryResponse:
        meta = self._parse_meta(row)
        return DailySummaryResponse(
            summary_id=row.id,
            run_id=row.run_id,
            user_id=row.created_by,
            report_date=row.report_date,
            status=row.status,
            text=row.content or "",
            source_reports=list(meta.get("source_reports") or []),
            source_row_counts={
                k: int(v) for k, v in (meta.get("source_row_counts") or {}).items()
            },
            missing_reports=list(meta.get("missing_reports") or []),
            run_status=run_status or meta.get("run_status"),
            error_message=row.error_message,
            created_at=row.created_at.isoformat() if row.created_at else None,
            updated_at=row.updated_at.isoformat() if row.updated_at else None,
        )

    def _to_list_item(self, row: GeneratedSummaryModel) -> DailySummaryListItem:
        meta = self._parse_meta(row)
        return DailySummaryListItem(
            summary_id=row.id,
            run_id=row.run_id,
            report_date=row.report_date,
            status=row.status,
            created_at=row.created_at.isoformat() if row.created_at else None,
            updated_at=row.updated_at.isoformat() if row.updated_at else None,
            missing_reports=list(meta.get("missing_reports") or []),
        )


async def generate_daily_summary_after_run(
    session: AsyncSession,
    run_id: str,
    user_id: str | None,
) -> None:
    """Fire-and-forget safe wrapper used from finalize_cdp_run."""
    if not user_id:
        return
    try:
        service = DailySummaryService(session)
        await service.generate(run_id, user_id)
    except Exception:
        logger.exception("auto_daily_summary_failed run_id=%s", run_id)
