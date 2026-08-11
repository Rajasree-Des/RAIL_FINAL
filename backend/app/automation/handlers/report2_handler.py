"""Report 2 / division handler: Division Wise Top 25 dual-source workflow."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.automation.config import config
from app.automation.filters import (
    FilterError,
    Report2FilterNotFoundError,
    discover_and_log_fields,
    save_filter_failure_artifacts,
)
from app.automation.report2_feedback import (
    DIVISION_FEEDBACK_DATASET_ID,
    extract_feedback_division_csv,
)
from app.automation.report2_filters import REPORT_2_FILTERS
from app.automation.reports import ReportDefinition
from app.automation.run_context import get_run_context
from app.automation.schemas import ReportResult
from app.automation.table_extractor import TableExtractor
from app.automation.table_sort import ReceivedSortError
from app.automation.utils import ensure_directory, log_automation_event, resolve_report_dir
from app.automation.wait_utils import poll_until
from app.automation.workflow import (
    extract_with_retry,
    ingest_downloaded_file,
    save_failure_artifacts,
)
from .base import BaseReportHandler

if TYPE_CHECKING:
    from playwright.async_api import Page

    from app.automation.session import SessionManager

logger = logging.getLogger(__name__)

EXPECTED_FILTER_IDS = {
    "fromInput",
    "refundInput",
    "inquiryInput",
    "viewType",
    "assistanceInput",
}

MIN_EXPECTED_SELECTS = 5


class Report2Handler(BaseReportHandler):
    """Execute Division Wise Top 25 dual-source workflow (canonical key: division)."""

    async def _validate_filter_form_ready(
        self,
        page: "Page",
        report_slug: str,
    ) -> tuple[bool, list[str]]:
        """Validate that the filter form is fully rendered with expected controls.

        Returns:
            Tuple of (is_valid, list of found element IDs).
        """
        try:
            report_root = await self.filter_service.get_report_root(page)
        except Exception as exc:
            log_automation_event(
                logger,
                "report2_filter_form_root_failed",
                report_slug=report_slug,
                error=str(exc),
            )
            return False, []

        found_ids: list[str] = []
        for element_id in EXPECTED_FILTER_IDS:
            try:
                locator = report_root.locator(f"#{element_id}").first
                if await locator.count() > 0:
                    found_ids.append(element_id)
            except Exception:
                pass

        select_count = 0
        try:
            select_count = await report_root.locator("select").count()
        except Exception:
            pass

        is_valid = len(found_ids) >= 3 and select_count >= MIN_EXPECTED_SELECTS

        log_automation_event(
            logger,
            "report2_filter_form_validation",
            report_slug=report_slug,
            is_valid=is_valid,
            found_ids=found_ids,
            expected_ids=list(EXPECTED_FILTER_IDS),
            select_count=select_count,
            min_expected_selects=MIN_EXPECTED_SELECTS,
        )

        return is_valid, found_ids

    async def _apply_filters_with_retry(
        self,
        page: "Page",
        session: "SessionManager",
        report: ReportDefinition,
    ) -> tuple[Any, dict[str, str], int]:
        """Apply filters with page validation and one retry on failure.

        On filter not found:
        1. Log all discovered fields
        2. Save diagnostic artifacts (screenshot, HTML, field list)
        3. Reacquire MIS tab and retry navigation once
        4. If still fails, raise Report2FilterNotFoundError

        Returns:
            Tuple of (report_root, applied_values, row_count).
        """
        max_attempts = 2

        for attempt in range(max_attempts):
            is_retry = attempt > 0

            if is_retry:
                log_automation_event(
                    logger,
                    "report2_filter_retry_started",
                    report_slug=report.slug,
                    attempt=attempt,
                )
                page = await self.ensure_mis_page(
                    page, session, f"{report.slug}_filter_retry", report=report
                )
                await self.navigation.navigate_to_report(page, report)
                retry_ctx = get_run_context()
                if retry_ctx is not None:
                    retry_ctx.timing.record_retry(reason=f"{report.slug}_filter_form")

                async def _form_ready() -> bool:
                    ready, _ = await self._validate_filter_form_ready(page, report.slug)
                    return ready

                await poll_until(
                    _form_ready,
                    interval_seconds=0.2,
                    timeout_seconds=5.0,
                    reason="report2_filter_form_retry",
                )

            form_valid, found_ids = await self._validate_filter_form_ready(page, report.slug)

            if not form_valid:
                log_automation_event(
                    logger,
                    "report2_filter_form_not_ready",
                    report_slug=report.slug,
                    attempt=attempt,
                    found_ids=found_ids,
                )
                if attempt < max_attempts - 1:
                    continue

                discovered_fields = await discover_and_log_fields(
                    page, report.slug, missing_field="form_not_ready"
                )
                await save_filter_failure_artifacts(
                    page, report.slug, "form_not_ready", discovered_fields
                )
                raise Report2FilterNotFoundError(
                    f"Filter form not ready after {max_attempts} attempts. "
                    f"Found IDs: {found_ids}, expected: {list(EXPECTED_FILTER_IDS)}",
                    discovered_fields=discovered_fields,
                )

            try:
                return await self.apply_filters_and_submit(
                    page, report, filters=REPORT_2_FILTERS, session=session
                )
            except FilterError as exc:
                error_msg = str(exc)
                log_automation_event(
                    logger,
                    "report2_filter_error",
                    report_slug=report.slug,
                    attempt=attempt,
                    error=error_msg,
                )

                discovered_fields = await discover_and_log_fields(
                    page, report.slug, missing_field=error_msg
                )
                await save_filter_failure_artifacts(
                    page, report.slug, error_msg, discovered_fields
                )

                if attempt < max_attempts - 1:
                    continue

                raise Report2FilterNotFoundError(
                    f"Filter field not found after {max_attempts} attempts: {error_msg}",
                    discovered_fields=discovered_fields,
                ) from exc

        raise Report2FilterNotFoundError(
            f"Filter application failed after {max_attempts} attempts",
            discovered_fields=[],
        )

    async def execute(
        self,
        page: "Page",
        session: "SessionManager",
        report: ReportDefinition,
    ) -> ReportResult:
        started_at = datetime.now(UTC).isoformat()
        t0 = time.perf_counter()
        page = await self.ensure_mis_page(page, session, f"{report.slug}_start", report=report)
        await self.navigation.navigate_to_report(page, report)
        page = await self.ensure_mis_page(page, session, f"{report.slug}_after_nav", report=report)

        try:
            report_root, _, row_count = await self._apply_filters_with_retry(
                page, session, report
            )
        except Report2FilterNotFoundError as exc:
            log_automation_event(
                logger,
                "report2_source_a_filter_not_found",
                report_slug=report.slug,
                error=str(exc),
                discovered_field_count=len(exc.discovered_fields),
            )
            return self.build_failed_result(
                report.slug,
                f"REPORT2_SOURCE_A_FILTER_NOT_FOUND: {exc}",
            )

        try:
            report_root, page = await self._sort_source_a_with_retry(
                page, session, report, report_root
            )
        except ReceivedSortError as exc:
            await save_failure_artifacts(
                page,
                session,
                report_slug=report.slug,
                phase="source_a_received_sort",
                error=str(exc),
            )
            return self.build_failed_result(
                report.slug,
                f"REPORT2_SOURCE_A_SORT_FAILED: {exc}",
            )

        extractor = TableExtractor(output_dir=Path(config.extracted_data_dir))
        extraction_result, _, _ = await extract_with_retry(
            page,
            extractor,
            report_root,
            report,
            self.navigation,
            self.filter_service,
            self.discovery_service,
            self.generator,
            session,
            max_retries=1,
        )

        if await self.reject_empty_table(extraction_result) or not extraction_result.csv_path:
            await save_failure_artifacts(
                page,
                session,
                report_slug=report.slug,
                phase="source_a_extract",
                error=extraction_result.error or "Extraction failed or empty table",
            )
            return self.build_failed_result(
                report.slug,
                extraction_result.error or "Extraction failed or empty table",
            )

        # Remove total/footer then keep header + first 25 data rows under
        # storage/extracted/division/ (never division/division/).
        extracted_dir = ensure_directory(
            resolve_report_dir(config.extracted_data_dir, report.slug)
        )
        if extraction_result.data:
            header = extraction_result.data[0]
            body = extraction_result.data[1:]
            portal_total: list[str] | None = None
            for row in body:
                if self._is_total_data_row(row):
                    portal_total = row
                    break
            body = [r for r in body if not self._is_total_data_row(r)]
            top_data = [header] + body[:25]
            csv_path = extracted_dir / "report2_division_comprehensive_top25.csv"
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                import csv as _csv

                writer = _csv.writer(handle)
                writer.writerows(top_data)
            if portal_total and header:
                import json

                total_dict = {
                    header[i]: (portal_total[i] if i < len(portal_total) else "")
                    for i in range(len(header))
                }
                total_sidecar = extracted_dir / "report2_division_comprehensive_portal_total.json"
                total_sidecar.write_text(json.dumps(total_dict), encoding="utf-8")
                log_automation_event(
                    logger,
                    "report2_portal_total_saved",
                    path=str(total_sidecar),
                )
            extraction_result.csv_path = csv_path
            extraction_result.data = top_data
            extraction_result.row_count = len(top_data)
            extraction_result.success = True
            log_automation_event(
                logger,
                "report2_source_a_extracted",
                path=str(csv_path),
                row_count=max(len(top_data) - 1, 0),
            )
            log_automation_event(
                logger,
                "report2_top25_selected",
                row_count=max(len(top_data) - 1, 0),
                csv_path=str(csv_path),
            )


        source_paths: list[str] = [str(extraction_result.csv_path)]
        row_counts: dict[str, int] = {"comprehensive": extraction_result.row_count}

        # Source B: Feedback Division Wise (fail closed — do not emit A-only finals)
        page = await self.ensure_mis_page(page, session, f"{report.slug}_feedback_extraction")
        feedback_result, _, _ = await extract_feedback_division_csv(
            page,
            extractor,
            self.navigation,
            self.filter_service,
            self.discovery_service,
            self.generator,
            session,
            max_retries=1,
        )

        feedback_ingestion_success = False
        log_automation_event(
            logger,
            "report2_feedback_extraction_result",
            success=feedback_result.success,
            csv_path=str(feedback_result.csv_path) if feedback_result.csv_path else None,
            csv_path_exists=feedback_result.csv_path.exists() if feedback_result.csv_path else False,
            row_count=feedback_result.row_count,
            error=feedback_result.error,
        )

        if feedback_result.success and feedback_result.csv_path:
            feedback_csv_path = Path(feedback_result.csv_path)
            if not feedback_csv_path.exists():
                log_automation_event(
                    logger,
                    "report2_feedback_csv_missing",
                    csv_path=str(feedback_csv_path),
                    error="Feedback CSV reported success but file does not exist on disk",
                )
                return self.build_failed_result(
                    report.slug,
                    "Feedback CSV extraction reported success but file not found on disk",
                    partial=bool(extraction_result.csv_path),
                    source_paths=source_paths,
                    row_counts=row_counts,
                    source_csv_path=str(extraction_result.csv_path),
                    source_row_count=extraction_result.row_count,
                )

            feedback_csv_size = feedback_csv_path.stat().st_size
            if feedback_csv_size == 0:
                log_automation_event(
                    logger,
                    "report2_feedback_csv_empty",
                    csv_path=str(feedback_csv_path),
                    size=feedback_csv_size,
                )
                return self.build_failed_result(
                    report.slug,
                    "Feedback CSV file is empty",
                    partial=bool(extraction_result.csv_path),
                    source_paths=source_paths,
                    row_counts=row_counts,
                    source_csv_path=str(extraction_result.csv_path),
                    source_row_count=extraction_result.row_count,
                )

            source_paths.append(str(feedback_result.csv_path))
            row_counts["feedback"] = feedback_result.row_count
            log_automation_event(
                logger,
                "report2_source_b_extracted",
                csv_path=str(feedback_csv_path),
                row_count=feedback_result.row_count,
                size=feedback_csv_size,
                mtime=feedback_csv_path.stat().st_mtime,
            )
            feedback_ingestion_success = await ingest_downloaded_file(
                feedback_csv_path,
                DIVISION_FEEDBACK_DATASET_ID,
                source="feedback_division_csv",
            )

        # Skip portal archive — processor PDF is the review artifact
        await self.archive_pdf(page, report_root, report.slug, session=session)

        extraction_seconds = time.perf_counter() - t0
        log_automation_event(
            logger,
            "report_extraction_completed",
            slug=report.slug,
            row_count=extraction_result.row_count,
            feedback_row_count=feedback_result.row_count,
            duration_seconds=round(extraction_seconds, 3),
        )

        if not (
            extraction_result.success
            and feedback_result.success
            and feedback_ingestion_success
        ):
            return self.build_failed_result(
                report.slug,
                feedback_result.error
                or "Phase 8 blocked: validated Comprehensive and Feedback Division Wise sources required",
                partial=bool(extraction_result.csv_path) or feedback_ingestion_success,
                source_paths=source_paths,
                row_counts=row_counts,
                source_csv_path=str(extraction_result.csv_path),
                source_row_count=extraction_result.row_count,
            )

        ingestion_success = await ingest_downloaded_file(
            Path(extraction_result.csv_path),
            report.slug,
            source="html_extracted_csv",
        )
        if not ingestion_success:
            return self.build_failed_result(
                report.slug,
                "Source A ingestion failed",
                partial=True,
                source_paths=source_paths,
                row_counts=row_counts,
                source_csv_path=str(extraction_result.csv_path),
                source_row_count=extraction_result.row_count,
            )

        processing_result = await self.invoke_processor(report.slug, ingestion_success)
        if not processing_result.success:
            return self.build_failed_result(
                report.slug,
                processing_result.error or "Processing failed",
                partial=True,
                source_paths=source_paths,
                row_counts=row_counts,
                ingestion_success=True,
                source_csv_path=str(extraction_result.csv_path),
                source_row_count=extraction_result.row_count,
            )

        excel_ok = bool(
            processing_result.excel_path
            and Path(processing_result.excel_path).is_file()
            and Path(processing_result.excel_path).stat().st_size > 0
        )
        pdf_ok = bool(
            processing_result.pdf_path
            and Path(processing_result.pdf_path).is_file()
            and Path(processing_result.pdf_path).stat().st_size > 0
        )
        if not (excel_ok and pdf_ok):
            return self.build_failed_result(
                report.slug,
                "Processor completed but Excel/PDF missing or empty",
                partial=True,
                source_paths=source_paths,
                row_counts=row_counts,
                ingestion_success=True,
                source_csv_path=str(extraction_result.csv_path),
                source_row_count=extraction_result.row_count,
            )

        log_automation_event(
            logger,
            "report2_complete",
            row_count=row_count,
            comprehensive_rows=extraction_result.row_count,
            feedback_rows=feedback_result.row_count,
        )

        result = self.build_success_result(
            report.slug,
            source_paths=source_paths,
            row_counts=row_counts,
            excel_path=processing_result.excel_path,
            pdf_path=processing_result.pdf_path,
            processor_used=processing_result.processor_used,
            input_row_count=processing_result.input_row_count,
            processed_row_count=processing_result.processed_row_count,
            ingestion_success=True,
            source_csv_path=str(extraction_result.csv_path),
            source_row_count=extraction_result.row_count,
            output_columns=processing_result.output_columns,
            visible_columns=processing_result.visible_columns,
            selected_column_ids=processing_result.selected_column_ids,
            column_order=processing_result.column_order,
            configuration_source=processing_result.configuration_source,
        )
        result.started_at = started_at
        result.extraction_seconds = round(extraction_seconds, 3)
        result.completed_at = datetime.now(UTC).isoformat()
        result = await self._register_report2_artifacts(result)
        return result

    async def _sort_source_a_with_retry(
        self,
        page: "Page",
        session: "SessionManager",
        report: ReportDefinition,
        report_root: Any,
    ) -> tuple[Any, "Page"]:
        """Click Received twice; on verification failure, reapply filters once and retry."""
        try:
            await self.click_received_twice(
                report_root, page, report_slug=report.slug
            )
            return report_root, page
        except ReceivedSortError as first_exc:
            log_automation_event(
                logger,
                "report2_source_a_sort_retry",
                error=str(first_exc),
            )
            await save_failure_artifacts(
                page,
                session,
                report_slug=report.slug,
                phase="source_a_received_sort_retry",
                error=str(first_exc),
            )
            page = await self.ensure_mis_page(
                page, session, f"{report.slug}_sort_retry"
            )
            await self.navigation.navigate_to_report(page, report)
            report_root, _, _ = await self._apply_filters_with_retry(
                page, session, report
            )
            await self.click_received_twice(
                report_root, page, report_slug=report.slug
            )
            return report_root, page

    @staticmethod
    def _is_total_data_row(row: list[str]) -> bool:
        return any("total" in str(cell).strip().lower() for cell in row)

    async def _register_report2_artifacts(self, result: ReportResult) -> ReportResult:
        """Register current-run Excel/PDF so preview/download URLs are fresh."""
        ctx = get_run_context()
        if ctx is None:
            return result
        from app.automation.run_registry import build_dual_artifact_metadata, register_artifact
        from app.infrastructure.database.session import SessionLocal

        artifact_metadata = build_dual_artifact_metadata(
            selected_column_ids=result.selected_column_ids,
            column_order=result.column_order,
            run_id=ctx.run_id,
            report_slug=result.slug,
        )

        async with SessionLocal() as session:
            artifact_ids: dict[str, str] = {}
            if result.excel_path:
                art = await register_artifact(
                    session,
                    run_id=ctx.run_id,
                    report_slug=result.slug,
                    report_name=result.slug,
                    file_type="excel",
                    file_path=result.excel_path,
                    metadata=artifact_metadata,
                )
                if art:
                    artifact_ids["excel"] = art.id
                    ctx.remember_artifact(result.slug, "excel", art.id)
            if result.pdf_path:
                art = await register_artifact(
                    session,
                    run_id=ctx.run_id,
                    report_slug=result.slug,
                    report_name=result.slug,
                    file_type="pdf",
                    file_path=result.pdf_path,
                    metadata=artifact_metadata,
                )
                if art:
                    artifact_ids["pdf"] = art.id
                    ctx.remember_artifact(result.slug, "pdf", art.id)
            if artifact_ids.get("pdf"):
                result.pdf_download_url = (
                    f"/api/v1/automation/artifacts/{artifact_ids['pdf']}/download"
                )
                result.pdf_preview_url = (
                    f"/api/v1/automation/artifacts/{artifact_ids['pdf']}/preview"
                )
            if artifact_ids.get("excel"):
                result.excel_download_url = (
                    f"/api/v1/automation/artifacts/{artifact_ids['excel']}/download"
                )
            log_automation_event(
                logger,
                "report2_final_artifact_registered",
                run_id=ctx.run_id,
                excel_path=result.excel_path,
                pdf_path=result.pdf_path,
                excel_artifact_id=artifact_ids.get("excel"),
                pdf_artifact_id=artifact_ids.get("pdf"),
                selected_column_ids=result.selected_column_ids,
                configuration_source=result.configuration_source,
                pdf_preview_url=result.pdf_preview_url,
                excel_download_url=result.excel_download_url,
            )
        return result
