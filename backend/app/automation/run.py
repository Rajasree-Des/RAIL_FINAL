"""CDP attach entrypoint: connect, discover tabs, run multi-report automation."""

from __future__ import annotations

import asyncio
import logging
from uuid import uuid4

from app.automation.browser import BrowserConnectionError, BrowserManager
from app.automation.cdp_session import (
    connection_error_code,
    ensure_live_mis_page,
    is_recoverable_connection_error,
    reconnect_browser_session,
)
from app.automation.cancellation import (
    RunCancelledError,
    clear_cancel,
    clear_pause,
    is_cancelled,
    is_pause_requested,
    wait_if_paused_async,
)
from app.automation.config import config
from app.automation.date_range import ReportDateRange
from app.automation.handlers import get_handler
from app.automation.report_keys import canonicalize_report_key
from app.automation.reports import catalog
from app.automation.run_context import RunContext, reset_run_context, set_run_context
from app.automation.run_registry import create_cdp_run, finalize_cdp_run
from app.automation.schemas import MultiReportResult, ReportResult
from app.automation.session import (
    MisSessionError,
    RailMadadTabNotFoundError,
    SessionManager,
    TabInfo,
)
from app.automation.timing import RunTiming
from app.automation.utils import log_automation_event
from app.infrastructure.database.models import AutomationRunModel
from app.infrastructure.database.session import SessionLocal

logger = logging.getLogger(__name__)


async def _execute_report_handler(
    *,
    run_id: str,
    slug: str,
    report,
    manager: BrowserManager,
    session: SessionManager,
    page,
    ctx: RunContext,
    timing: RunTiming,
):
    """Run one report handler with live-page checks, stage timeout, and one reconnect retry."""
    last_exc: Exception | None = None
    current_page = page
    for attempt in range(2):
        try:
            await ctx.checkpoint("before_handler_execute")
            current_page = await ensure_live_mis_page(
                run_id=run_id,
                report_slug=slug,
                manager=manager,
                session=session,
                page=current_page,
                prefer_url_fragment=report.url_fragment,
            )
            handler = get_handler(slug)
            handler.bind_browser(manager.browser)
            log_automation_event(
                logger,
                "exact_report_automation_started",
                run_id=run_id,
                report_slug=slug,
                stage="extraction",
                retry_count=attempt,
            )
            with timing.span(f"handler_execute:{slug}"):
                result = await asyncio.wait_for(
                    handler.execute(current_page, session, report),
                    timeout=float(config.timeout),
                )
            log_automation_event(
                logger,
                "extraction_completed",
                run_id=run_id,
                report_slug=slug,
                status=result.status,
            )
            return result, current_page
        except asyncio.TimeoutError as exc:
            last_exc = exc
            raise TimeoutError(
                f"Report {slug} extraction timed out after {config.timeout}s"
            ) from exc
        except MisSessionError:
            raise
        except Exception as exc:
            last_exc = exc
            if attempt == 0 and is_recoverable_connection_error(exc):
                log_automation_event(
                    logger,
                    "browser_connection_lost",
                    run_id=run_id,
                    report_slug=slug,
                    stage="handler_execute",
                    error=str(exc),
                    retry_count=attempt,
                )
                _browser, current_page = await reconnect_browser_session(
                    run_id=run_id,
                    report_slug=slug,
                    manager=manager,
                    session=session,
                )
                continue
            raise
    assert last_exc is not None
    raise last_exc


def _log_tab(tab: TabInfo) -> None:
    log_automation_event(
        logger,
        "tab_discovered",
        context_index=tab.context_index,
        tab_index=tab.tab_index,
        url=tab.url,
        title=tab.title,
        is_railmadad=tab.is_railmadad,
    )
    logger.info("%s", tab.format_line())


