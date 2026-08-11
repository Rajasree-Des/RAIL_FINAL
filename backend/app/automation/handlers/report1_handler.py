"""Report 1 handler: dual-source Zone Wise + Feedback workflow."""

from __future__ import annotations

import csv
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from app.automation.config import config
from app.automation.downloader import ReportDownloader
from app.automation.pdf_archiver import PdfArchiver
from app.automation.reports import ReportDefinition
from app.automation.report1_filters import REPORT_1_FILTERS
from app.automation.run_context import get_run_context
from app.automation.schemas import ReportResult
from app.automation.table_extractor import TableExtractor
from app.automation.table_validator import (
    COMPREHENSIVE_REQUIRED_HEADERS,
    FEEDBACK_REQUIRED_HEADERS,
    validate_extracted_data,
)
from app.automation.utils import log_automation_event, resolve_report_dir
from app.automation.workflow import (
    FEEDBACK_DATASET_ID,
    extract_feedback_zone_csv,
    extract_with_retry,
    ingest_downloaded_file,
    regenerate_comprehensive_for_pdf,
)

from .base import BaseReportHandler

if TYPE_CHECKING:
    from playwright.async_api import Page

    from app.automation.session import SessionManager

logger = logging.getLogger(__name__)

REPORT1_COMPREHENSIVE_MISSING = "REPORT1_COMPREHENSIVE_SOURCE_MISSING"
REPORT1_FEEDBACK_MISSING = "REPORT1_FEEDBACK_SOURCE_MISSING"
REPORT1_SOURCE_INVALID = "REPORT1_SOURCE_INVALID"
REPORT1_PHASE8_BLOCKED = "REPORT1_PHASE8_BLOCKED"


