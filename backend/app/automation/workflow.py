"""Shared workflow helpers for multi-report automation."""

from __future__ import annotations

import logging
from pathlib import Path

from app.automation.config import config
from app.automation.filters import FilterDiscoveryService, FilterError, FilterService
from app.automation.generator import ReportGenerationError, ReportGeneratorService
from app.automation.navigation import NavigationError, NavigationService
from app.automation.report1_filters import (
    applied_filter_records,
    build_filters_from_discovery,
)
from app.automation.reports import REPORT_1, REPORT_6_FEEDBACK
from app.automation.session import MisSessionError, SessionManager
from app.automation.table_extractor import (
    FEEDBACK_ZONE_REQUIRED_HEADERS,
    ExtractionResult,
    TableExtractor,
)
from app.automation.table_sort import ReceivedColumnService, ReceivedSortError
from app.automation.table_validator import (
    FEEDBACK_REQUIRED_HEADERS,
    validate_extracted_data,
)
from app.automation.utils import ensure_directory, log_automation_event
from app.automation.portal_from_date import (
    apply_previous_from_date,
    log_phase1_submit_clicked,
    log_phase2_submit_clicked,
)
from app.automation.report_keys import canonicalize_report_key
from app.automation.run_context import get_run_context

logger = logging.getLogger(__name__)

FEEDBACK_ZONE_FILENAME = "report1_feedback_zone_raw.csv"
FEEDBACK_DATASET_ID = "report1_feedback"


async def verify_mis_session_or_raise(
    session: SessionManager,
    page,
    context: str = "operation",
    browser=None,
) -> None:
    """Verify MIS session is valid; reacquire from other tabs when possible."""
    if browser is not None:
        await session.ensure_authenticated_mis_page(browser, page, prefer_url_fragment=None)
        log_automation_event(logger, "mis_session_verified", context=context)
        return

    status = await session.verify_mis_session(page)
    if not status.valid:
        # Last chance: if page looks public, still check URL patterns only
        log_automation_event(
            logger,
            "mis_session_lost",
            context=context,
            error_code=status.error_code,
            error=status.error,
        )
        raise MisSessionError(status)
    log_automation_event(logger, "mis_session_verified", context=context)


async def ingest_downloaded_file(
    file_path: Path,
    report_slug: str,
    source: str,
    *,
    expected_row_count: int | None = None,
) -> bool:
    """Ingest the downloaded CSV into the dataset system using canonical keys.

    Never ingests PDF. Verifies DB row_count matches CSV after commit.
    """
    import time

    try:
        from app.automation.report_keys import canonicalize_report_key
        from app.automation.run_context import get_run_context
        from app.features.datasets.service import DatasetService
        from app.infrastructure.database.session import SessionLocal

        canonical = canonicalize_report_key(report_slug)
        path = Path(file_path)
        if path.suffix.lower() == ".pdf":
            log_automation_event(
                logger,
                "ingestion_failed",
                file_path=str(path),
                report_slug=canonical,
                source=source,
                error="PDF cannot be ingested",
            )
            return False
        if not path.is_file():
            log_automation_event(
                logger,
                "ingestion_failed",
                file_path=str(path),
                report_slug=canonical,
                source=source,
                error="file not found",
            )
            return False

        resolved = str(path.resolve())
        ctx = get_run_context()
        if ctx is not None and ctx.already_ingested(canonical, resolved):
            log_automation_event(
                logger,
                "ingestion_skipped_duplicate",
                file_path=resolved,
                report_slug=canonical,
                source=source,
            )
            return True

        t0 = time.perf_counter()
        log_automation_event(
            logger,
            "ingestion_started",
            file_path=str(file_path),
            report_slug=canonical,
            source=source,
        )

        span_name = "ingestion_feedback" if "feedback" in source.lower() else "ingestion"
        meta = None

        async def _do_ingest() -> None:
            nonlocal meta
            async with SessionLocal() as db_session:
                service = DatasetService(db_session)
                await service.ensure_dataset_exists(canonical)
                meta = await service.ingest_file(
                    canonical,
                    file_path=path,
                    source_filename=path.name,
                )

        if ctx is not None:
            with ctx.timing.report_span(canonical, span_name):
                await _do_ingest()
            ctx.mark_ingested(canonical, resolved)
            if canonical in {"scr-train", "scr-station"}:
                ctx.current_run_sources[canonical] = resolved
                log_automation_event(
                    logger,
                    "current_run_dataset_ingested",
                    run_id=ctx.run_id,
                    report_slug=canonical,
                    source_path=resolved,
                    row_count=getattr(meta, "row_count", None) if meta else None,
                )
        else:
            await _do_ingest()

        duration_ms = int((time.perf_counter() - t0) * 1000)
        ingested_rows = getattr(meta, "row_count", None) if meta else None
        if (
            canonical == "scr-station"
            and expected_row_count is not None
            and ingested_rows is not None
            and ingested_rows != expected_row_count
        ):
            log_automation_event(
                logger,
                "ingestion_failed",
                file_path=str(file_path),
                report_slug=canonical,
                source=source,
                error=(
                    f"REPORT6_INGESTION_COUNT_MISMATCH: expected {expected_row_count}, "
                    f"ingested {ingested_rows}"
                ),
            )
            return False
        log_automation_event(
            logger,
            "ingestion_completed",
            file_path=str(file_path),
            report_slug=canonical,
            source=source,
            dataset_key=canonical,
            row_count=getattr(meta, "row_count", None) if meta else None,
            ingestion_duration_ms=duration_ms,
        )
        return True

    except Exception as exc:
        logger.error("Ingestion failed for %s: %s", file_path, exc, exc_info=True)
        log_automation_event(
            logger,
            "ingestion_failed",
            file_path=str(file_path),
            source=source,
            error=str(exc),
        )
        return False