async def _emit_report_activity(
    user_id: str | None,
    *,
    run_id: str,
    slug: str,
    status: str,
    error: str | None = None,
) -> None:
    if not user_id:
        return
    try:
        from app.features.activity.emit import emit_activity

        # Non-terminal deferred processing must not emit REPORT_FAILED.
        if status == "partial_success" and error and "ingest/process pending" in error.lower():
            return

        if status == "success":
            await emit_activity(
                user_id=user_id,
                action="REPORT_COMPLETED",
                message=f"Report {slug} completed",
                status="success",
                report_slug=slug,
                run_id=run_id,
                dedupe_key=f"report_completed:{run_id}:{slug}",
            )
        elif status == "partial_success":
            await emit_activity(
                user_id=user_id,
                action="REPORT_PARTIAL",
                message=error or f"Report {slug} partial success",
                status="warning",
                report_slug=slug,
                run_id=run_id,
                dedupe_key=f"report_partial:{run_id}:{slug}",
            )
        elif status == "failed":
            await emit_activity(
                user_id=user_id,
                action="REPORT_FAILED",
                message=error or f"Report {slug} failed",
                status="error",
                report_slug=slug,
                run_id=run_id,
                dedupe_key=f"report_failed:{run_id}:{slug}",
            )
        # skipped/stopped: no per-report completed/failed activity here
    except Exception:
        pass


async def _finalize_failed_run(
    *,
    ctx: RunContext,
    run_id: str,
    user_id: str | None,
    result: MultiReportResult,
    session_lost: bool = False,
) -> MultiReportResult:
    """Persist run failure and emit activity (deduped via finalize_cdp_run)."""
    if session_lost and user_id:
        try:
            from app.features.activity.emit import emit_activity

            await emit_activity(
                user_id=user_id,
                action="SESSION_LOST",
                message=result.error or "MIS session lost",
                status="error",
                run_id=run_id,
                dedupe_key=f"session_lost:{run_id}",
            )
        except Exception:
            pass
    try:
        async with SessionLocal() as db:
            await finalize_cdp_run(db, run_id, result, user_id=user_id)
    except Exception:
        if user_id:
            try:
                from app.features.activity.emit import emit_activity

                await emit_activity(
                    user_id=user_id,
                    action="AUTOMATION_FAILED",
                    message=result.error or "Automation failed",
                    status="error",
                    run_id=run_id,
                    dedupe_key=f"automation_final:{run_id}",
                )
            except Exception:
                pass
    return result


async def _capture_failure_screenshot(
    session: SessionManager,
    tabs: list[TabInfo],
) -> str | None:
    page = session.first_available_page(tabs)
    if page is None:
        return None
    try:
        from pathlib import Path

        return await session.capture_screenshot(page, Path(config.screenshots_dir))
    except Exception as exc:
        logger.warning("Could not capture failure screenshot: %s", exc)
        return None


async def _register_missing_artifacts(ctx: RunContext, reports: list[ReportResult]) -> None:
    """Register excel/pdf for reports that processed inline (e.g. report1)."""
    from app.automation.run_registry import register_artifact

    try:
        async with SessionLocal() as session:
            for report in reports:
                ids = ctx._artifact_ids.get(report.slug) or {}
                if report.excel_path and "excel" not in ids:
                    art = await register_artifact(
                        session,
                        run_id=ctx.run_id,
                        report_slug=report.slug,
                        report_name=report.slug,
                        file_type="excel",
                        file_path=report.excel_path,
                    )
                    if art:
                        ctx.remember_artifact(report.slug, "excel", art.id)
                if report.pdf_path and "pdf" not in ids:
                    art = await register_artifact(
                        session,
                        run_id=ctx.run_id,
                        report_slug=report.slug,
                        report_name=report.slug,
                        file_type="pdf",
                        file_path=report.pdf_path,
                    )
                    if art:
                        ctx.remember_artifact(report.slug, "pdf", art.id)
    except Exception as exc:
        logger.warning("Artifact backfill failed: %s", exc)


