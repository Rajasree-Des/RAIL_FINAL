"""Report Vande Bharat handler: MIS Report No. 18 — single-source extract."""

from __future__ import annotations

import csv
import logging
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.automation.config import config
from app.automation.generator import ReportGenerationError
from app.automation.portal_from_date import (
    PortalFromDateError,
    apply_previous_from_date,
    log_phase1_submit_clicked,
)
from app.automation.date_range import get_context_date_range
from app.automation.report18_detail_extract import (
    capture_report18_screenshot,
    extract_vande_bharat_detail,
    wait_for_vande_bharat_aggregate_table,
)
from app.automation.report18_filters import (
    REPORT_18_FILTERS,
    REPORT18_CSV_FILENAME,
    REPORT18_LOG_PREFIX,
    REPORT18_TAB_LABEL,
    REPORT18_URL_FRAGMENT,
    ZONE_SCR,
)
from app.automation.report18_navigation import (
    Report18NavigationError,
    navigate_report18_via_menu,
    resolve_report18_form_context,
    url_is_vande_bharat,
)
from app.automation.navigation import url_matches_report_fragment
from app.automation.reports import ReportDefinition
from app.automation.run_context import get_run_context
from app.automation.schemas import ReportResult
from app.automation.table_extractor import TableExtractor
from app.automation.table_validator import validate_extracted_data
from app.automation.utils import (
    ensure_directory,
    log_automation_event,
    resolve_report_dir,
)

from .base import BaseReportHandler

if TYPE_CHECKING:
    from playwright.async_api import Page

    from app.automation.session import SessionManager

logger = logging.getLogger(__name__)


def _log_step(message: str, **fields: Any) -> None:
    logger.info("%s %s", REPORT18_LOG_PREFIX, message)
    event = "report18_" + message.lower().replace(" ", "_")
    log_automation_event(logger, event, **fields)


