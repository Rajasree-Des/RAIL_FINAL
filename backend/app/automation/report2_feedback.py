"""Report 2-only Feedback (Division Wise) extraction.

Does not modify Report 1 Zone Wise feedback extraction in workflow.py.
"""

from __future__ import annotations

import logging

from app.automation.filters import FilterDiscoveryService, FilterError, FilterService
from app.automation.generator import ReportGenerationError, ReportGeneratorService
from app.automation.navigation import NavigationError, NavigationService
from app.automation.report1_filters import applied_filter_records
from app.automation.report2_filters import REPORT_2_FEEDBACK_FILTERS
from app.automation.reports import REPORT_6_FEEDBACK
from app.automation.session import MisSessionError, SessionManager
from app.automation.table_extractor import (
    FEEDBACK_DIVISION_REQUIRED_HEADERS,
    FEEDBACK_ZONE_REQUIRED_HEADERS,
    ExtractionResult,
    TableExtractor,
)
from app.automation.table_sort import ReceivedColumnService, ReceivedSortError
from app.automation.table_validator import (
    FEEDBACK_DIVISION_REQUIRED_HEADERS as VALIDATION_FEEDBACK_DIVISION_HEADERS,
    FEEDBACK_REQUIRED_HEADERS,
    validate_extracted_data,
)
from app.automation.utils import log_automation_event
from app.automation.portal_from_date import (
    apply_previous_from_date,
    log_phase1_submit_clicked,
)
from app.automation.run_context import get_run_context
from app.automation.workflow import save_failure_artifacts, verify_mis_session_or_raise

logger = logging.getLogger(__name__)

FEEDBACK_DIVISION_FILENAME = "report2_division_feedback_raw.csv"
DIVISION_FEEDBACK_DATASET_ID = "division_feedback"
DIVISION_REPORT_SLUG = "division"


