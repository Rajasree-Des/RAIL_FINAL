"""Base handler class with shared automation logic."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.automation.config import config
from app.automation.filters import FilterDiscoveryService, FilterService
from app.automation.generator import ReportGenerationError, ReportGeneratorService
from app.automation.navigation import NavigationService
from app.automation.pdf_archiver import PdfArchiver
from app.automation.processing.service import process_report
from app.automation.report1_filters import build_filters_from_discovery
from app.automation.report_keys import canonicalize_report_key
from app.automation.reports import ReportDefinition
from app.automation.run_context import get_run_context
from app.automation.portal_from_date import (
    PHASE3_REPORT_KEYS,
    apply_previous_from_date,
    log_phase1_submit_clicked,
    log_phase2_submit_clicked,
    log_phase3_submit_clicked,
)
from app.automation.schemas import ReportResult
from app.automation.session import MisSessionError, SessionManager
from app.automation.table_extractor import ExtractionResult, TableExtractor
from app.automation.table_sort import ReceivedColumnService
from app.automation.utils import log_automation_event, resolve_report_dir
from datetime import UTC, datetime

if TYPE_CHECKING:
    from playwright.async_api import Browser, Page

logger = logging.getLogger(__name__)

# Re-export for handlers/tests that imported from base
__all__ = ["BaseReportHandler", "MisSessionError"]


class BaseReportHandler(ABC):
    """Base class for report-specific handlers."""

    def __init__(self) -> None:
        self.navigation = NavigationService()
        self.filter_service = FilterService()
        self.discovery_service = FilterDiscoveryService()
        self.generator = ReportGeneratorService()
        self.received_service = ReceivedColumnService()
        self._browser: Browser | None = None

    def bind_browser(self, browser: "Browser") -> None:
        """Attach the CDP browser so session reacquisition can scan all tabs."""
        self._browser = browser

    @abstractmethod
    async def execute(
        self,
        page: "Page",
        session: SessionManager,
        report: ReportDefinition,
    ) -> ReportResult:
        """Execute the report workflow and return result."""
        ...

    async def ensure_mis_page(
        self,
        page: "Page",
        session: SessionManager,
        context: str = "operation",
        *,
        prefer_url_fragment: str | None = None,
        report: ReportDefinition | None = None,
    ) -> "Page":
        """Reacquire authenticated MIS page; prefer the active report URL fragment."""
        ctx = get_run_context()
        if ctx is not None:
            await ctx.checkpoint(f"ensure_mis:{context}")

        fragment = prefer_url_fragment
        if fragment is None and report is not None:
            fragment = report.url_fragment

        if self._browser is not None:
            mis_page = await session.ensure_authenticated_mis_page(
                self._browser,
                page,
                prefer_url_fragment=fragment,
            )
            if report is not None and not await self.navigation.verify_report_page(
                mis_page, report
            ):
                log_automation_event(
                    logger,
                    "mis_page_wrong_report",
                    context=context,
                    expected_fragment=report.url_fragment,
                    actual_url=mis_page.url,
                    report_slug=report.slug,
                )
                await self.navigation.navigate_to_report(mis_page, report)
                mis_page = await session.ensure_authenticated_mis_page(
                    self._browser,
                    mis_page,
                    prefer_url_fragment=report.url_fragment,
                )
                if not await self.navigation.verify_report_page(mis_page, report):
                    await self.navigation.navigate_to_report(mis_page, report)
            log_automation_event(
                logger,
                "mis_session_verified",
                context=context,
                page_url=mis_page.url,
                prefer_url_fragment=fragment,
            )
            return mis_page

        status = await session.verify_mis_session(page)
        if not status.valid:
            log_automation_event(
                logger,
                "mis_session_lost",
                context=context,
                error_code=status.error_code,
                error=status.error,
            )
            raise MisSessionError(status)
        if report is not None and not await self.navigation.verify_report_page(page, report):
            await self.navigation.navigate_to_report(page, report)
        log_automation_event(
            logger,
            "mis_session_verified",
            context=context,
            page_url=page.url,
            prefer_url_fragment=fragment,
        )
        return page

    async def verify_session(
        self,
        page: "Page",
        session: SessionManager,
        context: str = "operation",
        *,
        report: ReportDefinition | None = None,
    ) -> "Page":
        """Verify MIS session is valid; reacquire when browser is bound."""
        return await self.ensure_mis_page(page, session, context, report=report)

    async def apply_filters_and_submit(
        self,
        page: "Page",
        report: ReportDefinition,
        filters: list | None = None,
        session: SessionManager | None = None,
        *,
        source_name: str = "comprehensive",
    ) -> tuple:
        """Apply filters, submit, and verify report is displayed.

        Returns (report_root, applied_values, row_count).
        """
        key = canonicalize_report_key(report.slug)
        ctx = get_run_context()
        span_cm = (
            ctx.timing.report_span(key, "nav_filter_submit")
            if ctx is not None
            else None
        )

        async def _body() -> tuple:
            nonlocal page
            ctx_inner = get_run_context()
            if ctx_inner is not None:
                await ctx_inner.checkpoint(f"filters:{report.slug}")
            if session is not None:
                page = await self.ensure_mis_page(
                    page,
                    session,
                    f"{report.slug}_before_submit",
                    report=report,
                )
            elif not await self.navigation.verify_report_page(page, report):
                await self.navigation.navigate_to_report(page, report)

            report_root = await self.filter_service.get_report_root(page)

            if filters is None:
                discovered_fields = await self.discovery_service.discover_fields(page)
                filters_local = build_filters_from_discovery(discovered_fields, report.slug)
            else:
                filters_local = filters

            applied_values = await self.filter_service.apply_filters(
                report_root,
                filters_local,
                page=page,
            )
            await self.filter_service.validate_mandatory(
                report_root, filters_local, applied_values
            )

            # Verify Previous Day was applied when dateRange is present
            date_applied = None
            for name, value in applied_values.items():
                if "date" in name.lower() and "range" in name.lower():
                    date_applied = value
                    break
            if date_applied is None:
                date_applied = applied_values.get("dateRange")
            if date_applied and "previous day" not in str(date_applied).lower():
                log_automation_event(
                    logger,
                    "date_range_mismatch",
                    applied=date_applied,
                    expected="Previous Day",
                )
                raise ReportGenerationError(
                    f"Date Range must be Previous Day before Submit, got: {date_applied}"
                )

            if key in {"report1", "division"}:
                run_id = ctx_inner.run_id if ctx_inner is not None else ""
                await apply_previous_from_date(
                    page,
                    run_id,
                    report.slug,
                    source_name,
                    filter_service=self.filter_service,
                )
                log_phase1_submit_clicked(
                    run_id,
                    report.slug,
                    source_name,
                )
            elif key == "train-no":
                run_id = ctx_inner.run_id if ctx_inner is not None else ""
                await apply_previous_from_date(
                    page,
                    run_id,
                    report.slug,
                    source_name,
                    filter_service=self.filter_service,
                )
                log_phase2_submit_clicked(
                    run_id,
                    report.slug,
                    source_name,
                )
            elif key in PHASE3_REPORT_KEYS:
                run_id = ctx_inner.run_id if ctx_inner is not None else ""
                await apply_previous_from_date(
                    page,
                    run_id,
                    report.slug,
                    source_name,
                    filter_service=self.filter_service,
                )
                log_phase3_submit_clicked(
                    run_id,
                    report.slug,
                    source_name,
                )

            await self.generator.generate_report(report_root, page)

            await page.wait_for_timeout(500)

            row_count = await self.generator.count_rows(report_root)

            if not await self.generator.verify_report_displayed(report_root):
                await page.wait_for_timeout(1000)
                if not await self.generator.verify_report_displayed(report_root):
                    raise ReportGenerationError(
                        f"Report {report.slug} did not display after generate"
                    )

            return report_root, applied_values, row_count

        if span_cm is not None:
            with span_cm:
                return await _body()
        return await _body()

    async def click_received_twice(
        self,
        report_root: Any,
        page: "Page",
        feedback: bool = False,
        *,
        report_slug: str | None = None,
    ) -> None:
        """Click Received or Feedback Received column header twice for descending sort."""
        ctx = get_run_context()
        if ctx is not None:
            await ctx.checkpoint(f"sort:{report_slug or 'received'}")
        slug = canonicalize_report_key(report_slug) if report_slug else None

        async def _sort() -> None:
            if feedback:
                await self.received_service.sort_feedback_received_descending(
                    report_root, page
                )
            else:
                await self.received_service.sort_received_descending(report_root, page)

        if ctx is not None and slug:
            with ctx.timing.report_span(slug, "sorting"):
                await _sort()
        else:
            await _sort()

    async def extract_table_data(
        self,
        page: "Page",
        report_root: Any,
        report_slug: str,
        required_headers: set[str] | None = None,
    ) -> ExtractionResult:
        """Extract HTML table data and save as CSV under the canonical key."""
        key = canonicalize_report_key(report_slug)
        extractor = TableExtractor(output_dir=Path(config.extracted_data_dir))

        if required_headers:
            data = await extractor.extract_table_data_by_headers(
                report_root,
                required_headers,
            )
            if not data:
                return ExtractionResult(
                    success=False,
                    error=f"Table with required headers not found for {key}",
                )
            html = await extractor.extract_table_html(report_root)
            csv_path = await extractor.save_as_csv_fixed(
                data,
                report_slug=key,
            )
            return ExtractionResult(
                success=csv_path is not None,
                html=html,
                data=data,
                csv_path=csv_path,
                row_count=len(data),
                column_count=len(data[0]) if data else 0,
            )
        return await extractor.extract_and_save(report_root, key)

    async def reject_empty_table(self, extraction_result: ExtractionResult) -> bool:
        """Check if table is empty or has no data. Returns True if should reject."""
        if not extraction_result.success:
            return True
        if extraction_result.row_count is None or extraction_result.row_count == 0:
            return True
        if extraction_result.data and len(extraction_result.data) == 0:
            return True
        if extraction_result.html and "no data available" in extraction_result.html.lower():
            return True
        return False

    async def ingest_csv(
        self,
        csv_path: Path,
        report_slug: str,
        source: str = "html_extracted_csv",
        *,
        expected_row_count: int | None = None,
    ) -> bool:
        """Ingest the CSV file using the canonical dataset key."""
        from app.automation.workflow import ingest_downloaded_file

        return await ingest_downloaded_file(
            csv_path,
            report_slug,
            source,
            expected_row_count=expected_row_count,
        )

    async def invoke_processor(
        self,
        report_slug: str,
        ingestion_success: bool,
        *,
        column_selection: dict | None = None,
    ):
        """Call the registered processor for this report slug."""
        from app.automation.run_context import get_run_context
        from app.automation.report_keys import canonicalize_report_key

        selection = dict(column_selection) if column_selection else {}
        ctx = get_run_context()
        if ctx is not None:
            if ctx.manual_config:
                manual = ctx.manual_config
                slug = canonicalize_report_key(report_slug)
                manual_slug = canonicalize_report_key(str(manual.get("report_slug") or slug))
                if manual_slug == slug:
                    selection.update(manual)
            if ctx.run_id:
                selection.setdefault("run_id", ctx.run_id)
        if not selection:
            selection = None
        return await process_report(
            canonicalize_report_key(report_slug),
            ingestion_success,
            column_selection=selection,
        )

    async def archive_pdf(
        self,
        page: "Page",
        report_root: Any,
        report_slug: str,
        existing_pdf_path: Path | None = None,
        session: SessionManager | None = None,
    ) -> tuple[bool, str | None, str | None]:
        """Archive PDF for the report. Returns (success, archive_path, error).

        Skips portal PDF click when RunContext.skip_portal_archive is set
        (Reports 2–6 use processor PDFs). Report 1 still passes existing_pdf_path.
        """
        key = canonicalize_report_key(report_slug)
        ctx = get_run_context()
        if ctx is not None and ctx.skip_portal_archive and existing_pdf_path is None:
            log_automation_event(
                logger,
                "pdf_archive_skipped",
                slug=key,
                reason="processor_pdf_preferred",
            )
            return True, None, None

        if session is not None:
            page = await self.ensure_mis_page(page, session, f"{key}_before_pdf")

        archive_dir = resolve_report_dir(config.pdf_archive_dir, key)
        try:
            archiver = PdfArchiver(archive_dir=archive_dir)
            archive_result = await archiver.archive_pdf(
                page,
                report_root,
                key,
                use_print=False,
                existing_pdf_path=existing_pdf_path,
            )
            if self._browser is not None and session is not None:
                page = await session.ensure_authenticated_mis_page(self._browser, page)
            return (
                archive_result.success,
                str(archive_result.file_path) if archive_result.file_path else None,
                archive_result.error,
            )
        except Exception as exc:
            logger.warning("PDF archive failed for %s: %s", key, exc)
            return False, None, str(exc)

    async def finalize_after_extract(
        self,
        *,
        slug: str,
        csv_path: Path,
        source_paths: list[str] | None = None,
        row_counts: dict[str, int] | None = None,
        source_row_count: int | None = None,
        archive_path: str | None = None,
        ingest_source: str = "html_extracted_csv",
        started_at: str | None = None,
        extraction_seconds: float | None = None,
    ) -> ReportResult:
        """Ingest + process, optionally deferred via RunContext process pool."""
        key = canonicalize_report_key(slug)
        ctx = get_run_context()
        if ctx is not None:
            await ctx.checkpoint("after_extract_before_process")

        paths = source_paths or [str(csv_path)]
        counts = row_counts or {"extracted": source_row_count or 0}
        row_count = source_row_count
        if row_count is None and counts:
            row_count = next(iter(counts.values()), None)

        partial = ReportResult(
            slug=key,
            dataset_key=key,
            status="partial_success",
            source_paths=paths,
            source_csv_path=str(csv_path),
            source_row_count=row_count,
            row_counts=counts,
            archive_path=archive_path,
            started_at=started_at,
            extraction_seconds=extraction_seconds,
            row_count=row_count,
            processing_attempted=False,
            processing_success=False,
            ingestion_success=False,
            error="Extracted; ingest/process pending",
        )

        if ctx is not None:
            ctx.store_partial(partial)
            ctx.timing.record_report_span(
                key, "extraction", extraction_seconds or 0.0
            )

        async def _work() -> ReportResult:
            from app.automation.run_context import get_run_context
            from app.automation.workflow import ingest_downloaded_file
            from app.automation.run_registry import register_artifact
            from app.infrastructure.database.session import SessionLocal
            from app.features.reports.scr_fresh import is_scr_manual_fresh, verify_current_run_source

            ctx = get_run_context()

            if ctx is not None and (
                is_scr_manual_fresh(ctx.manual_config) or key == "scr-station"
            ):
                try:
                    verify_current_run_source(
                        csv_path,
                        run_id=ctx.run_id,
                        report_slug=key,
                        run_started_at=ctx.run_started_at,
                    )
                except ValueError as exc:
                    log_automation_event(
                        logger,
                        "stale_source_rejected",
                        run_id=ctx.run_id,
                        report_slug=key,
                        source_path=str(csv_path),
                        error=str(exc),
                    )
                    return self.build_failed_result(
                        key,
                        str(exc),
                        source_paths=paths,
                        row_counts=counts,
                        source_csv_path=str(csv_path),
                        source_row_count=row_count,
                    )

            ingestion_success = await ingest_downloaded_file(
                csv_path,
                key,
                source=ingest_source,
                expected_row_count=row_count if key == "scr-station" else None,
            )
            if not ingestion_success:
                return self.build_failed_result(
                    key,
                    f"INGESTION_FAILED: Could not ingest current-run source for {key}",
                    source_paths=paths,
                    row_counts=counts,
                    source_csv_path=str(csv_path),
                    source_row_count=row_count,
                )

            if ctx is not None and (
                is_scr_manual_fresh(ctx.manual_config) or key == "scr-station"
            ):
                log_automation_event(
                    logger,
                    "current_run_dataset_ingested",
                    run_id=ctx.run_id,
                    report_slug=key,
                    source_path=str(csv_path),
                    row_count=row_count,
                )

            processing_result = await self.invoke_processor(key, ingestion_success)
            if not processing_result.success:
                err = processing_result.error or "Processing failed"
                if not err.startswith(("PROCESSING_FAILED", "REPORT")):
                    err = f"PROCESSING_FAILED: {err}"
                return self.build_failed_result(
                    key,
                    err,
                    source_paths=paths,
                    row_counts=counts,
                    ingestion_success=True,
                    source_csv_path=str(csv_path),
                    source_row_count=row_count,
                )

            if ctx is not None and processing_result.selected_column_ids:
                log_automation_event(
                    logger,
                    "selected_columns_applied",
                    run_id=ctx.run_id,
                    report_slug=key,
                    selected_column_ids=processing_result.selected_column_ids,
                    visible_columns=processing_result.visible_columns,
                )

            result = self.build_success_result(
                key,
                source_paths=paths,
                row_counts=counts,
                excel_path=processing_result.excel_path,
                pdf_path=processing_result.pdf_path,
                archive_path=archive_path,
                processor_used=processing_result.processor_used,
                input_row_count=row_count,
                processed_row_count=processing_result.processed_row_count,
                ingestion_success=True,
                source_csv_path=str(csv_path),
                source_row_count=row_count,
                output_columns=processing_result.output_columns,
                visible_columns=processing_result.visible_columns,
                selected_column_ids=processing_result.selected_column_ids,
                column_order=processing_result.column_order,
                configuration_source=processing_result.configuration_source,
            )
            result.started_at = started_at
            result.extraction_seconds = extraction_seconds
            result.row_count = row_count
            result.completed_at = datetime.now(UTC).isoformat()

            # Gate terminal success on non-empty Excel/PDF artifacts
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
                    key,
                    "ARTIFACT_REGISTRATION_FAILED: Processor completed but Excel/PDF missing or empty",
                    source_paths=paths,
                    row_counts=counts,
                    ingestion_success=True,
                    source_csv_path=str(csv_path),
                    source_row_count=row_count,
                )

            log_automation_event(
                logger,
                "excel_generated",
                run_id=ctx.run_id if ctx else None,
                report_slug=key,
                excel_path=processing_result.excel_path,
            )
            log_automation_event(
                logger,
                "pdf_generated",
                run_id=ctx.run_id if ctx else None,
                report_slug=key,
                pdf_path=processing_result.pdf_path,
            )

            if ctx is not None:
                from app.automation.run_registry import build_dual_artifact_metadata

                artifact_metadata = None
                if getattr(processing_result, "artifact_metadata", None):
                    artifact_metadata = dict(processing_result.artifact_metadata)
                    if ctx.run_id and "run_id" not in artifact_metadata:
                        artifact_metadata["run_id"] = ctx.run_id
                elif processing_result.selected_column_ids:
                    artifact_metadata = build_dual_artifact_metadata(
                        selected_column_ids=processing_result.selected_column_ids,
                        column_order=processing_result.column_order,
                        run_id=ctx.run_id,
                        report_slug=key,
                    )
                async with SessionLocal() as session:
                    artifact_ids: dict[str, str] = {}
                    if processing_result.excel_path:
                        art = await register_artifact(
                            session,
                            run_id=ctx.run_id,
                            report_slug=key,
                            report_name=key,
                            file_type="excel",
                            file_path=processing_result.excel_path,
                            metadata=artifact_metadata,
                        )
                        if art:
                            artifact_ids["excel"] = art.id
                            ctx.remember_artifact(key, "excel", art.id)
                    if processing_result.pdf_path:
                        art = await register_artifact(
                            session,
                            run_id=ctx.run_id,
                            report_slug=key,
                            report_name=key,
                            file_type="pdf",
                            file_path=processing_result.pdf_path,
                            metadata=artifact_metadata,
                        )
                        if art:
                            artifact_ids["pdf"] = art.id
                            ctx.remember_artifact(key, "pdf", art.id)
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
                        "artifacts_registered",
                        run_id=ctx.run_id,
                        report_slug=key,
                        excel_artifact_id=artifact_ids.get("excel"),
                        pdf_artifact_id=artifact_ids.get("pdf"),
                    )
                    log_automation_event(
                        logger,
                        "report_terminal_status",
                        run_id=ctx.run_id,
                        report_slug=key,
                        status="success",
                    )
                    rt = ctx.timing.ensure_report(key)
                    result.processing_seconds = rt.processing_seconds
                    result.duration_seconds = rt.duration_seconds
            return result

        if ctx is not None and ctx.defer_processing:
            await ctx.schedule_processing(key, _work)
            return partial

        return await _work()

    def build_success_result(
        self,
        slug: str,
        *,
        source_paths: list[str] | None = None,
        row_counts: dict[str, int] | None = None,
        excel_path: str | None = None,
        pdf_path: str | None = None,
        archive_path: str | None = None,
        processor_used: str | None = None,
        input_row_count: int | None = None,
        processed_row_count: int | None = None,
        ingestion_success: bool = True,
        source_csv_path: str | None = None,
        source_row_count: int | None = None,
        output_columns: list[str] | None = None,
        visible_columns: list[str] | None = None,
        selected_column_ids: list[str] | None = None,
        column_order: list[str] | None = None,
        configuration_source: str | None = None,
    ) -> ReportResult:
        """Build a successful ReportResult with download URL."""
        key = canonicalize_report_key(slug)
        csv_path = source_csv_path or (source_paths[0] if source_paths else None)
        row_count = source_row_count
        if row_count is None and row_counts:
            row_count = next(iter(row_counts.values()), None)
        return ReportResult(
            slug=key,
            dataset_key=key,
            status="success",
            source_paths=source_paths or [],
            source_csv_path=csv_path,
            source_row_count=row_count,
            row_counts=row_counts or {},
            ingestion_success=ingestion_success,
            excel_path=excel_path,
            pdf_path=pdf_path,
            pdf_download_url=None,
            archive_path=archive_path,
            processing_attempted=True,
            processing_success=True,
            processor_used=processor_used,
            input_row_count=input_row_count,
            processed_row_count=processed_row_count,
            output_columns=output_columns,
            visible_columns=visible_columns,
            selected_column_ids=selected_column_ids,
            column_order=column_order,
            configuration_source=configuration_source,
            error=None,
        )

    def build_failed_result(
        self,
        slug: str,
        error: str,
        *,
        partial: bool = False,
        source_paths: list[str] | None = None,
        row_counts: dict[str, int] | None = None,
        ingestion_success: bool = False,
        source_csv_path: str | None = None,
        source_row_count: int | None = None,
    ) -> ReportResult:
        """Build a failed ReportResult."""
        key = canonicalize_report_key(slug)
        return ReportResult(
            slug=key,
            dataset_key=key,
            status="partial_success" if partial else "failed",
            source_paths=source_paths or [],
            source_csv_path=source_csv_path or (source_paths[0] if source_paths else None),
            source_row_count=source_row_count,
            row_counts=row_counts or {},
            ingestion_success=ingestion_success,
            error=error,
        )

    def build_skipped_result(self, slug: str, reason: str) -> ReportResult:
        """Build a skipped ReportResult."""
        key = canonicalize_report_key(slug)
        return ReportResult(
            slug=key,
            dataset_key=key,
            status="skipped",
            error=reason,
        )