def _read_csv_rows(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [list(row) for row in csv.reader(handle)]


def validate_report1_source_csv(
    path: Path | None,
    *,
    required_headers: frozenset[str],
    label: str,
) -> tuple[bool, str | None, int]:
    """Verify a current-run CSV exists, is non-empty, and has headers + data rows."""
    if path is None:
        return False, f"{label} path is missing", 0
    candidate = Path(path)
    if not candidate.exists():
        return False, f"{label} file does not exist: {candidate}", 0
    size = candidate.stat().st_size
    if size <= 0:
        return False, f"{label} file is empty: {candidate}", 0
    try:
        rows = _read_csv_rows(candidate)
    except Exception as exc:
        return False, f"{label} could not be read: {exc}", 0
    validation = validate_extracted_data(rows, required_headers, min_data_rows=1)
    if not validation.valid:
        return False, f"{label} invalid: {validation.error}", 0
    return True, None, validation.row_count


class Report1Handler(BaseReportHandler):
    """Execute Report 1 dual-source Comprehensive + Feedback workflow."""

    async def execute(
        self,
        page: "Page",
        session: "SessionManager",
        report: ReportDefinition,
    ) -> ReportResult:
        started_at = datetime.now(UTC).isoformat()
        ctx = get_run_context()
        comprehensive_csv_path: Path | None = None
        feedback_csv_path: Path | None = None
        source_paths: list[str] = []
        row_counts: dict[str, int] = {}
        terminal: ReportResult | None = None

        try:
            page = await self.ensure_mis_page(page, session, f"{report.slug}_start", report=report)
            await self.navigation.navigate_to_report(page, report)
            page = await self.ensure_mis_page(page, session, f"{report.slug}_after_nav", report=report)

            try:
                await page.wait_for_load_state("networkidle", timeout=10_000)
            except Exception:
                pass

            report_root, applied_values, row_count = await self.apply_filters_and_submit(
                page,
                report,
                filters=REPORT_1_FILTERS,
                session=session,
                source_name="comprehensive",
            )
            log_automation_event(
                logger,
                "report1_filters_applied",
                applied_values=applied_values,
            )

            await self.click_received_twice(report_root, page, report_slug=report.slug)

            extractor = TableExtractor(output_dir=Path(config.extracted_data_dir))
            t_extract = time.perf_counter()
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
                max_retries=2,
            )
            extraction_seconds = round(time.perf_counter() - t_extract, 3)
            if ctx is not None:
                ctx.timing.record_report_span("report1", "extraction", extraction_seconds)
                ctx.timing.spans["extraction:report1"] = extraction_seconds
                log_automation_event(
                    logger,
                    "report_extraction_completed",
                    slug="report1",
                    duration_seconds=extraction_seconds,
                )

            if extraction_result.success and extraction_result.csv_path:
                comprehensive_csv_path = Path(extraction_result.csv_path)

            ok_a, err_a, rows_a = validate_report1_source_csv(
                comprehensive_csv_path,
                required_headers=COMPREHENSIVE_REQUIRED_HEADERS,
                label="Comprehensive",
            )
            if not ok_a:
                detail = err_a
                if extraction_result.error:
                    detail = f"{err_a} (extract: {extraction_result.error})"
                log_automation_event(
                    logger,
                    "report1_comprehensive_invalid",
                    error=detail,
                    csv_path=str(comprehensive_csv_path) if comprehensive_csv_path else None,
                    extract_success=extraction_result.success,
                    extract_error=extraction_result.error,
                )
                terminal = self._failed(
                    report.slug,
                    f"{REPORT1_COMPREHENSIVE_MISSING}: {detail}",
                    source_paths=source_paths,
                    row_counts=row_counts,
                    started_at=started_at,
                )
                return terminal

            source_paths.append(str(comprehensive_csv_path))
            row_counts["comprehensive"] = rows_a
            log_automation_event(
                logger,
                "report1_source_a_extracted",
                csv_path=str(comprehensive_csv_path),
                row_count=rows_a,
            )

            page = await self.ensure_mis_page(page, session, "feedback_extraction")
            feedback_cm = (
                ctx.timing.report_span("report1", "feedback_extraction")
                if ctx is not None
                else None
            )

            async def _feedback():
                return await extract_feedback_zone_csv(
                    page,
                    extractor,
                    self.navigation,
                    self.filter_service,
                    self.discovery_service,
                    self.generator,
                    session,
                    max_retries=2,
                )

            if feedback_cm is not None:
                with feedback_cm:
                    feedback_result, _, _ = await _feedback()
            else:
                feedback_result, _, _ = await _feedback()

            if feedback_result.success and feedback_result.csv_path:
                feedback_csv_path = Path(feedback_result.csv_path)

            ok_b, err_b, rows_b = validate_report1_source_csv(
                feedback_csv_path,
                required_headers=FEEDBACK_REQUIRED_HEADERS,
                label="Feedback",
            )
            if not ok_b:
                log_automation_event(
                    logger,
                    "report1_feedback_invalid",
                    error=err_b,
                    csv_path=str(feedback_csv_path) if feedback_csv_path else None,
                )
                terminal = self._failed(
                    report.slug,
                    f"{REPORT1_FEEDBACK_MISSING}: {err_b}",
                    source_paths=source_paths,
                    row_counts=row_counts,
                    started_at=started_at,
                )
                return terminal

            source_paths.append(str(feedback_csv_path))
            row_counts["feedback"] = rows_b
            log_automation_event(
                logger,
                "report1_source_b_extracted",
                csv_path=str(feedback_csv_path),
                row_count=rows_b,
            )

            # Ingest both current-run CSVs before Phase 8 (order: feedback then comprehensive)
            feedback_ingestion_success = await ingest_downloaded_file(
                feedback_csv_path,
                FEEDBACK_DATASET_ID,
                source="feedback_zone_csv",
            )
            comprehensive_ingestion_success = await ingest_downloaded_file(
                comprehensive_csv_path,
                report.slug,
                source="html_extracted_csv",
            )
            log_automation_event(
                logger,
                "report1_sources_ingested",
                comprehensive_path=str(comprehensive_csv_path),
                feedback_path=str(feedback_csv_path),
                comprehensive_ingestion=comprehensive_ingestion_success,
                feedback_ingestion=feedback_ingestion_success,
                comprehensive_rows=rows_a,
                feedback_rows=rows_b,
            )

            if not (comprehensive_ingestion_success and feedback_ingestion_success):
                terminal = self._failed(
                    report.slug,
                    f"{REPORT1_PHASE8_BLOCKED}: ingestion failed for current-run sources",
                    source_paths=source_paths,
                    row_counts=row_counts,
                    ingestion_success=False,
                    started_at=started_at,
                )
                return terminal

            page = await self.ensure_mis_page(
                page, session, "comprehensive_regenerate", report=report
            )
            report_root, _, _ = await regenerate_comprehensive_for_pdf(
                page,
                self.navigation,
                self.filter_service,
                self.discovery_service,
                self.generator,
                extractor,
                session,
                known_filters=REPORT_1_FILTERS,
            )

            archive_path: str | None = None
            skip_portal_pdf = ctx is not None and ctx.skip_portal_archive
            phase6_pdf_path = None

            if skip_portal_pdf:
                log_automation_event(
                    logger,
                    "phase6_pdf_download_skipped",
                    reason="processor_pdf_preferred",
                )
            else:
                downloader = ReportDownloader(downloads_dir=Path(config.downloads_dir))
                pdf_cm = (
                    ctx.timing.report_span("report1", "phase6_pdf_download")
                    if ctx is not None
                    else None
                )

                async def _download():
                    return await downloader.download_report(
                        report_root, page, report_slug=report.slug
                    )

                if pdf_cm is not None:
                    with pdf_cm:
                        download_result = await _download()
                else:
                    download_result = await _download()

                if (
                    download_result.file_path
                    and download_result.file_path.suffix.lower() == ".pdf"
                ):
                    phase6_pdf_path = download_result.file_path

                page = await self.ensure_mis_page(page, session, "pdf_archive")
                archive_dir = resolve_report_dir(config.pdf_archive_dir, report.slug)
                archiver = PdfArchiver(archive_dir=archive_dir)
                archive_cm = (
                    ctx.timing.report_span("report1", "archive") if ctx is not None else None
                )

                async def _archive():
                    return await archiver.archive_pdf(
                        page,
                        report_root,
                        report.slug,
                        use_print=False,
                        existing_pdf_path=phase6_pdf_path,
                    )

                if archive_cm is not None:
                    with archive_cm:
                        archive_result = await _archive()
                else:
                    archive_result = await _archive()
                if archive_result.file_path:
                    archive_path = str(archive_result.file_path)

            t_proc = time.perf_counter()
            processing_result = await self.invoke_processor(
                report.slug, comprehensive_ingestion_success
            )
            if ctx is not None:
                elapsed = time.perf_counter() - t_proc
                ctx.timing.record_report_span("report1", "processing", elapsed)
                ctx.timing.record_report_span("report1", "excel_generation", elapsed / 2)
                ctx.timing.record_report_span("report1", "pdf_generation", elapsed / 2)
                ctx.timing.spans["processing:report1"] = round(elapsed, 3)

            if not processing_result.success:
                terminal = self._failed(
                    report.slug,
                    processing_result.error or "REPORT1_PROCESSING_FAILED",
                    source_paths=source_paths,
                    row_counts=row_counts,
                    ingestion_success=True,
                    started_at=started_at,
                )
                return terminal

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
                terminal = self._failed(
                    report.slug,
                    "REPORT1_ARTIFACTS_MISSING: processor completed but Excel/PDF missing or empty",
                    source_paths=source_paths,
                    row_counts=row_counts,
                    ingestion_success=True,
                    started_at=started_at,
                )
                return terminal

            log_automation_event(
                logger,
                "report1_complete",
                row_count=row_count,
                comprehensive_rows=rows_a,
                feedback_rows=rows_b,
                comprehensive_path=str(comprehensive_csv_path),
                feedback_path=str(feedback_csv_path),
                excel_path=processing_result.excel_path,
                pdf_path=processing_result.pdf_path,
            )

            result = self.build_success_result(
                report.slug,
                source_paths=source_paths,
                row_counts=row_counts,
                excel_path=processing_result.excel_path,
                pdf_path=processing_result.pdf_path,
                archive_path=archive_path,
                processor_used=processing_result.processor_used,
                input_row_count=processing_result.input_row_count,
                processed_row_count=processing_result.processed_row_count,
                ingestion_success=True,
                source_csv_path=str(comprehensive_csv_path),
                source_row_count=rows_a,
                output_columns=processing_result.output_columns,
                visible_columns=processing_result.visible_columns,
                selected_column_ids=processing_result.selected_column_ids,
                column_order=processing_result.column_order,
                configuration_source=processing_result.configuration_source,
            )
            result.started_at = started_at
            result.completed_at = datetime.now(UTC).isoformat()
            result.extraction_seconds = extraction_seconds
            result.row_count = rows_a
            result = await self._register_report1_artifacts(result)
            terminal = result
            return terminal

        except Exception as exc:
            log_automation_event(
                logger,
                "report1_handler_exception",
                error=str(exc),
            )
            terminal = self._failed(
                report.slug,
                f"REPORT1_HANDLER_ERROR: {exc}",
                source_paths=source_paths,
                row_counts=row_counts,
                started_at=started_at,
            )
        finally:
            if terminal is None:
                # Should never leave Report 1 without a terminal status.
                terminal = self._failed(
                    report.slug,
                    "REPORT1_NO_TERMINAL_STATUS",
                    source_paths=source_paths,
                    row_counts=row_counts,
                    started_at=started_at,
                )
            elif terminal.completed_at is None:
                terminal.completed_at = datetime.now(UTC).isoformat()
            if ctx is not None:
                ctx.store_partial(terminal)
            log_automation_event(
                logger,
                "report1_terminal_status",
                status=terminal.status,
                error=terminal.error,
                source_paths=terminal.source_paths,
                excel_path=terminal.excel_path,
                pdf_path=terminal.pdf_path,
            )

        return terminal

    async def _apply_filters_fast(self, report_root, page) -> dict[str, str]:
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

        from app.automation.wait_utils import tracked_sleep
        await tracked_sleep(0.05, reason="report1_fast_filters_settle")

        log_automation_event(
            logger,
            "report1_filters_applied_fast",
            applied_values=applied_values,
        )

        return applied_values

    def _failed(
        self,
        slug: str,
        error: str,
        *,
        source_paths: list[str] | None = None,
        row_counts: dict[str, int] | None = None,
        ingestion_success: bool = False,
        started_at: str | None = None,
    ) -> ReportResult:
        """Fail-closed Report 1 result — never partial without real outputs."""
        result = self.build_failed_result(
            slug,
            error,
            partial=False,
            source_paths=source_paths,
            row_counts=row_counts,
            ingestion_success=ingestion_success,
            source_csv_path=source_paths[0] if source_paths else None,
            source_row_count=(row_counts or {}).get("comprehensive"),
        )
        result.processing_success = False
        result.processing_attempted = False
        result.excel_path = None
        result.pdf_path = None
        result.pdf_download_url = None
        result.excel_download_url = None
        result.pdf_preview_url = None
        result.started_at = started_at
        result.completed_at = datetime.now(UTC).isoformat()
        return result

    async def _register_report1_artifacts(self, result: ReportResult) -> ReportResult:
        """Register current-run processed Excel/PDF so preview/download URLs are fresh."""
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
                "report1_final_artifact_registered",
                run_id=ctx.run_id,
                excel_path=result.excel_path,
                pdf_path=result.pdf_path,
                excel_artifact_id=artifact_ids.get("excel"),
                pdf_artifact_id=artifact_ids.get("pdf"),
                selected_column_ids=result.selected_column_ids,
                configuration_source=result.configuration_source,
            )
        return result
