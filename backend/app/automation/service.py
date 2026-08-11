"""In-process browser automation service."""

import asyncio
import logging
import sys
import threading
from uuid import uuid4

from app.automation.automation_lock import (
    automation_lock_status,
    release_automation_lock,
    try_acquire_automation_lock,
)
from app.automation.cancellation import (
    clear_cancel,
    clear_pause,
    request_cancel,
    request_pause,
)
from app.automation.run import attach_to_railmadad
from app.automation.run_registry import create_cdp_run, finalize_cdp_run, mark_run_stopped, set_run_status
from app.automation.schemas import MultiReportResult
from app.infrastructure.database.models import AutomationRunModel
from app.infrastructure.database.session import SessionLocal

logger = logging.getLogger(__name__)


def _lock_report_slug(
    report_slugs: list[str] | None,
    manual_config: dict | None = None,
) -> str:
    if manual_config and manual_config.get("report_slug"):
        return str(manual_config["report_slug"])
    if report_slugs:
        return report_slugs[0]
    return "catalog"


class AutomationLockBusyError(Exception):
    """Raised when another CDP automation run already holds the browser lock."""

    def __init__(self, *, active_run_id: str | None, active_report_slug: str | None) -> None:
        self.active_run_id = active_run_id
        self.active_report_slug = active_report_slug
        super().__init__(
            f"Automation already running"
            + (f" ({active_report_slug}, run_id={active_run_id})" if active_run_id else "")
        )


async def _finalize_orphan_run(run_id: str, *, user_id: str | None, message: str) -> None:
    """Mark a background worker run failed when the thread exits unexpectedly."""
    error_code = (
        "AUTOMATION_ALREADY_RUNNING"
        if "already running" in message.lower()
        else "AUTOMATION_WORKER_FAILED"
    )
    result = MultiReportResult(
        success=False,
        connected=False,
        tab_found=False,
        error=message,
        error_code=error_code,
        run_id=run_id,
    )
    try:
        async with SessionLocal() as db:
            run = await db.get(AutomationRunModel, run_id)
            if run is None or run.status in {"completed", "failed", "stopped"}:
                return
            await finalize_cdp_run(db, run_id, result, user_id=user_id)
    except Exception:
        logger.exception("Could not finalize orphan automation run %s", run_id)


