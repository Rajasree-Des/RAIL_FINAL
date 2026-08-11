"""Per-run context: timing, deferred processing pool, artifact registration."""

from __future__ import annotations

import asyncio
import logging
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Coroutine

from app.automation.date_range import ReportDateRange
from app.automation.schemas import ReportResult
from app.automation.timing import RunTiming
from app.automation.utils import log_automation_event

logger = logging.getLogger(__name__)

_current: ContextVar["RunContext | None"] = ContextVar("automation_run_context", default=None)

PROCESS_CONCURRENCY = 3


def get_run_context() -> "RunContext | None":
    return _current.get()


def set_run_context(ctx: "RunContext | None"):
    return _current.set(ctx)


def reset_run_context(token) -> None:
    _current.reset(token)


@dataclass
class RunContext:
    """Shared state for one attach_to_railmadad invocation."""

    run_id: str
    timing: RunTiming
    user_id: str | None = None
    defer_processing: bool = True
    process_semaphore: asyncio.Semaphore = field(
        default_factory=lambda: asyncio.Semaphore(PROCESS_CONCURRENCY)
    )
    manual_config: dict | None = None
    current_run_sources: dict[str, str] = field(default_factory=dict)
    run_started_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    _tasks: list[asyncio.Task] = field(default_factory=list)
    _results: dict[str, ReportResult] = field(default_factory=dict)
    _artifact_ids: dict[str, dict[str, str]] = field(default_factory=dict)
    _ingested_keys: set[str] = field(default_factory=set)
    skip_portal_archive: bool = True
    phase1_from_date: str = ""
    date_range: ReportDateRange | None = None
    report_from_dates: dict[str, str] = field(default_factory=dict)

    def freeze_report_from_date(self, slug: str) -> str:
        """Freeze From Date once per report run (Reports 3/4/5/6)."""
        from app.automation.date_range import resolve_portal_from_date
        from app.automation.report_keys import canonicalize_report_key

        key = canonicalize_report_key(slug)
        if key not in self.report_from_dates:
            if self.date_range is not None:
                frozen = self.date_range.iso_from()
            else:
                frozen = resolve_portal_from_date()
            self.report_from_dates[key] = frozen
            event = (
                "phase3_from_date_frozen"
                if key in {"scr-train", "scr-station"}
                else "phase2_from_date_frozen"
            )
            log_automation_event(
                logger,
                event,
                run_id=self.run_id,
                report_slug=slug,
                expected_from_date=frozen,
            )
        return self.report_from_dates[key]

    def already_ingested(self, dataset_key: str, file_path: str) -> bool:
        return f"{dataset_key}|{file_path}" in self._ingested_keys

    def mark_ingested(self, dataset_key: str, file_path: str) -> None:
        self._ingested_keys.add(f"{dataset_key}|{file_path}")

    def store_partial(self, result: ReportResult) -> None:
        """Store an intermediate or handler-return result without downgrading terminals.

        If deferred processing already merged a terminal success/failed, a late
        handler return of ``partial_success`` with ``ingest/process pending``
        must not overwrite it.
        """
        existing = self._results.get(result.slug)
        if existing is not None and existing.status in {"success", "failed"}:
            if self._is_deferred_pending(result):
                return
        self._results[result.slug] = result
        try:
            loop = asyncio.get_running_loop()
            from app.automation.run_registry import persist_run_progress

            loop.create_task(
                persist_run_progress(self.run_id, self.get_results(), status="running")
            )
        except RuntimeError:
            pass

    @staticmethod
    def _is_deferred_pending(result: ReportResult) -> bool:
        err = (result.error or "").lower()
        return (
            result.status == "partial_success"
            and "ingest/process pending" in err
        )

    def merge_result(self, result: ReportResult) -> None:
        """Merge a processing outcome into the stored report result.

        Soft-merge skips ``None`` values so deferred success must explicitly
        clear sticky fields such as ``error="Extracted; ingest/process pending"``.
        """
        existing = self._results.get(result.slug)
        if existing is None:
            self._results[result.slug] = result
        elif existing.status in {"success", "failed"} and self._is_deferred_pending(result):
            # Do not downgrade a completed report with a late pending partial.
            return
        else:
            data = existing.model_dump()
            data.update({k: v for k, v in result.model_dump().items() if v is not None})
            if result.status in {"success", "partial_success", "failed"}:
                data["status"] = result.status
            # Terminal success/failed must clear stale pending error even when
            # the incoming result uses error=None (Pydantic default).
            if result.status in {"success", "failed"}:
                data["error"] = result.error
            self._results[result.slug] = ReportResult(**data)
        # Fire-and-forget progress persist (best-effort)
        try:
            loop = asyncio.get_running_loop()
            from app.automation.run_registry import persist_run_progress

            loop.create_task(
                persist_run_progress(self.run_id, self.get_results(), status="running")
            )
        except RuntimeError:
            pass

    def get_results(self) -> list[ReportResult]:
        return list(self._results.values())

    async def schedule_processing(
        self,
        slug: str,
        work: Callable[[], Awaitable[ReportResult]],
    ) -> ReportResult | None:
        """Queue ingest/process work with concurrency limit. Returns None if deferred."""
        if not self.defer_processing:
            async with self.process_semaphore:
                log_automation_event(
                    logger,
                    "report_processing_started",
                    slug=slug,
                    run_id=self.run_id,
                )
                t0 = datetime.now(UTC)
                result = await work()
                elapsed = (datetime.now(UTC) - t0).total_seconds()
                self.timing.record_report_span(slug, "processing", elapsed)
                log_automation_event(
                    logger,
                    "report_processing_completed",
                    slug=slug,
                    run_id=self.run_id,
                    duration_seconds=round(elapsed, 3),
                    status=result.status,
                )
                self.merge_result(result)
                return result

        async def _runner() -> None:
            async with self.process_semaphore:
                log_automation_event(
                    logger,
                    "report_processing_started",
                    slug=slug,
                    run_id=self.run_id,
                )
                t0 = datetime.now(UTC)
                try:
                    result = await work()
                    elapsed = (datetime.now(UTC) - t0).total_seconds()
                    self.timing.record_report_span(slug, "processing", elapsed)
                    log_automation_event(
                        logger,
                        "report_processing_completed",
                        slug=slug,
                        run_id=self.run_id,
                        duration_seconds=round(elapsed, 3),
                        status=result.status,
                    )
                    self.merge_result(result)
                except Exception as exc:
                    logger.exception("Deferred processing failed for %s", slug)
                    self.merge_result(
                        ReportResult(
                            slug=slug,
                            dataset_key=slug,
                            status="failed",
                            error=f"Processing failed: {exc}",
                        )
                    )

        task = asyncio.create_task(_runner(), name=f"process:{slug}")
        self._tasks.append(task)
        return None

    async def wait_all(self) -> None:
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    def artifact_url(self, slug: str, file_type: str) -> str | None:
        ids = self._artifact_ids.get(slug) or {}
        artifact_id = ids.get(file_type)
        if not artifact_id:
            return None
        if file_type == "pdf":
            return f"/api/v1/automation/artifacts/{artifact_id}/download"
        return f"/api/v1/automation/artifacts/{artifact_id}/download"

    def preview_url(self, slug: str) -> str | None:
        ids = self._artifact_ids.get(slug) or {}
        artifact_id = ids.get("pdf")
        if not artifact_id:
            return None
        return f"/api/v1/automation/artifacts/{artifact_id}/preview"

    def remember_artifact(self, slug: str, file_type: str, artifact_id: str) -> None:
        self._artifact_ids.setdefault(slug, {})[file_type] = artifact_id
        log_automation_event(
            logger,
            "artifact_registered",
            run_id=self.run_id,
            slug=slug,
            file_type=file_type,
            artifact_id=artifact_id,
        )

    async def checkpoint(self, label: str = "") -> None:
        """Honor pause/cancel between safe automation steps."""
        from app.automation.cancellation import (
            RunCancelledError,
            checkpoint as control_checkpoint,
            is_cancelled,
            is_pause_requested,
        )
        from app.automation.run_registry import set_run_status
        from app.infrastructure.database.session import SessionLocal

        if is_cancelled(self.run_id):
            raise RunCancelledError(self.run_id)
        if is_pause_requested(self.run_id):
            try:
                async with SessionLocal() as session:
                    await set_run_status(session, self.run_id, "paused")
            except Exception:
                pass
            await control_checkpoint(self.run_id, label=label)
            if is_cancelled(self.run_id):
                raise RunCancelledError(self.run_id)
            try:
                async with SessionLocal() as session:
                    await set_run_status(session, self.run_id, "running")
            except Exception:
                pass
        else:
            await control_checkpoint(self.run_id, label=label)