async def save_failure_artifacts(
    page,
    session: SessionManager | None,
    *,
    phase: str,
    report_slug: str,
    html: str | None = None,
    error: str | None = None,
) -> str | None:
    """Save screenshot, HTML, and metadata on session/validation failure."""
    from datetime import UTC, datetime

    dest = ensure_directory(Path(config.screenshots_dir) / "phase9")
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    screenshot_path: str | None = None

    try:
        url = page.url if page is not None else None
    except Exception:
        url = None

    meta_lines = [
        f"phase={phase}",
        f"report_slug={report_slug}",
        f"url={url}",
        f"error={error}",
        f"timestamp={timestamp}",
    ]
    meta_path = dest / f"failure_{timestamp}_{report_slug}_{phase}.txt"
    try:
        meta_path.write_text("\n".join(meta_lines) + "\n", encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not write failure metadata: %s", exc)

    if html:
        html_path = dest / f"failure_{timestamp}_{report_slug}_{phase}.html"
        try:
            html_path.write_text(html, encoding="utf-8")
        except Exception as exc:
            logger.warning("Could not write failure HTML: %s", exc)

    if page is not None and session is not None:
        try:
            screenshot_path = await session.capture_screenshot(page, dest)
        except Exception as exc:
            logger.warning("Could not capture failure screenshot: %s", exc)

    log_automation_event(
        logger,
        "phase9_failure_artifacts_saved",
        phase=phase,
        report_slug=report_slug,
        url=url,
        error=error,
        screenshot_path=screenshot_path,
        meta_path=str(meta_path),
    )
    return screenshot_path


async def extract_with_retry(
    page,
    extractor: TableExtractor,
    report_root,
    report,
    navigation: NavigationService,
    filter_service: FilterService,
    discovery: FilterDiscoveryService,
    generator: ReportGeneratorService,
    session: SessionManager,
    max_retries: int = 1,
) -> tuple[ExtractionResult, bool, bool]:
    """Extract table with validation and one retry."""
    retry_attempted = False
    retry_succeeded = False
    result = ExtractionResult(success=False, error="No extraction attempted")

    for attempt in range(max_retries + 1):
        is_retry = attempt > 0

        if is_retry:
            retry_attempted = True
            log_automation_event(
                logger,
                "extraction_retry_started",
                attempt=attempt,
                report=report.slug,
            )
            await verify_mis_session_or_raise(session, page, "extraction_retry")
            await navigation.navigate_to_report(page, report)
            report_root = await filter_service.get_report_root(page)
            discovered_fields = await discovery.discover_fields(page)
            report_filters = build_filters_from_discovery(discovered_fields, report.slug)
            applied_values = await filter_service.apply_filters(
                report_root, report_filters, page=page
            )
            await filter_service.validate_mandatory(report_root, report_filters, applied_values)
            slug_key = canonicalize_report_key(report.slug)
            if slug_key in {"report1", "division"}:
                ctx_retry = get_run_context()
                run_id = ctx_retry.run_id if ctx_retry is not None else ""
                await apply_previous_from_date(
                    page,
                    run_id,
                    report.slug,
                    "comprehensive_retry",
                    filter_service=filter_service,
                )
                log_phase1_submit_clicked(
                    run_id,
                    report.slug,
                    "comprehensive_retry",
                )
            elif slug_key == "train-no":
                ctx_retry = get_run_context()
                run_id = ctx_retry.run_id if ctx_retry is not None else ""
                await apply_previous_from_date(
                    page,
                    run_id,
                    report.slug,
                    "train_no_wise_retry",
                    filter_service=filter_service,
                )
                log_phase2_submit_clicked(
                    run_id,
                    report.slug,
                    "train_no_wise_retry",
                )
            await generator.generate_report(report_root, page)

            if not await generator.verify_report_displayed(report_root):
                log_automation_event(
                    logger,
                    "extraction_retry_failed",
                    attempt=attempt,
                    reason="report_not_displayed",
                )
                continue

            await ReceivedColumnService().sort_received_descending(report_root, page)

        result = await extractor.extract_and_save(report_root, report.slug)

        if result.success:
            if is_retry:
                retry_succeeded = True
                log_automation_event(
                    logger,
                    "extraction_retry_succeeded",
                    attempt=attempt,
                    row_count=result.row_count,
                )
            return result, retry_attempted, retry_succeeded

        if result.validation_result and not result.validation_result.valid:
            log_automation_event(
                logger,
                "table_validation_failed",
                attempt=attempt,
                error=result.validation_result.error,
                issues=result.validation_result.detected_issues,
            )
            await save_failure_artifacts(
                page,
                session,
                phase="comprehensive_validation",
                report_slug=report.slug,
                html=result.html,
                error=result.validation_result.error,
            )

        if attempt < max_retries:
            log_automation_event(
                logger,
                "extraction_will_retry",
                attempt=attempt,
                error=result.error,
            )

    if retry_attempted:
        log_automation_event(
            logger,
            "extraction_retry_failed",
            final_error=result.error,
        )

    return result, retry_attempted, retry_succeeded


async def _apply_feedback_filters_fast(report_root) -> dict[str, str]:
    """Apply Feedback filters using fast JavaScript batch operation."""
    js_code = """() => {
        const results = {};
        const selectByLabel = (sel, targetLabels) => {
            const el = document.querySelector(sel);
            if (!el || el.tagName !== 'SELECT') return null;
            const labels = Array.isArray(targetLabels) ? targetLabels : [targetLabels];
            
            // Priority 1: Exact match (case-insensitive)
            for (const label of labels) {
                const labelLower = label.toLowerCase().trim();
                for (let i = 0; i < el.options.length; i++) {
                    const optText = (el.options[i].text || '').trim();
                    if (optText.toLowerCase() === labelLower) {
                        el.selectedIndex = i;
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        return optText;
                    }
                }
            }
            
            // Priority 2: Option text includes target label (NOT vice versa)
            for (const label of labels) {
                const labelLower = label.toLowerCase().trim();
                for (let i = 0; i < el.options.length; i++) {
                    const optText = (el.options[i].text || '').trim();
                    if (optText.toLowerCase().includes(labelLower)) {
                        el.selectedIndex = i;
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        return optText;
                    }
                }
            }
            
            return el.options[el.selectedIndex]?.text || '';
        };

        results.zone = selectByLabel('#complaintZoneInput, select[name*="Zone"]', ['ALL', 'All']);
        results.division = selectByLabel('#complaintDivInput, select[name*="Division"]', ['ALL', 'All']);
        results.department = selectByLabel('#complaintDeptInput, select[name*="Dept"]', ['ALL', 'All']);
        results.mode = selectByLabel('#complaintModeInput, select[name*="Mode"]', ['ALL', 'All']);
        results.type = selectByLabel('#complaintTypeInput, select[name*="Type"]', ['ALL', 'All']);
        results.sub_type = selectByLabel('#complaintSubTypeInput, select[name*="SubType"]', ['ALL', 'All']);
        results.view = selectByLabel('#viewType, select[name*="View"]', ['Zone Wise / Dept. Wise', 'Zone Wise', 'ZoneWise']);
        results.excluding_assistance_cases = selectByLabel('#assistanceInput, select[name*="assistance"]', ['Yes', 'YES']);
        results.excluding_refund_cases = selectByLabel('#refundInput, select[name*="refund"]', ['YES', 'Yes']);
        results.excluding_inquiry_cases = selectByLabel('#inquiryInput, select[name*="inquiry"]', ['Yes', 'YES']);
        results.date_range = selectByLabel('#dateRange, select[name*="dateRange"], select[id*="dateRange"]', ['Previous Day', 'Previous day']);

        return results;
    }"""

    applied_values = await report_root.evaluate(js_code)
    return applied_values


async def attempt_feedback_extract(
    page,
    extractor: TableExtractor,
    navigation: NavigationService,
    filter_service: FilterService,
    discovery_service: FilterDiscoveryService,
    generator: ReportGeneratorService,
) -> ExtractionResult:
    """Single Feedback Tab 6 pass: filters → Previous Day → Submit → sort → validate → save."""
    from app.automation.report1_filters import REPORT_6_FILTERS

    log_automation_event(logger, "feedback_extraction_started")

    await navigation.navigate_to_report(page, REPORT_6_FEEDBACK)

    report_root = await filter_service.get_report_root(page)

    applied_values = await filter_service.apply_filters(
        report_root,
        REPORT_6_FILTERS,
        page=page,
    )
    await filter_service.validate_mandatory(
        report_root,
        REPORT_6_FILTERS,
        applied_values,
    )

    date_applied = applied_values.get("dateRange") or ""
    for name, value in applied_values.items():
        if "date" in name.lower() and "range" in name.lower():
            date_applied = value
            break
    if date_applied and "previous day" not in str(date_applied).lower():
        return ExtractionResult(
            success=False,
            error=f"Feedback Date Range must be Previous Day before Submit, got: {date_applied}",
        )

    log_automation_event(
        logger,
        "feedback_filters_applied",
        applied_values=applied_values,
    )

    ctx = get_run_context()
    run_id = ctx.run_id if ctx is not None else ""
    await apply_previous_from_date(
        page,
        run_id,
        "report1",
        "feedback",
        filter_service=filter_service,
    )
    log_phase1_submit_clicked(run_id, "report1", "feedback")

    await generator.generate_report(report_root, page)
    if not await generator.verify_report_displayed(report_root):
        return ExtractionResult(
            success=False,
            error="Feedback report did not display after generate",
        )

    await ReceivedColumnService().sort_feedback_received_descending(report_root, page)

    data = await extractor.extract_table_data_by_headers(
        report_root,
        FEEDBACK_ZONE_REQUIRED_HEADERS,
    )
    if not data:
        return ExtractionResult(
            success=False,
            error="Feedback Zone Wise table not found",
        )

    html = await extractor.extract_table_html(report_root)
    validation = validate_extracted_data(data, FEEDBACK_REQUIRED_HEADERS)
    if not validation.valid:
        log_automation_event(
            logger,
            "table_validation_failed",
            report="report6",
            error=validation.error,
            issues=validation.detected_issues,
        )
        return ExtractionResult(
            success=False,
            html=html,
            data=data,
            row_count=len(data),
            column_count=len(data[0]) if data else 0,
            error=validation.error,
            validation_result=validation,
        )

    csv_path = await extractor.save_as_csv_fixed(
        data,
        report_slug="report1",
        filename=FEEDBACK_ZONE_FILENAME,
    )
    if csv_path is None:
        return ExtractionResult(
            success=False,
            html=html,
            data=data,
            validation_result=validation,
            error="Failed to save Feedback Zone Wise CSV",
        )

    log_automation_event(
        logger,
        "feedback_extraction_complete",
        csv_path=str(csv_path),
        row_count=len(data),
    )
    return ExtractionResult(
        success=True,
        html=html,
        data=data,
        csv_path=csv_path,
        row_count=len(data),
        column_count=len(data[0]) if data else 0,
        validation_result=validation,
    )


async def extract_feedback_zone_csv(
    page,
    extractor: TableExtractor,
    navigation: NavigationService,
    filter_service: FilterService,
    discovery_service: FilterDiscoveryService,
    generator: ReportGeneratorService,
    session: SessionManager,
    max_retries: int = 1,
) -> tuple[ExtractionResult, bool, bool]:
    """Extract Feedback with validation and one retry."""
    retry_attempted = False
    retry_succeeded = False
    result = ExtractionResult(success=False, error="No feedback extraction attempted")

    for attempt in range(max_retries + 1):
        is_retry = attempt > 0
        if is_retry:
            retry_attempted = True
            log_automation_event(
                logger,
                "extraction_retry_started",
                attempt=attempt,
                report="report6",
            )
            await verify_mis_session_or_raise(session, page, "feedback_retry")

        try:
            result = await attempt_feedback_extract(
                page,
                extractor,
                navigation,
                filter_service,
                discovery_service,
                generator,
            )
        except MisSessionError:
            raise
        except (NavigationError, FilterError, ReportGenerationError, ReceivedSortError) as exc:
            log_automation_event(logger, "feedback_extraction_failed", error=str(exc))
            result = ExtractionResult(success=False, error=str(exc))
        except Exception as exc:
            log_automation_event(logger, "feedback_extraction_error", error=str(exc))
            result = ExtractionResult(success=False, error=str(exc))

        if result.success:
            if is_retry:
                retry_succeeded = True
                log_automation_event(
                    logger,
                    "extraction_retry_succeeded",
                    attempt=attempt,
                    report="report6",
                    row_count=result.row_count,
                )
            return result, retry_attempted, retry_succeeded

        await save_failure_artifacts(
            page,
            session,
            phase="feedback_validation" if result.validation_result else "feedback_extraction",
            report_slug="report6",
            html=result.html,
            error=result.error,
        )

        if attempt < max_retries:
            log_automation_event(
                logger,
                "extraction_will_retry",
                attempt=attempt,
                report="report6",
                error=result.error,
            )

    if retry_attempted:
        log_automation_event(
            logger,
            "extraction_retry_failed",
            report="report6",
            final_error=result.error,
        )
    return result, retry_attempted, retry_succeeded


async def _apply_report1_filters_fast(report_root) -> dict[str, str]:
    """Apply Report 1 filters using fast JavaScript batch operation."""
    js_code = """() => {
        const results = {};
        const selectByLabel = (sel, targetLabels) => {
            const el = document.querySelector(sel);
            if (!el || el.tagName !== 'SELECT') return null;
            const labels = Array.isArray(targetLabels) ? targetLabels : [targetLabels];
            
            // Priority 1: Exact match (case-insensitive)
            for (const label of labels) {
                const labelLower = label.toLowerCase().trim();
                for (let i = 0; i < el.options.length; i++) {
                    const optText = (el.options[i].text || '').trim();
                    if (optText.toLowerCase() === labelLower) {
                        el.selectedIndex = i;
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        return optText;
                    }
                }
            }
            
            // Priority 2: Option text includes target label (NOT vice versa)
            for (const label of labels) {
                const labelLower = label.toLowerCase().trim();
                for (let i = 0; i < el.options.length; i++) {
                    const optText = (el.options[i].text || '').trim();
                    if (optText.toLowerCase().includes(labelLower)) {
                        el.selectedIndex = i;
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        return optText;
                    }
                }
            }
            
            return el.options[el.selectedIndex]?.text || '';
        };

        results.zone = selectByLabel('#complaintZoneInput', ['ALL', 'All']);
        results.division = selectByLabel('#complaintDivInput', ['ALL', 'All']);
        results.department = selectByLabel('#complaintDeptInput', ['ALL', 'All']);
        results.mode = selectByLabel('#complaintModeInput', ['ALL', 'All']);
        results.type = selectByLabel('#complaintTypeInput', ['ALL', 'All']);
        results.sub_type = selectByLabel('#complaintSubTypeInput', ['ALL', 'All']);
        results.view = selectByLabel('#viewType', ['Zone Wise', 'ZoneWise']);
        results.excluding_assistance_cases = selectByLabel('#assistanceInput', ['Yes', 'YES']);
        results.excluding_refund_cases = selectByLabel('#refundInput', ['YES', 'Yes']);
        results.excluding_inquiry_cases = selectByLabel('#inquiryInput', ['Yes', 'YES']);
        results.channel_type = selectByLabel('#channelTypeInput', ['ALL', 'All']);
        results.train_type = selectByLabel('#trainTypeInput', ['ALL', 'All']);
        results.date_range = selectByLabel('#dateRange, select[name*="dateRange"], select[id*="dateRange"]', ['Previous Day', 'Previous day']);

        return results;
    }"""

    applied_values = await report_root.evaluate(js_code)
    return applied_values


async def regenerate_comprehensive_for_pdf(
    page,
    navigation: NavigationService,
    filter_service: FilterService,
    discovery_service: FilterDiscoveryService,
    generator: ReportGeneratorService,
    extractor: TableExtractor,
    session: SessionManager,
    *,
    known_filters: list | None = None,
):
    """Return to Report 1, reapply filters, Submit, re-sort Received, then ready for PDF.

    Uses fast JavaScript filter application for speed.
    """
    from app.automation.run_context import get_run_context

    ctx = get_run_context()
    span_cm = (
        ctx.timing.report_span("report1", "comprehensive_regenerate")
        if ctx is not None
        else None
    )

    async def _body():
        await verify_mis_session_or_raise(session, page, "comprehensive_regenerate")
        await navigation.navigate_to_report(page, REPORT_1)

        try:
            await page.wait_for_load_state("networkidle", timeout=10_000)
        except Exception:
            pass

        report_root = await filter_service.get_report_root(page)

        applied_values = await _apply_report1_filters_fast(report_root)

        from app.automation.wait_utils import tracked_sleep
        await tracked_sleep(0.1, reason="regen_fast_filters_settle")

        log_automation_event(
            logger,
            "comprehensive_regen_filters_applied_fast",
            applied_values=applied_values,
        )

        run_id = ctx.run_id if ctx is not None else ""
        await apply_previous_from_date(
            page,
            run_id,
            REPORT_1.slug,
            "comprehensive_pdf_regen",
            filter_service=filter_service,
        )
        log_phase1_submit_clicked(
            run_id,
            REPORT_1.slug,
            "comprehensive_pdf_regen",
        )
        await generator.generate_report(report_root, page)

        await page.wait_for_timeout(500)

        if not await generator.verify_report_displayed(report_root):
            await page.wait_for_timeout(1000)
            if not await generator.verify_report_displayed(report_root):
                raise ReportGenerationError(
                    "Comprehensive report did not display after regenerate before PDF"
                )
        row_count = await generator.count_rows(report_root)
        if row_count is None or row_count <= 0:
            raise ReportGenerationError(
                "Comprehensive table empty after regenerate before PDF"
            )

        await ReceivedColumnService().sort_received_descending(report_root, page)

        log_automation_event(
            logger,
            "comprehensive_regenerated_before_pdf",
            row_count=row_count,
            received_sorted=True,
            rediscovery_skipped=known_filters is not None,
        )
        return report_root, known_filters, applied_values

    if span_cm is not None:
        with span_cm:
            return await _body()
    return await _body()