def _run_attach_in_thread(
    user_id: str | None = None,
    report_slugs: list[str] | None = None,
    run_id: str | None = None,
    manual_config: dict | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> MultiReportResult:
    """Run Playwright in a dedicated loop (required on Windows + Uvicorn)."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    async def _attach_with_loop_local_db() -> MultiReportResult:
        from app.infrastructure.database.session import dispose_current_loop_engine

        try:
            return await attach_to_railmadad(
                user_id=user_id,
                report_slugs=report_slugs,
                run_id=run_id,
                manual_config=manual_config,
                date_from=date_from,
                date_to=date_to,
            )
        finally:
            await dispose_current_loop_engine()

    return asyncio.run(_attach_with_loop_local_db())


class AutomationService:
    """Single entry point for in-process Playwright automation."""

    async def start(
        self,
        user_id: str | None = None,
        report_slugs: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> MultiReportResult:
        """Connect to Chrome via CDP and run catalog reports (blocking until done)."""
        run_id = str(uuid4())
        report_slug = _lock_report_slug(report_slugs)
        if not try_acquire_automation_lock(run_id, report_slug):
            status = automation_lock_status()
            raise AutomationLockBusyError(
                active_run_id=status.run_id,
                active_report_slug=status.report_slug,
            )
        try:
            return await asyncio.to_thread(
                _run_attach_in_thread,
                user_id,
                report_slugs,
                run_id,
                None,
                date_from,
                date_to,
            )
        finally:
            release_automation_lock(run_id)

    async def start_async(
        self,
        user_id: str | None = None,
        report_slugs: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> tuple[str, str]:
        """Create a run row and start CDP work in a background thread.

        Returns (run_id, status) immediately so the UI can poll GET /runs/{id}.
        """
        async with SessionLocal() as db:
            run = await create_cdp_run(
                db,
                user_id=user_id,
                date_from=date_from,
                date_to=date_to,
            )
            run_id = run.id

        clear_cancel(run_id)
        clear_pause(run_id)
        report_slug = _lock_report_slug(report_slugs)
        if not try_acquire_automation_lock(run_id, report_slug):
            status = automation_lock_status()
            await _finalize_orphan_run(
                run_id,
                user_id=user_id,
                message=(
                    f"Automation already running for {status.report_slug or 'unknown report'}"
                ),
            )
            raise AutomationLockBusyError(
                active_run_id=status.run_id,
                active_report_slug=status.report_slug,
            )

        def _worker() -> None:
            try:
                _run_attach_in_thread(
                    user_id,
                    report_slugs,
                    run_id,
                    None,
                    date_from,
                    date_to,
                )
            except Exception as exc:
                logger.exception("Background automation failed for run %s", run_id)
                asyncio.run(
                    _finalize_orphan_run(
                        run_id,
                        user_id=user_id,
                        message=str(exc) or "Background automation failed",
                    )
                )
            finally:
                release_automation_lock(run_id)
                clear_cancel(run_id)
                clear_pause(run_id)

        thread = threading.Thread(
            target=_worker,
            name=f"automation-{run_id[:8]}",
            daemon=True,
        )
        thread.start()
        return run_id, "running"

    async def start_manual_async(
        self,
        user_id: str | None = None,
        report_slugs: list[str] | None = None,
        manual_config: dict | None = None,
    ) -> tuple[str, str]:
        """Create a manual-report run and start single-report CDP automation."""
        from app.features.reports.service import MANUAL_TRIGGER

        async with SessionLocal() as db:
            run = await create_cdp_run(
                db,
                user_id=user_id,
                trigger_type=MANUAL_TRIGGER,
                manual_config=manual_config,
            )
            run_id = run.id

        report_slug = _lock_report_slug(report_slugs, manual_config)

        if not try_acquire_automation_lock(run_id, report_slug):
            status = automation_lock_status()
            await _finalize_orphan_run(
                run_id,
                user_id=user_id,
                message=(
                    f"Automation already running for {status.report_slug or 'unknown report'}"
                ),
            )
            raise AutomationLockBusyError(
                active_run_id=status.run_id,
                active_report_slug=status.report_slug,
            )

        logger.info(
            "manual_generation_requested run_id=%s report_slug=%s",
            run_id,
            report_slug,
        )
        clear_cancel(run_id)
        clear_pause(run_id)

        def _worker() -> None:
            try:
                _run_attach_in_thread(user_id, report_slugs, run_id, manual_config)
            except Exception as exc:
                logger.exception("Background manual report failed for run %s", run_id)
                asyncio.run(
                    _finalize_orphan_run(
                        run_id,
                        user_id=user_id,
                        message=str(exc) or "Background manual report failed",
                    )
                )
            finally:
                release_automation_lock(run_id)
                logger.info(
                    "automation_lock_released run_id=%s report_slug=%s",
                    run_id,
                    report_slug,
                )
                clear_cancel(run_id)
                clear_pause(run_id)

        thread = threading.Thread(
            target=_worker,
            name=f"manual-report-{run_id[:8]}",
            daemon=True,
        )
        thread.start()
        return run_id, "running"

    async def stop(
        self,
        run_id: str,
        *,
        user_id: str | None = None,
    ) -> dict[str, str | bool]:
        """Request cooperative cancel and mark the CDP run stopped."""
        async with SessionLocal() as db:
            run = await db.get(AutomationRunModel, run_id)
            if not run:
                return {
                    "success": False,
                    "status": "not_found",
                    "message": "Run not found",
                    "run_id": run_id,
                }
            if run.status in {"completed", "failed", "stopped"}:
                return {
                    "success": True,
                    "status": run.status,
                    "message": f"Run already {run.status}",
                    "run_id": run_id,
                }

            request_cancel(run_id)
            clear_pause(run_id)
            await mark_run_stopped(
                db, run_id, user_id=user_id, intermediate=True
            )
            # Immediately surface terminal stopped for UI; worker finalizes details.
            await mark_run_stopped(db, run_id, user_id=user_id, intermediate=False)
            logger.info("cdp_run_stop_requested run_id=%s", run_id)
            return {
                "success": True,
                "status": "stopped",
                "message": "Automation stopped",
                "run_id": run_id,
            }

    async def pause(
        self,
        run_id: str,
        *,
        user_id: str | None = None,
    ) -> dict[str, str | bool]:
        async with SessionLocal() as db:
            run = await db.get(AutomationRunModel, run_id)
            if not run:
                return {
                    "success": False,
                    "status": "not_found",
                    "message": "Run not found",
                    "run_id": run_id,
                }
            if run.status in {"completed", "failed", "stopped"}:
                return {
                    "success": False,
                    "status": run.status,
                    "message": f"Run already {run.status}",
                    "run_id": run_id,
                }
            if run.status == "paused":
                return {
                    "success": True,
                    "status": "paused",
                    "message": "Run already paused",
                    "run_id": run_id,
                }

            request_pause(run_id)
            await set_run_status(
                db,
                run_id,
                "pause_requested",
                user_id=user_id,
                activity_action="AUTOMATION_PAUSE_REQUESTED",
                activity_message="Report generation pause requested",
            )
            logger.info("cdp_run_pause_requested run_id=%s", run_id)
            return {
                "success": True,
                "status": "pause_requested",
                "message": "Pause requested",
                "run_id": run_id,
            }

    async def resume(
        self,
        run_id: str,
        *,
        user_id: str | None = None,
    ) -> dict[str, str | bool]:
        async with SessionLocal() as db:
            run = await db.get(AutomationRunModel, run_id)
            if not run:
                return {
                    "success": False,
                    "status": "not_found",
                    "message": "Run not found",
                    "run_id": run_id,
                }
            if run.status not in {"paused", "pause_requested", "running"}:
                return {
                    "success": False,
                    "status": run.status,
                    "message": f"Cannot resume from {run.status}",
                    "run_id": run_id,
                }

            clear_pause(run_id)
            await set_run_status(
                db,
                run_id,
                "running",
                user_id=user_id,
                activity_action="AUTOMATION_RESUMED",
                activity_message="Report generation resumed",
            )
            logger.info("cdp_run_resumed run_id=%s", run_id)
            return {
                "success": True,
                "status": "running",
                "message": "Automation resumed",
                "run_id": run_id,
            }