class Report18Handler(BaseReportHandler):
    """Execute Report Vande Bharat (Report No. 18) workflow."""

    async def execute(
        self,
        page: "Page",
        session: "SessionManager",
        report: ReportDefinition,
    ) -> ReportResult:
        started_at = datetime.now(UTC).isoformat()
        t0 = time.perf_counter()
        # Session only — omit report= so ensure_mis_page does not URL-goto
        # a potentially blank report shell before menu navigation.
        page = await self.ensure_mis_page(page, session, f"{report.slug}_start")

        ctx = get_run_context()
        run_id = ctx.run_id if ctx is not None else str(uuid.uuid4())
        if ctx is not None:
            ctx.freeze_report_from_date(report.slug)

        extracted_dir = ensure_directory(
            resolve_report_dir(config.extracted_data_dir, report.slug) / run_id
        )

        _log_step("Opening Report 18", run_id=run_id)
        try:
            await navigate_report18_via_menu(page, run_id=run_id)
        except Report18NavigationError as exc:
            log_automation_event(
                logger,
                "report18_navigation_failed",
                error=str(exc),
                stage=getattr(exc, "stage", "report18_navigation"),
                url=page.url,
            )
            return self.build_failed_result(
                report.slug,
                f"REPORT18_NAVIGATION_FAILED: {exc}",
            )

        page = await self.ensure_mis_page(page, session, f"{report.slug}_after_nav")

        # --- Validation: report 18 page is open (never accept Comprehensive / report1) ---
        if url_matches_report_fragment(page.url, "mis_reports/report1") and not url_is_vande_bharat(
            page.url
        ):
            return self.build_failed_result(
                report.slug,
                "REPORT18_PAGE_NOT_OPEN: still on Comprehensive (report1); "
                "expected MIS Reports → 18) Vande Bharat Report "
                f"({REPORT18_URL_FRAGMENT})",
            )

        form_ctx = await resolve_report18_form_context(page)
        if form_ctx is None:
            return self.build_failed_result(
                report.slug,
                "REPORT18_PAGE_NOT_OPEN: Vande Bharat Train Report page is not open "
                f"(url={page.url})",
            )

        if not url_is_vande_bharat(page.url):
            # Heading matched but URL still wrong — refuse to extract from another tab.
            return self.build_failed_result(
                report.slug,
                "REPORT18_PAGE_NOT_OPEN: page URL is not vandebharatreport "
                f"(url={page.url})",
            )

        try:
            report_root = await self.filter_service.get_report_root(page)
        except Exception as exc:
            return self.build_failed_result(
                report.slug,
                f"REPORT18_PAGE_NOT_OPEN: could not resolve report root: {exc}",
            )

        # Wait for date inputs / form controls (Playwright waits, not hardcoded sleep).
        for sel in ("#complaintZoneInput", "#fromInput", "#toInput", "form", "select"):
            try:
                await page.wait_for_selector(sel, state="attached", timeout=10_000)
                break
            except Exception:
                continue

        # Zone must be South Central Railway (other filters stay at portal defaults).
        try:
            applied = await self.filter_service.apply_filters(
                report_root,
                REPORT_18_FILTERS,
                page=page,
            )
            await self.filter_service.validate_mandatory(
                report_root, REPORT_18_FILTERS, applied
            )
            zone_ok, zone_err = await self._verify_zone_scr(report_root, page)
            if not zone_ok:
                # Fallback: set zone via DOM evaluate (same pattern as report9/14).
                await self._set_zone_js(report_root, ZONE_SCR)
                zone_ok, zone_err = await self._verify_zone_scr(report_root, page)
            if not zone_ok:
                return self.build_failed_result(
                    report.slug,
                    f"REPORT18_ZONE_FAILED: {zone_err}",
                )
            log_automation_event(
                logger,
                "report18_zone_applied",
                zone=ZONE_SCR,
                applied=applied,
            )
        except Exception as exc:
            return self.build_failed_result(
                report.slug,
                f"REPORT18_ZONE_FAILED: could not set Zone to {ZONE_SCR}: {exc}",
            )

        _log_step("Setting dates", run_id=run_id, tab=REPORT18_TAB_LABEL)
        try:
            await apply_previous_from_date(
                page,
                run_id,
                report.slug,
                "vande_bharat",
                filter_service=self.filter_service,
            )
        except PortalFromDateError as exc:
            return self.build_failed_result(
                report.slug,
                f"REPORT18_DATE_FAILED: {exc.code}: {exc}",
            )

        # --- Validation: dates populated correctly ---
        date_ok, date_err = await self._verify_dates_populated(page, report_root)
        if not date_ok:
            return self.build_failed_result(
                report.slug,
                f"REPORT18_DATE_MISMATCH: {date_err}",
            )

        log_phase1_submit_clicked(run_id, report.slug, "vande_bharat")
        _log_step("Filters submitted", run_id=run_id)
        _log_step("Clicking Submit", run_id=run_id)

        try:
            await self.generator.generate_report(report_root, page)
        except ReportGenerationError as exc:
            return self.build_failed_result(
                report.slug,
                f"REPORT18_SUBMIT_FAILED: {exc}",
            )

        _log_step("Waiting for report", run_id=run_id)
        if not await wait_for_vande_bharat_aggregate_table(page, report_root):
            try:
                await page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass
            if not await wait_for_vande_bharat_aggregate_table(
                page, report_root, timeout_ms=30_000
            ):
                await capture_report18_screenshot(page, "00_aggregate_table_missing")
                return self.build_failed_result(
                    report.slug,
                    "REPORT18_SUBMIT_FAILED: vande_bharat_aggregate_table_missing: "
                    "summary table with data rows did not load after Submit",
                )

        # --- Validation: summary table exists + at least one data row ---
        extractor = TableExtractor(output_dir=extracted_dir)
        data = await extractor.extract_table_data(report_root)
        validation = validate_extracted_data(data, required_headers=None, min_data_rows=1)
        if not validation.valid:
            return self.build_failed_result(
                report.slug,
                f"REPORT18_TABLE_INVALID: vande_bharat_aggregate_table_missing: "
                f"{validation.error or 'table missing or empty'}",
            )

        summary_csv_path = extracted_dir / REPORT18_CSV_FILENAME
        self._save_csv(data, summary_csv_path)
        summary_rows = max(len(data) - 1, 0)
        _log_step(
            "Summary loaded",
            run_id=run_id,
            row_count=summary_rows,
            csv_path=str(summary_csv_path),
            date_from=self._ctx_date_from(),
            date_to=self._ctx_date_to(),
        )

        # --- NEW: TOTAL Received drill-down → detailed Excel → mapped CSV ---
        detail = await extract_vande_bharat_detail(page, report_root, extracted_dir)
        if not detail.success or detail.detail_csv_path is None:
            return self.build_failed_result(
                report.slug,
                f"REPORT18_DETAIL_FAILED: {detail.error or 'detail extract failed'}",
                source_paths=[str(summary_csv_path)],
                row_counts={
                    "vande_bharat_summary": summary_rows,
                    "vande_bharat_summary_total": detail.summary_total or 0,
                },
                source_csv_path=str(summary_csv_path),
                source_row_count=summary_rows,
            )

        csv_path = detail.detail_csv_path
        data_rows = detail.detail_row_count
        _log_step(
            "Detailed complaints extracted",
            run_id=run_id,
            summary_total=detail.summary_total,
            detail_rows=data_rows,
            csv_path=str(csv_path),
        )

        extraction_seconds = time.perf_counter() - t0
        log_automation_event(
            logger,
            "report_extraction_completed",
            slug=report.slug,
            total_rows=data_rows,
            summary_total=detail.summary_total,
            duration_seconds=round(extraction_seconds, 3),
        )

        source_paths = [str(csv_path), str(summary_csv_path)]
        row_counts = {
            "vande_bharat": data_rows,
            "vande_bharat_summary": summary_rows,
            "vande_bharat_summary_total": detail.summary_total or 0,
        }

        saved_defer: bool | None = None
        if ctx is not None:
            saved_defer = ctx.defer_processing
            ctx.defer_processing = False
        t_proc = time.perf_counter()
        try:
            result = await self.finalize_after_extract(
                slug=report.slug,
                csv_path=csv_path,
                source_paths=source_paths,
                row_counts=row_counts,
                source_row_count=data_rows,
                started_at=started_at,
                extraction_seconds=round(extraction_seconds, 3),
            )
        finally:
            if ctx is not None and saved_defer is not None:
                ctx.defer_processing = saved_defer

        processing_seconds = time.perf_counter() - t_proc
        result = result.model_copy(
            update={"processing_seconds": round(processing_seconds, 3)}
        )

        if not result.ingestion_success:
            return self.build_failed_result(
                report.slug,
                "REPORT18_INGESTION_FAILED",
                source_paths=source_paths,
                row_counts=row_counts,
                source_csv_path=str(csv_path),
                source_row_count=data_rows,
            )

        if not result.processing_success:
            err = (result.error or "").upper()
            if "PDF" in err:
                code = "REPORT18_PDF_FAILED"
            elif "XLSX" in err or "EXCEL" in err:
                code = "REPORT18_XLSX_FAILED"
            else:
                code = result.error or "REPORT18_XLSX_FAILED"
            return self.build_failed_result(
                report.slug,
                code,
                source_paths=source_paths,
                row_counts=row_counts,
                ingestion_success=True,
                source_csv_path=str(csv_path),
                source_row_count=data_rows,
            )

        if result.excel_path:
            _log_step("Excel generated", excel_path=result.excel_path)
        if result.pdf_path:
            _log_step("PDF generated", pdf_path=result.pdf_path)

        log_automation_event(
            logger,
            "processing:report18",
            excel_path=result.excel_path,
            pdf_path=result.pdf_path,
            processing_success=result.processing_success,
            duration_seconds=round(processing_seconds, 3),
        )
        if ctx is not None:
            ctx.timing.spans["processing:report18"] = round(processing_seconds, 3)
            ctx.timing.record_report_span("report18", "processing", processing_seconds)

        _log_step("Completed", run_id=run_id, status=result.status)
        return result

    async def _verify_dates_populated(
        self,
        page: "Page",
        report_root: Any,
    ) -> tuple[bool, str]:
        """Confirm From/To date fields match the selected report date range."""
        expected = get_context_date_range()
        expected_from = expected.iso_from()
        expected_to = expected.iso_to()

        read_js = """() => {
            const read = (sels) => {
                for (const s of sels) {
                    const el = document.querySelector(s);
                    if (el && el.value) return String(el.value).trim();
                }
                return '';
            };
            return {
                from: read([
                    '#fromInput',
                    "div.fromDate input",
                    "label[for='fromInput'] + input",
                    "input[name*='from' i]",
                ]),
                to: read([
                    '#toInput',
                    "div.toDate input",
                    "label[for='toInput'] + input",
                    "input[name*='to' i]",
                ]),
            };
        }"""
        try:
            values = await report_root.evaluate(read_js)
        except Exception:
            try:
                values = await page.evaluate(read_js)
            except Exception as exc:
                return False, f"could not read date fields: {exc}"

        actual_from = str((values or {}).get("from") or "").strip()
        actual_to = str((values or {}).get("to") or "").strip()

        def _norm(value: str) -> str:
            text = (value or "").strip()
            # Accept dd-mm-yyyy or yyyy-mm-dd
            if len(text) >= 10 and text[2] == "-" and text[5] == "-":
                d, m, y = text[:2], text[3:5], text[6:10]
                return f"{y}-{m}-{d}"
            return text[:10]

        nf, nt = _norm(actual_from), _norm(actual_to)
        ef, et = expected_from[:10], expected_to[:10]
        if not nf or not nt:
            return False, f"date fields empty (from={actual_from!r}, to={actual_to!r})"
        if nf != ef or nt != et:
            return (
                False,
                f"expected from={ef} to={et}, actual from={nf} to={nt}",
            )
        return True, ""

    async def _verify_zone_scr(
        self,
        report_root: Any,
        page: "Page",
    ) -> tuple[bool, str]:
        """Confirm Zone select shows South Central Railway."""
        actual = await self._read_zone(report_root, page)
        if self._zone_matches_scr(actual):
            return True, ""
        return False, f"expected Zone={ZONE_SCR!r}, actual={actual!r}"

    async def _read_zone(self, report_root: Any, page: "Page") -> str:
        read_js = """() => {
            const sels = [
                '#complaintZoneInput',
                "select[name*='zone' i]",
                "select[id*='zone' i]",
            ];
            for (const s of sels) {
                const el = document.querySelector(s);
                if (el && el.tagName === 'SELECT') {
                    return (el.options[el.selectedIndex]?.text || el.value || '').trim();
                }
            }
            return '';
        }"""
        try:
            return str(await report_root.evaluate(read_js) or "").strip()
        except Exception:
            try:
                return str(await page.evaluate(read_js) or "").strip()
            except Exception:
                return ""

    async def _set_zone_js(self, report_root: Any, zone: str) -> None:
        await report_root.evaluate(
            """(zone) => {
              const sels = [
                '#complaintZoneInput',
                "select[name*='zone' i]",
                "select[id*='zone' i]",
              ];
              let el = null;
              for (const s of sels) {
                el = document.querySelector(s);
                if (el && el.tagName === 'SELECT') break;
                el = null;
              }
              if (!el) return false;
              const target = (zone || '').toLowerCase().trim();
              for (let i = 0; i < el.options.length; i++) {
                const text = (el.options[i].text || '').trim();
                if (text.toLowerCase() === target) {
                  el.selectedIndex = i;
                  el.dispatchEvent(new Event('change', { bubbles: true }));
                  el.dispatchEvent(new Event('input', { bubbles: true }));
                  return true;
                }
              }
              for (let i = 0; i < el.options.length; i++) {
                const text = (el.options[i].text || '').trim();
                if (text.toLowerCase().includes(target) || target.includes(text.toLowerCase())) {
                  el.selectedIndex = i;
                  el.dispatchEvent(new Event('change', { bubbles: true }));
                  el.dispatchEvent(new Event('input', { bubbles: true }));
                  return true;
                }
              }
              return false;
            }""",
            zone,
        )

    @staticmethod
    def _zone_matches_scr(actual: str) -> bool:
        a = (actual or "").strip().lower()
        if not a:
            return False
        if a == ZONE_SCR.lower():
            return True
        if "south central" in a or a in {"scr", "s.c.railway", "s.c. railway"}:
            return True
        return False

    @staticmethod
    def _save_csv(data: list[list[str]], csv_path: Path) -> None:
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            for row in data:
                writer.writerow(row)

    @staticmethod
    def _ctx_date_from() -> str | None:
        ctx = get_run_context()
        if ctx is None or ctx.date_range is None:
            return None
        return ctx.date_range.iso_from()

    @staticmethod
    def _ctx_date_to() -> str | None:
        ctx = get_run_context()
        if ctx is None or ctx.date_range is None:
            return None
        return ctx.date_range.iso_to()