def _finalize_multi_result(
    *,
    ctx: RunContext,
    connected: bool,
    report_results: list[ReportResult],
    success: bool | None = None,
    stopped_early: bool = False,
    stop_reason: str | None = None,
    error: str | None = None,
    error_code: str | None = None,
    session_valid: bool = True,
    tab_found: bool = True,
) -> MultiReportResult:
    # Prefer merged deferred results when present
    merged = {r.slug: r for r in report_results}
    for r in ctx.get_results():
        merged[r.slug] = r
    reports = list(merged.values())
    # Preserve catalog order
    order = [canonicalize_report_key(r.slug) for r in catalog.reports]
    reports.sort(
        key=lambda r: order.index(r.slug) if r.slug in order else 999
    )

    timing_payload = ctx.timing.finish()
    for report in reports:
        rt = ctx.timing.reports.get(report.slug)
        if rt:
            report.started_at = report.started_at or rt.started_at
            report.completed_at = report.completed_at or rt.completed_at
            report.duration_seconds = report.duration_seconds or rt.duration_seconds
            report.extraction_seconds = (
                report.extraction_seconds or rt.extraction_seconds
            )
            report.processing_seconds = (
                report.processing_seconds or rt.processing_seconds
            )
        if report.row_count is None:
            report.row_count = report.source_row_count
        ids = ctx._artifact_ids.get(report.slug) or {}
        if ids.get("pdf"):
            report.pdf_download_url = (
                f"/api/v1/automation/artifacts/{ids['pdf']}/download"
            )
            report.pdf_preview_url = (
                f"/api/v1/automation/artifacts/{ids['pdf']}/preview"
            )
        if ids.get("excel"):
            report.excel_download_url = (
                f"/api/v1/automation/artifacts/{ids['excel']}/download"
            )

    ok = all(r.status == "success" for r in reports) if success is None else success
    successful = sum(1 for r in reports if r.status == "success")
    failed = sum(1 for r in reports if r.status in {"failed", "partial_success"})
    return MultiReportResult(
        success=ok and not stopped_early,
        connected=connected,
        tab_found=tab_found,
        reports=reports,
        stopped_early=stopped_early,
        stop_reason=stop_reason,
        error=error,
        error_code=error_code,
        session_valid=session_valid,
        run_id=ctx.run_id,
        total_duration_seconds=timing_payload.get("total_duration_seconds"),
        reports_successful=successful,
        reports_failed=failed,
        download_pdf_all_url=f"/api/v1/automation/runs/{ctx.run_id}/download/pdf/all",
        download_excel_all_url=f"/api/v1/automation/runs/{ctx.run_id}/download/excel/all",
    )