async def attempt_feedback_division_extract(
    page,
    extractor: TableExtractor,
    navigation: NavigationService,
    filter_service: FilterService,
    discovery_service: FilterDiscoveryService,
    generator: ReportGeneratorService,
) -> ExtractionResult:
    """Single Feedback Tab pass with Division Wise filters → validate → save."""
    log_automation_event(logger, "report2_feedback_navigation_started")

    # discovery_service kept for call-site parity with Report 1 extract helpers.
    _ = discovery_service

    await navigation.navigate_to_report(page, REPORT_6_FEEDBACK)
    log_automation_event(
        logger,
        "report2_feedback_page_opened",
        page_url=page.url,
        report_slug=REPORT_6_FEEDBACK.slug,
    )

    report_root = await filter_service.get_report_root(page)
    # Prefer curated Division Wise filters (do not reuse Report 1 Zone Wise discovery).
    report_filters = list(REPORT_2_FEEDBACK_FILTERS)

    # Log the filters we're about to apply
    filter_summary = [
        {"name": f.name, "value": f.value, "label": getattr(f, "label", None)}
        for f in report_filters
    ]
    log_automation_event(
        logger,
        "report2_feedback_filters_to_apply",
        filters=filter_summary,
        filter_count=len(report_filters),
    )

    applied_values = await filter_service.apply_filters(
        report_root, report_filters, page=page
    )
    await filter_service.validate_mandatory(report_root, report_filters, applied_values)
    log_automation_event(
        logger,
        "report2_feedback_filters_applied",
        filters=applied_filter_records(report_filters, applied_values),
        applied_count=len(applied_values),
    )

    # Verify View=Division Wise was applied
    view_applied = applied_values.get("View", "")
    if "division" not in view_applied.lower():
        log_automation_event(
            logger,
            "report2_feedback_view_mismatch",
            expected="Division Wise",
            actual=view_applied,
            warning="View filter may not have been applied correctly",
        )

    ctx = get_run_context()
    run_id = ctx.run_id if ctx is not None else ""
    await apply_previous_from_date(
        page,
        run_id,
        DIVISION_REPORT_SLUG,
        "feedback",
        filter_service=filter_service,
    )
    log_phase1_submit_clicked(run_id, DIVISION_REPORT_SLUG, "feedback")

    log_automation_event(logger, "report2_feedback_submit_clicked")
    await generator.generate_report(report_root, page)
    if not await generator.verify_report_displayed(report_root):
        return ExtractionResult(
            success=False,
            error="Report 2 Feedback Division Wise report did not display after generate",
        )

    log_automation_event(logger, "report2_feedback_sorting_started")
    await ReceivedColumnService().sort_feedback_received_descending(report_root, page)
    log_automation_event(logger, "report2_feedback_sorting_completed")

    # Use the specialized Division Wise feedback table extraction
    log_automation_event(logger, "report2_feedback_table_extraction_started")
    data = await extractor.extract_division_feedback_table(report_root)

    if not data:
        # Fallback: try the original method with Zone headers
        log_automation_event(
            logger,
            "report2_feedback_table_fallback_attempt",
            reason="Division-specific extraction returned no data",
        )
        data = await extractor.extract_table_data_by_headers(
            report_root,
            FEEDBACK_ZONE_REQUIRED_HEADERS,
        )

    if not data:
        log_automation_event(
            logger,
            "report2_feedback_table_not_found",
            error="Neither Division nor Zone extraction found a valid table",
        )
        return ExtractionResult(
            success=False,
            error="Feedback Division Wise table not found - no table with required headers",
        )

    log_automation_event(
        logger,
        "report2_feedback_table_found",
        row_count=len(data),
        headers=data[0] if data else [],
        column_count=len(data[0]) if data else 0,
    )

    html = await extractor.extract_table_html(report_root)

    # Validate using Division-specific headers (accepts Division OR Organisation)
    # For validation, we just need to check basic feedback headers exist
    validation = validate_extracted_data(data, FEEDBACK_DIVISION_REQUIRED_HEADERS)
    if not validation.valid:
        log_automation_event(
            logger,
            "report2_feedback_validation_failed",
            report="division_feedback",
            error=validation.error,
            issues=validation.detected_issues,
            headers=data[0] if data else [],
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

    log_automation_event(
        logger,
        "report2_feedback_rows_extracted",
        row_count=len(data) - 1,
        headers=data[0] if data else [],
    )

    log_automation_event(
        logger,
        "report2_feedback_csv_save_start",
        report_slug=DIVISION_REPORT_SLUG,
        filename=FEEDBACK_DIVISION_FILENAME,
        row_count=len(data),
        headers=data[0] if data else [],
        output_dir=str(extractor.output_dir),
    )
    csv_path = await extractor.save_as_csv_fixed(
        data,
        report_slug=DIVISION_REPORT_SLUG,
        filename=FEEDBACK_DIVISION_FILENAME,
    )
    log_automation_event(
        logger,
        "report2_feedback_csv_saved",
        csv_path=str(csv_path) if csv_path else None,
        csv_exists=csv_path.exists() if csv_path else False,
        csv_size=csv_path.stat().st_size if csv_path and csv_path.exists() else 0,
    )
    if csv_path is None:
        return ExtractionResult(
            success=False,
            html=html,
            data=data,
            validation_result=validation,
            error="Failed to save Feedback Division Wise CSV",
        )

    # Verify CSV file exists, is non-empty, and has required headers
    if not csv_path.exists():
        log_automation_event(
            logger,
            "report2_feedback_csv_verification_failed",
            csv_path=str(csv_path),
            error="CSV file does not exist after save",
        )
        return ExtractionResult(
            success=False,
            html=html,
            data=data,
            validation_result=validation,
            error=f"REPORT2_FEEDBACK_EXTRACTION_FAILED: CSV not created at {csv_path}",
        )

    csv_size = csv_path.stat().st_size
    if csv_size == 0:
        log_automation_event(
            logger,
            "report2_feedback_csv_verification_failed",
            csv_path=str(csv_path),
            size=csv_size,
            error="CSV file is empty",
        )
        return ExtractionResult(
            success=False,
            html=html,
            data=data,
            validation_result=validation,
            error=f"REPORT2_FEEDBACK_EXTRACTION_FAILED: CSV is empty at {csv_path}",
        )

    log_automation_event(
        logger,
        "report2_feedback_csv_verified",
        csv_path=str(csv_path),
        csv_size=csv_size,
        row_count=len(data) - 1,
        headers=data[0] if data else [],
    )

    log_automation_event(
        logger,
        "report2_source_b_propagated",
        source_b_path=str(csv_path),
        row_count=len(data) - 1,
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


async def extract_feedback_division_csv(
    page,
    extractor: TableExtractor,
    navigation: NavigationService,
    filter_service: FilterService,
    discovery_service: FilterDiscoveryService,
    generator: ReportGeneratorService,
    session: SessionManager,
    max_retries: int = 1,
) -> tuple[ExtractionResult, bool, bool]:
    """Extract Report 2 Feedback Division Wise with validation and one retry."""
    retry_attempted = False
    retry_succeeded = False
    result = ExtractionResult(success=False, error="No Report 2 feedback extraction attempted")

    for attempt in range(max_retries + 1):
        is_retry = attempt > 0
        if is_retry:
            retry_attempted = True
            log_automation_event(
                logger,
                "extraction_retry_started",
                attempt=attempt,
                report="division_feedback",
            )
            await verify_mis_session_or_raise(session, page, "report2_feedback_retry")

        try:
            result = await attempt_feedback_division_extract(
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
            log_automation_event(logger, "report2_feedback_extraction_failed", error=str(exc))
            result = ExtractionResult(success=False, error=str(exc))
        except Exception as exc:
            log_automation_event(logger, "report2_feedback_extraction_error", error=str(exc))
            result = ExtractionResult(success=False, error=str(exc))

        if result.success:
            if is_retry:
                retry_succeeded = True
                log_automation_event(
                    logger,
                    "extraction_retry_succeeded",
                    attempt=attempt,
                    report="division_feedback",
                    row_count=result.row_count,
                )
            return result, retry_attempted, retry_succeeded

        await save_failure_artifacts(
            page,
            session,
            phase="report2_feedback_validation" if result.validation_result else "report2_feedback_extraction",
            report_slug=DIVISION_REPORT_SLUG,
            html=result.html,
            error=result.error,
        )

        if attempt < max_retries:
            log_automation_event(
                logger,
                "extraction_will_retry",
                attempt=attempt,
                report="division_feedback",
                error=result.error,
            )

    if retry_attempted:
        log_automation_event(
            logger,
            "extraction_retry_failed",
            report="division_feedback",
            final_error=result.error,
        )
    return result, retry_attempted, retry_succeeded