async def attach_to_railmadad(
    *,
    report_slugs: list[str] | None = None,
    user_id: str | None = None,
    run_id: str | None = None,
    manual_config: dict | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> MultiReportResult:
    """Connect to Chrome over CDP and execute catalog reports sequentially."""
    manager = BrowserManager(cdp_url=config.chrome_debug_url)
    session = SessionManager(railmadad_url=config.railmadad_url)
    tabs: list[TabInfo] = []
    connected = False
    report_results: list[ReportResult] = []

    resolved_run_id = run_id or str(uuid4())
    try:
        async with SessionLocal() as db:
            if run_id:
                existing = await db.get(AutomationRunModel, run_id)
                if existing is None:
                    run = await create_cdp_run(db, user_id=user_id, run_id=run_id)
                    resolved_run_id = run.id
                else:
                    resolved_run_id = existing.id
            else:
                run = await create_cdp_run(db, user_id=user_id)
                resolved_run_id = run.id
    except Exception as exc:
        logger.warning("Could not persist CDP run row: %s", exc)

    timing = RunTiming(run_id=resolved_run_id)
    if date_from and date_to:
        date_range = ReportDateRange.from_iso(date_from, date_to)
        resolution_source = "frontend"
    elif manual_config:
        date_range = ReportDateRange.from_snapshot(manual_config)
        resolution_source = "manual_config"
    else:
        date_range = ReportDateRange.default_global_range()
        resolution_source = "backend_default"
    frozen_from_date = date_range.iso_from()
    ctx = RunContext(
        run_id=resolved_run_id,
        timing=timing,
        user_id=user_id,
        defer_processing=True,
        skip_portal_archive=True,
        manual_config=manual_config,
        phase1_from_date=frozen_from_date,
        date_range=date_range,
    )
    log_automation_event(
        logger,
        "phase1_from_date_frozen",
        run_id=resolved_run_id,
        expected_from_date=frozen_from_date,
        expected_to_date=date_range.iso_to(),
        resolution_source=resolution_source,
    )
    token = set_run_context(ctx)
    run_id = resolved_run_id

    if user_id:
        try:
            from app.features.activity.emit import emit_activity

            await emit_activity(
                user_id=user_id,
                action="AUTOMATION_STARTED",
                message="Automation run started",
                status="info",
                run_id=run_id,
                dedupe_key=f"automation_started:{run_id}",
            )
        except Exception:
            pass

    try:
        with timing.span("browser_connect"):
            log_automation_event(
                logger,
                "cdp_connect_attempt",
                cdp_url=config.chrome_debug_url,
                run_id=run_id,
            )
            browser = await manager.connect()
            connected = True
            log_automation_event(
                logger,
                "cdp_connected",
                cdp_url=config.chrome_debug_url,
                context_count=len(browser.contexts),
                run_id=run_id,
            )

        tabs = await session.discover_tabs(browser)
        for tab in tabs:
            _log_tab(tab)

        page = await ensure_live_mis_page(
            run_id=run_id,
            report_slug=report_slugs[0] if report_slugs else catalog.first_report().slug,
            manager=manager,
            session=session,
            page=None,
            prefer_url_fragment=catalog.first_report().url_fragment,
        )
        log_automation_event(
            logger,
            "railmadad_tab_activated",
            url=page.url,
            run_id=run_id,
        )
        logger.info("RailMadad MIS tab activated: %s", page.url)

        if await session.is_login_page(page):
            result = MultiReportResult(
                success=False,
                connected=True,
                tab_found=True,
                error="Please log in to RailMadad before generating reports.",
                error_code="RAILMADAD_NOT_LOGGED_IN",
                run_id=run_id,
            )
            return await _finalize_failed_run(
                ctx=ctx, run_id=run_id, user_id=user_id, result=result
            )

        log_automation_event(logger, "phase9_validation_started", run_id=run_id)

        selected = catalog.reports
        if report_slugs:
            wanted = {canonicalize_report_key(s) for s in report_slugs}
            selected = [r for r in catalog.reports if canonicalize_report_key(r.slug) in wanted]

        for report in selected:
            if is_cancelled(run_id):
                remaining = selected[selected.index(report) :]
                for pending in remaining:
                    pending_slug = canonicalize_report_key(pending.slug)
                    skipped = ReportResult(
                        slug=pending_slug,
                        dataset_key=pending_slug,
                        status="skipped",
                        error="Cancelled by user",
                    )
                    report_results.append(skipped)
                    ctx.store_partial(skipped)
                await ctx.wait_all()
                for r in ctx.get_results():
                    found = False
                    for i, existing in enumerate(report_results):
                        if existing.slug == r.slug:
                            if existing.status != "skipped":
                                report_results[i] = r
                            found = True
                            break
                    if not found:
                        report_results.append(r)
                result = _finalize_multi_result(
                    ctx=ctx,
                    connected=True,
                    report_results=report_results,
                    success=False,
                    stopped_early=True,
                    stop_reason="USER_CANCELLED",
                    error="Report generation stopped by user",
                    error_code="USER_CANCELLED",
                    session_valid=True,
                )
                try:
                    async with SessionLocal() as db:
                        await finalize_cdp_run(db, run_id, result, user_id=user_id)
                except Exception as exc:
                    logger.warning("Could not finalize cancelled CDP run: %s", exc)
                clear_cancel(run_id)
                clear_pause(run_id)
                return result

            if is_pause_requested(run_id):
                try:
                    async with SessionLocal() as db:
                        from app.automation.run_registry import set_run_status

                        await set_run_status(
                            db,
                            run_id,
                            "paused",
                            user_id=user_id,
                            activity_action="AUTOMATION_PAUSED",
                            activity_message="Report generation paused",
                        )
                except Exception:
                    pass
                if user_id:
                    try:
                        from app.features.activity.emit import emit_activity

                        await emit_activity(
                            user_id=user_id,
                            action="AUTOMATION_PAUSED",
                            message="Report generation paused",
                            status="warning",
                            run_id=run_id,
                            dedupe_key=f"automation_paused:{run_id}",
                        )
                    except Exception:
                        pass
                await wait_if_paused_async(run_id)
                if is_cancelled(run_id):
                    continue
                try:
                    async with SessionLocal() as db:
                        from app.automation.run_registry import set_run_status

                        await set_run_status(
                            db,
                            run_id,
                            "running",
                            user_id=user_id,
                        )
                except Exception:
                    pass

            slug = canonicalize_report_key(report.slug)
            ctx.timing.start_report(slug)
            if user_id:
                try:
                    from app.features.activity.emit import emit_activity

                    await emit_activity(
                        user_id=user_id,
                        action="REPORT_STARTED",
                        message=f"Report {slug} started",
                        status="info",
                        report_slug=slug,
                        run_id=run_id,
                        dedupe_key=f"report_started:{run_id}:{slug}",
                    )
                except Exception:
                    pass

            try:
                if is_cancelled(run_id):
                    continue
                result, page = await _execute_report_handler(
                    run_id=run_id,
                    slug=slug,
                    report=report,
                    manager=manager,
                    session=session,
                    page=page,
                    ctx=ctx,
                    timing=timing,
                )
                report_results.append(result)
                ctx.store_partial(result)

                page = await ensure_live_mis_page(
                    run_id=run_id,
                    report_slug=slug,
                    manager=manager,
                    session=session,
                    page=page,
                )
                ctx.timing.end_report(slug, status=result.status, error=result.error)
                await _emit_report_activity(
                    user_id,
                    run_id=run_id,
                    slug=slug,
                    status=result.status,
                    error=result.error,
                )

            except RunCancelledError:
                skipped = ReportResult(
                    slug=slug,
                    dataset_key=slug,
                    status="skipped",
                    error="Cancelled by user",
                )
                report_results.append(skipped)
                ctx.store_partial(skipped)
                ctx.timing.end_report(slug, status="skipped", error="cancelled")
                # Fall through to top-of-loop cancel handling on next iteration
                continue

            except MisSessionError as exc:
                failed_result = ReportResult(
                    slug=slug,
                    dataset_key=slug,
                    status="failed",
                    error=exc.status.error,
                )
                report_results.append(failed_result)
                ctx.timing.end_report(slug, status="failed", error="auth_lost")
                await _emit_report_activity(
                    user_id,
                    run_id=run_id,
                    slug=slug,
                    status="failed",
                    error=exc.status.error,
                )
                if user_id:
                    try:
                        from app.features.activity.emit import emit_activity

                        await emit_activity(
                            user_id=user_id,
                            action="SESSION_LOST",
                            message=exc.status.error or "MIS session lost",
                            status="error",
                            run_id=run_id,
                            dedupe_key=f"session_lost:{run_id}:{slug}",
                        )
                    except Exception:
                        pass
                await ctx.wait_all()
                result = _finalize_multi_result(
                    ctx=ctx,
                    connected=True,
                    report_results=report_results,
                    success=False,
                    stopped_early=True,
                    stop_reason=exc.status.error_code or "MIS_SESSION_LOST",
                    error=exc.status.error,
                    error_code=exc.status.error_code,
                    session_valid=False,
                )
                try:
                    async with SessionLocal() as db:
                        await finalize_cdp_run(db, run_id, result, user_id=user_id)
                except Exception:
                    pass
                return result

            except Exception as exc:
                logger.exception("Report %s failed", slug)

                error_code = (
                    connection_error_code(exc)
                    if is_recoverable_connection_error(exc)
                    else None
                )
                log_automation_event(
                    logger,
                    "handler_failed",
                    run_id=run_id,
                    report_slug=slug,
                    error=str(exc),
                    error_code=error_code,
                    connection_closed=is_recoverable_connection_error(exc),
                )
                report_results.append(
                    ReportResult(
                        slug=slug,
                        dataset_key=slug,
                        status="failed",
                        error=str(exc),
                        error_code=error_code,
                    )
                )
                ctx.timing.end_report(slug, status="failed", error=str(exc))
                await _emit_report_activity(
                    user_id,
                    run_id=run_id,
                    slug=slug,
                    status="failed",
                    error=str(exc),
                )
                try:
                    page = await ensure_live_mis_page(
                        run_id=run_id,
                        report_slug=slug,
                        manager=manager,
                        session=session,
                        page=page,
                    )
                except MisSessionError as auth_exc:
                    await ctx.wait_all()
                    result = _finalize_multi_result(
                        ctx=ctx,
                        connected=True,
                        report_results=report_results,
                        success=False,
                        stopped_early=True,
                        stop_reason=auth_exc.status.error_code or "MIS_SESSION_LOST",
                        error=auth_exc.status.error,
                        error_code=auth_exc.status.error_code,
                        session_valid=False,
                    )
                    return await _finalize_failed_run(
                        ctx=ctx,
                        run_id=run_id,
                        user_id=user_id,
                        result=result,
                        session_lost=True,
                    )

        await manager.close()
        log_automation_event(
            logger,
            "cdp_disconnected",
            run_id=run_id,
            stage="post_extraction",
        )

        await ctx.wait_all()
        log_automation_event(logger, "processing_completed", run_id=run_id)
        # Merge deferred results before artifact backfill
        for r in ctx.get_results():
            found = False
            for i, existing in enumerate(report_results):
                if existing.slug == r.slug:
                    report_results[i] = r
                    found = True
                    break
            if not found:
                report_results.append(r)
        await _register_missing_artifacts(ctx, report_results)
        # Emit terminal activity from merged results (handler emit skipped pending).
        for r in report_results:
            await _emit_report_activity(
                user_id,
                run_id=run_id,
                slug=r.slug,
                status=r.status,
                error=r.error,
            )
        result = _finalize_multi_result(
            ctx=ctx,
            connected=True,
            report_results=report_results,
            session_valid=True,
        )
        try:
            async with SessionLocal() as db:
                await finalize_cdp_run(db, run_id, result, user_id=user_id)
        except Exception as exc:
            logger.warning("Could not finalize CDP run row: %s", exc)
        log_automation_event(
            logger,
            "report_terminal_status",
            run_id=run_id,
            run_status="completed" if result.success else "failed",
            reports_successful=result.reports_successful,
            reports_failed=result.reports_failed,
        )
        return result

    except MisSessionError as exc:
        logger.error("MIS session lost or invalid", exc_info=True)
        await _capture_failure_screenshot(session, tabs)
        await ctx.wait_all()
        result = _finalize_multi_result(
            ctx=ctx,
            connected=connected,
            report_results=report_results,
            success=False,
            stopped_early=True,
            stop_reason=exc.status.error_code or "MIS_SESSION_LOST",
            error=exc.status.error,
            error_code=exc.status.error_code,
            session_valid=False,
        )
        return await _finalize_failed_run(
            ctx=ctx,
            run_id=run_id,
            user_id=user_id,
            result=result,
            session_lost=True,
        )

    except BrowserConnectionError as exc:
        logger.error(
            "CDP connection failed at %s",
            config.chrome_debug_url,
            exc_info=True,
        )
        result = MultiReportResult(
            success=False,
            connected=False,
            tab_found=False,
            error=exc.message,
            run_id=run_id,
        )
        return await _finalize_failed_run(
            ctx=ctx, run_id=run_id, user_id=user_id, result=result
        )

    except RailMadadTabNotFoundError as exc:
        screenshot_path = await _capture_failure_screenshot(session, tabs)
        log_automation_event(
            logger,
            "attach_failed",
            error=str(exc),
            screenshot_path=screenshot_path,
        )
        result = MultiReportResult(
            success=False,
            connected=connected,
            tab_found=False,
            error=str(exc),
            run_id=run_id,
        )
        return await _finalize_failed_run(
            ctx=ctx, run_id=run_id, user_id=user_id, result=result
        )

    except Exception as exc:
        logger.exception("Automation attach run failed")
        screenshot_path = await _capture_failure_screenshot(session, tabs)
        log_automation_event(
            logger,
            "attach_failed",
            error=str(exc),
            screenshot_path=screenshot_path,
        )
        tab_found = connected and any(tab.is_railmadad for tab in tabs)
        await ctx.wait_all()
        result = _finalize_multi_result(
            ctx=ctx,
            connected=connected,
            report_results=report_results,
            success=False,
            error=str(exc),
            tab_found=tab_found,
        )
        return await _finalize_failed_run(
            ctx=ctx, run_id=run_id, user_id=user_id, result=result
        )

    finally:
        reset_run_context(token)
        log_automation_event(
            logger,
            "cdp_disconnect_start",
            browser_connected=manager.browser is not None,
            cdp_url=config.chrome_debug_url,
            run_id=run_id,
        )
        await manager.close()
        log_automation_event(logger, "cdp_disconnected", run_id=run_id)


async def run() -> bool:
    """CLI/debug entrypoint — returns True when attach succeeded."""
    result = await attach_to_railmadad()
    return result.success


async def main() -> None:
    success = await run()
    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
