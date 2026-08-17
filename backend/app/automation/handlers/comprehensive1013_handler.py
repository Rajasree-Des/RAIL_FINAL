"""Report 10-13 handler: Comprehensive Reports with four sections.

Extracts from the same Comprehensive (with drill down) page four times:
- Report 10 (C&W): Department=Carriage & Wagon, Mode=Train
- Report 11 (Security): Type=Security-Train
- Report 12 (Punctuality): Type=Punctuality-Train
- Report 13 (Electrical Equipment): Type=Electrical Equipment-Train

All sections use Zone=South Central Railway, Division=ALL, View=Division Wise.
"""

from __future__ import annotations

import csv
import logging
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.automation.config import config
from app.automation.comprehensive1013_filters import (
    SectionConfig,
    get_all_section_configs,
)
from app.automation.generator import ReportGenerationError
from app.automation.portal_from_date import (
    apply_previous_from_date,
    log_phase1_submit_clicked,
)
from app.automation.reports import ReportDefinition
from app.automation.run_context import get_run_context
from app.automation.schemas import ReportResult
from app.automation.table_extractor import TableExtractor
from app.automation.page_wait import wait_for_portal_settle, wait_for_report_form_controls
from app.automation.railmadad_wait import verify_report_filters
from app.automation.table_refresh import require_fingerprint_changed, table_fingerprint
from app.automation.table_sort import ReceivedSortError
from app.automation.utils import ensure_directory, log_automation_event, resolve_report_dir
from app.automation.wait_utils import poll_until

from .base import BaseReportHandler

if TYPE_CHECKING:
    from playwright.async_api import Page

    from app.automation.session import SessionManager

logger = logging.getLogger(__name__)

SECTION_SUBMIT_MAX_ATTEMPTS = 2


class Comprehensive1013Handler(BaseReportHandler):
    """Execute Report 10-13 Comprehensive grouped report workflow."""

    async def execute(
        self,
        page: "Page",
        session: "SessionManager",
        report: ReportDefinition,
    ) -> ReportResult:
        started_at = datetime.now(UTC).isoformat()
        t0 = time.perf_counter()
        page = await self.ensure_mis_page(page, session, f"{report.slug}_start", report=report)
        section_configs = get_all_section_configs()

        ctx = get_run_context()
        run_id = ctx.run_id if ctx is not None else str(uuid.uuid4())
        if ctx is not None:
            ctx.freeze_report_from_date(report.slug)
        extracted_dir = ensure_directory(
            resolve_report_dir(config.extracted_data_dir, report.slug) / run_id
        )

        source_paths: list[str] = []
        row_counts: dict[str, int] = {}
        total_rows = 0
        section_results: list[dict[str, Any]] = []
        failed_sections: list[str] = []

        await self.navigation.navigate_to_report(page, report)
        page = await self.ensure_mis_page(page, session, f"{report.slug}_after_nav", report=report)
        try:
            await page.wait_for_selector("#complaintTypeInput, #viewType", timeout=15_000)
        except Exception:
            pass

        for section_config in section_configs:
            page = await self.ensure_mis_page(
                page, session, f"{report.slug}_{section_config.section_id}", report=report
            )
            outcome = await self._run_section_with_retry(
                page,
                session,
                report,
                section_config,
                extracted_dir,
            )
            page = outcome.get("page", page)
            section_results.append(outcome)

            if outcome.get("status") == "success" and outcome.get("csv_path"):
                source_paths.append(str(outcome["csv_path"]))
                rows = int(outcome.get("row_count") or 0)
                row_counts[section_config.section_id] = rows
                total_rows += rows
            else:
                failed_sections.append(section_config.section_id)

        if not source_paths:
            return self.build_failed_result(
                report.slug,
                "No section data extracted",
                row_counts=row_counts,
            )

        combined_path = extracted_dir / "comprehensive_combined_index.csv"
        self._write_combined_index(combined_path, section_results)
        log_automation_event(
            logger,
            "comprehensive1013_index_saved",
            path=str(combined_path),
            success_count=len(source_paths),
            failed_sections=failed_sections,
            run_id=run_id,
        )

        extraction_seconds = time.perf_counter() - t0
        log_automation_event(
            logger,
            "report_extraction_completed",
            slug=report.slug,
            section_count=len(source_paths),
            total_rows=total_rows,
            failed_sections=failed_sections,
            duration_seconds=round(extraction_seconds, 3),
        )

        saved_defer: bool | None = None
        if ctx is not None:
            saved_defer = ctx.defer_processing
            ctx.defer_processing = False
        t_proc = time.perf_counter()
        try:
            result = await self.finalize_after_extract(
                slug=report.slug,
                csv_path=combined_path,
                source_paths=source_paths,
                row_counts=row_counts,
                source_row_count=total_rows,
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

        log_automation_event(
            logger,
            "ingestion:comprehensive-10-13",
            path=str(combined_path),
            ingestion_success=result.ingestion_success,
        )
        log_automation_event(
            logger,
            "processing:comprehensive-10-13",
            excel_path=result.excel_path,
            pdf_path=result.pdf_path,
            processing_success=result.processing_success,
            duration_seconds=round(processing_seconds, 3),
        )
        if ctx is not None:
            ctx.timing.spans["processing:comprehensive-10-13"] = round(processing_seconds, 3)
            ctx.timing.record_report_span("comprehensive-10-13", "processing", processing_seconds)

        if failed_sections and result.status == "success":
            result = result.model_copy(
                update={
                    "status": "partial_success",
                    "error": f"Failed sections: {', '.join(failed_sections)}",
                }
            )
            if ctx is not None:
                ctx.merge_result(result)

        if result.pdf_preview_url or result.excel_download_url:
            log_automation_event(
                logger,
                "comprehensive1013_artifacts_registered",
                pdf_preview_url=result.pdf_preview_url,
                pdf_download_url=result.pdf_download_url,
                excel_download_url=result.excel_download_url,
                excel_path=result.excel_path,
                pdf_path=result.pdf_path,
            )

        return result

    def _write_combined_index(
        self,
        combined_path: Path,
        section_results: list[dict[str, Any]],
    ) -> None:
        with combined_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["section_id", "section_name", "csv_path", "row_count", "status", "error"])
            for outcome in section_results:
                writer.writerow(
                    [
                        outcome.get("section_id", ""),
                        outcome.get("section_name", ""),
                        outcome.get("csv_path") or "",
                        outcome.get("row_count") or 0,
                        outcome.get("status", "failed"),
                        outcome.get("error") or "",
                    ]
                )

    async def _run_section_with_retry(
        self,
        page: "Page",
        session: "SessionManager",
        report: ReportDefinition,
        section_config: SectionConfig,
        extracted_dir: Path,
    ) -> dict[str, Any]:
        """Submit/sort/extract one section; retry once with full reacquire on failure."""
        log_automation_event(
            logger,
            "comprehensive1013_section_started",
            section_id=section_config.section_id,
            section_name=section_config.name,
        )
        last_error: str | None = None

        for attempt in range(1, SECTION_SUBMIT_MAX_ATTEMPTS + 1):
            try:
                if attempt > 1:
                    log_automation_event(
                        logger,
                        "comprehensive1013_section_retry",
                        section_id=section_config.section_id,
                        attempt=attempt,
                    )
                    page = await self.ensure_mis_page(
                        page,
                        session,
                        f"{report.slug}_{section_config.section_id}_retry_{attempt}",
                    )
                    await self.navigation.navigate_to_report(page, report)
                    page = await self.ensure_mis_page(
                        page,
                        session,
                        f"{report.slug}_{section_config.section_id}_retry_nav",
                    )
                    try:
                        await page.wait_for_selector(
                            "#complaintTypeInput, #viewType",
                            timeout=15_000,
                        )
                    except Exception:
                        pass

                report_root = await self._submit_section_once(
                    page, session, report, section_config, attempt=attempt
                )
                await self._wait_for_received_header(page, section_config.section_id)
                await self._sort_received(report_root, page, report.slug, section_config.section_id)
                csv_path, row_count = await self._extract_section(
                    report_root, report, section_config, extracted_dir
                )
                log_automation_event(
                    logger,
                    "comprehensive1013_section_completed",
                    section_id=section_config.section_id,
                    row_count=row_count,
                    csv_path=str(csv_path),
                    attempt=attempt,
                )
                return {
                    "section_id": section_config.section_id,
                    "section_name": section_config.name,
                    "csv_path": str(csv_path),
                    "row_count": row_count,
                    "status": "success",
                    "error": "",
                    "page": page,
                }
            except Exception as exc:
                last_error = str(exc)
                log_automation_event(
                    logger,
                    "comprehensive1013_section_failed",
                    section_id=section_config.section_id,
                    attempt=attempt,
                    error=last_error,
                )
                await self._save_section_failure_artifacts(
                    page, section_config.section_id, attempt, last_error
                )
                report_root = await self.filter_service.get_report_root(page)
                await wait_for_portal_settle(
                    report_root,
                    page,
                    timeout_seconds=min(0.5 * attempt, 2.0),
                    reason="comprehensive1013_section_retry",
                    report_slug="comprehensive-10-13",
                )

        return {
            "section_id": section_config.section_id,
            "section_name": section_config.name,
            "csv_path": "",
            "row_count": 0,
            "status": "failed",
            "error": last_error or "unknown",
            "page": page,
        }

    async def _submit_section_once(
        self,
        page: "Page",
        session: "SessionManager",
        report: ReportDefinition,
        section_config: SectionConfig,
        *,
        attempt: int,
    ) -> Any:
        """Apply full filters, submit, wait for genuine table refresh."""
        page = await self.ensure_mis_page(
            page, session, f"{report.slug}_{section_config.section_id}_before_submit"
        )

        report_root = await self.filter_service.get_report_root(page)
        await wait_for_report_form_controls(page, report_slug=report.slug)

        log_automation_event(
            logger,
            "comprehensive1013_applying_filters_fast",
            section_id=section_config.section_id,
            expected_department=section_config.department,
            expected_mode=section_config.mode,
            expected_type=section_config.complaint_type,
        )

        applied_values = await self._apply_filters_fast(
            report_root, page, section_config
        )

        self._verify_core_filters(applied_values, section_config)

        ctx = get_run_context()
        run_id = ctx.run_id if ctx is not None else ""
        await apply_previous_from_date(
            page,
            run_id,
            report.slug,
            section_config.section_id,
            filter_service=self.filter_service,
        )
        log_phase1_submit_clicked(
            run_id,
            report.slug,
            section_config.section_id,
        )

        old_fp = await table_fingerprint(report_root)
        log_automation_event(
            logger,
            "comprehensive1013_section_submit",
            section_id=section_config.section_id,
            attempt=attempt,
            old_fingerprint=old_fp[:120] if old_fp else "",
        )

        await self.generator.generate_report(report_root, page, report_slug=report.slug)

        new_fp = await table_fingerprint(report_root)
        require_fingerprint_changed(old_fp, new_fp, report_slug=report.slug)

        expected_filters = {
            "zone": "South Central Railway",
            "division": "ALL",
            "view": "Division Wise",
        }
        if section_config.complaint_type and section_config.complaint_type != "ALL":
            expected_filters["type"] = section_config.complaint_type
        filter_err = await verify_report_filters(
            report_root,
            expected_filters,
            report_slug=report.slug,
        )
        if filter_err:
            raise ReportGenerationError(filter_err)

        if not await self._wait_for_report_displayed(report_root, page):
            raise ReportGenerationError(
                f"Report {report.slug} did not display after generate"
            )

        log_automation_event(
            logger,
            "comprehensive1013_new_table_verified",
            section_id=section_config.section_id,
            attempt=attempt,
            refreshed=True,
        )
        return report_root

    async def _wait_for_report_displayed(
        self,
        report_root: Any,
        page: "Page",
        *,
        timeout_seconds: float = 12.0,
    ) -> bool:
        """Poll until the results table/grid is visible after submit redraw."""

        async def _visible() -> bool:
            return await self.generator.verify_report_displayed(report_root)

        return await poll_until(
            _visible,
            interval_seconds=0.15,
            timeout_seconds=timeout_seconds,
            reason="comprehensive1013_display_poll",
        )

    @staticmethod
    def _verify_core_filters(applied_values: dict[str, str], section_config: SectionConfig) -> None:
        """Verify that core filters were applied correctly. Fail-closed for critical mismatches.

        Raises ReportGenerationError with specific error codes when filters don't match.
        This ensures we never extract a table with wrong filters applied.
        """
        view_applied = str(applied_values.get("view") or "")
        if view_applied and "division" not in view_applied.lower():
            log_automation_event(
                logger,
                "comprehensive1013_filter_mismatch",
                section_id=section_config.section_id,
                filter_name="view",
                expected="Division Wise",
                actual=view_applied,
            )
            raise ReportGenerationError(
                f"COMPREHENSIVE_VIEW_FILTER_NOT_APPLIED: "
                f"expected 'Division Wise', got '{view_applied}'"
            )

        zone_applied = str(applied_values.get("zone") or "")
        if zone_applied and "south central" not in zone_applied.lower() and "scr" not in zone_applied.lower():
            log_automation_event(
                logger,
                "comprehensive1013_filter_mismatch",
                section_id=section_config.section_id,
                filter_name="zone",
                expected="South Central Railway",
                actual=zone_applied,
            )
            raise ReportGenerationError(
                f"COMPREHENSIVE_ZONE_FILTER_NOT_APPLIED: "
                f"expected 'South Central Railway', got '{zone_applied}'"
            )

        dept_applied = str(applied_values.get("department") or "")
        expected_dept = section_config.department.lower()
        dept_matches = (
            expected_dept == "all"
            or expected_dept in dept_applied.lower()
            or ("carriage" in expected_dept and "carriage" in dept_applied.lower())
            or ("wagon" in expected_dept and "wagon" in dept_applied.lower())
            or ("c&w" in expected_dept and ("c&w" in dept_applied.lower() or "carriage" in dept_applied.lower()))
        )
        if not dept_matches:
            section_upper = section_config.section_id.upper().replace("_", "")
            log_automation_event(
                logger,
                "comprehensive1013_filter_mismatch",
                section_id=section_config.section_id,
                filter_name="department",
                expected=section_config.department,
                actual=dept_applied,
            )
            raise ReportGenerationError(
                f"{section_upper}_DEPARTMENT_FILTER_NOT_APPLIED: "
                f"expected '{section_config.department}', got '{dept_applied}'"
            )

        mode_applied = str(applied_values.get("mode") or "")
        expected_mode = section_config.mode.lower()
        mode_matches = (
            expected_mode == "all"
            or expected_mode in mode_applied.lower()
            or mode_applied.lower() in expected_mode
        )
        if not mode_matches:
            section_upper = section_config.section_id.upper().replace("_", "")
            log_automation_event(
                logger,
                "comprehensive1013_filter_mismatch",
                section_id=section_config.section_id,
                filter_name="mode",
                expected=section_config.mode,
                actual=mode_applied,
            )
            raise ReportGenerationError(
                f"{section_upper}_MODE_FILTER_NOT_APPLIED: "
                f"expected '{section_config.mode}', got '{mode_applied}'"
            )

        type_applied = str(applied_values.get("type") or "")
        expected_type = section_config.complaint_type.lower()
        type_matches = (
            expected_type == "all"
            or expected_type in type_applied.lower()
            or type_applied.lower() in expected_type
            or (expected_type.replace("-", " ").replace("  ", " ") in type_applied.lower().replace("-", " ").replace("  ", " "))
        )
        if not type_matches:
            section_upper = section_config.section_id.upper().replace("_", "")
            log_automation_event(
                logger,
                "comprehensive1013_filter_mismatch",
                section_id=section_config.section_id,
                filter_name="type",
                expected=section_config.complaint_type,
                actual=type_applied,
            )
            raise ReportGenerationError(
                f"{section_upper}_TYPE_FILTER_NOT_APPLIED: "
                f"expected '{section_config.complaint_type}', got '{type_applied}'"
            )

        log_automation_event(
            logger,
            "comprehensive1013_filters_verified",
            section_id=section_config.section_id,
            view=view_applied,
            zone=zone_applied,
            department=dept_applied,
            mode=mode_applied,
            type=type_applied,
        )

    async def _apply_filters_fast(
        self,
        report_root: Any,
        page: "Page",
        section_config: SectionConfig,
    ) -> dict[str, str]:
        """Apply section filters using staged approach for cascading dropdown handling.

        Applies filters in stages with waits between Department/Mode/Type changes
        to handle portal's cascading dropdown refresh behavior.

        Returns the applied values dict for verification.
        """
        applied_values: dict[str, str] = {}

        # Stage 1: Apply base filters (these don't cause cascading refreshes)
        base_js = """() => {
            const results = {};
            const selectByLabel = (sel, targetLabels) => {
                const el = document.querySelector(sel);
                if (!el || el.tagName !== 'SELECT') return null;
                const labels = Array.isArray(targetLabels) ? targetLabels : [targetLabels];
                
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

            results.zone = selectByLabel('#complaintZoneInput', ['South Central Railway', 'SCR']);
            results.division = selectByLabel('#complaintDivInput', ['ALL', 'All']);
            results.view = selectByLabel('#viewType', ['Division Wise', 'DivisionWise']);
            results.sub_type = selectByLabel('#complaintSubTypeInput', ['ALL', 'All']);
            results.excluding_assistance_cases = selectByLabel('#assistanceInput', ['Yes', 'YES']);
            results.excluding_refund_cases = selectByLabel('#refundInput', ['YES', 'Yes']);
            results.excluding_inquiry_cases = selectByLabel('#inquiryInput', ['Yes', 'YES']);
            results.channel_type = selectByLabel('#channelTypeInput', ['ALL', 'All']);
            results.train_type = selectByLabel('#trainTypeInput', ['ALL', 'All']);

            return results;
        }"""

        base_values = await report_root.evaluate(base_js)
        applied_values.update(base_values)
        await wait_for_portal_settle(
            report_root, page, reason="base_filters_settle", report_slug="comprehensive-10-13"
        )

        log_automation_event(
            logger,
            "comprehensive1013_base_filters_applied",
            section_id=section_config.section_id,
            base_values=base_values,
        )

        # Stage 2: Apply Department (may trigger Type dropdown refresh)
        dept_labels = (
            ["ALL", "All"]
            if section_config.department.lower() == "all"
            else [section_config.department, "Carriage & Wagon", "Carriage And Wagon", "C&W"]
        )
        dept_result = await report_root.evaluate(
            """(labels) => {
                const el = document.querySelector('#complaintDeptInput');
                if (!el || el.tagName !== 'SELECT') return '';
                
                for (const label of labels) {
                    const labelLower = label.toLowerCase().trim();
                    for (let i = 0; i < el.options.length; i++) {
                        const optText = (el.options[i].text || '').trim();
                        if (optText.toLowerCase() === labelLower || 
                            optText.toLowerCase().includes(labelLower)) {
                            el.selectedIndex = i;
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                            return optText;
                        }
                    }
                }
                return el.options[el.selectedIndex]?.text || '';
            }""",
            dept_labels,
        )
        applied_values["department"] = dept_result
        await wait_for_portal_settle(
            report_root, page, reason="department_change_settle", report_slug="comprehensive-10-13"
        )

        log_automation_event(
            logger,
            "comprehensive1013_department_applied",
            section_id=section_config.section_id,
            department=dept_result,
        )

        # Stage 3: Apply Mode (may trigger Type dropdown refresh)
        mode_labels = (
            ["ALL", "All"]
            if section_config.mode.lower() == "all"
            else [section_config.mode, "Train", "TRAIN"]
        )
        mode_result = await report_root.evaluate(
            """(labels) => {
                const el = document.querySelector('#complaintModeInput');
                if (!el || el.tagName !== 'SELECT') return '';
                
                for (const label of labels) {
                    const labelLower = label.toLowerCase().trim();
                    for (let i = 0; i < el.options.length; i++) {
                        const optText = (el.options[i].text || '').trim();
                        if (optText.toLowerCase() === labelLower || 
                            optText.toLowerCase().includes(labelLower)) {
                            el.selectedIndex = i;
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                            return optText;
                        }
                    }
                }
                return el.options[el.selectedIndex]?.text || '';
            }""",
            mode_labels,
        )
        applied_values["mode"] = mode_result
        await wait_for_portal_settle(
            report_root, page, reason="mode_change_settle", report_slug="comprehensive-10-13"
        )

        log_automation_event(
            logger,
            "comprehensive1013_mode_applied",
            section_id=section_config.section_id,
            mode=mode_result,
        )

        # Stage 4: Wait for Type dropdown options to stabilize after Dept/Mode changes
        await self._wait_for_type_dropdown_stable(report_root, section_config.section_id)

        # Stage 5: Apply Type with exact portal labels (including space after hyphen)
        type_result = await self._select_type_with_verification(
            report_root, page, section_config
        )
        applied_values["type"] = type_result

        log_automation_event(
            logger,
            "comprehensive1013_filters_applied_staged",
            section_id=section_config.section_id,
            applied_values=applied_values,
        )

        return applied_values

    async def _wait_for_type_dropdown_stable(
        self,
        report_root: Any,
        section_id: str,
    ) -> None:
        """Wait for Type dropdown options to stabilize after Dept/Mode changes."""
        state = {"prev_count": -1, "stable_checks": 0}

        async def _stable() -> bool:
            current_count = await report_root.evaluate(
                """() => {
                    const el = document.querySelector('#complaintTypeInput');
                    return el ? el.options.length : 0;
                }"""
            )
            if current_count == state["prev_count"] and current_count > 0:
                state["stable_checks"] += 1
                return state["stable_checks"] >= 2
            state["prev_count"] = current_count
            state["stable_checks"] = 0
            return False

        ok = await poll_until(
            _stable,
            interval_seconds=0.08,
            timeout_seconds=3.0,
            reason="type_dropdown_stabilize",
        )
        if ok:
            log_automation_event(
                logger,
                "comprehensive1013_type_dropdown_stable",
                section_id=section_id,
                option_count=state["prev_count"],
            )
        else:
            log_automation_event(
                logger,
                "comprehensive1013_type_dropdown_stabilize_timeout",
                section_id=section_id,
                final_count=state["prev_count"],
            )

    async def _select_type_with_verification(
        self,
        report_root: Any,
        page: "Page",
        section_config: SectionConfig,
    ) -> str:
        """Select Type value and verify selection with exact portal labels.

        Uses exact portal labels including the space after hyphen format:
        - Security- Train
        - Punctuality- Train
        - Electrical Equipment- Train
        """
        target_type = section_config.complaint_type

        if target_type.lower() == "all":
            type_labels = ["ALL", "All"]
        else:
            # Include exact portal labels with space after hyphen
            type_labels = [
                target_type,
                target_type.replace("-", "- "),       # Security-Train -> Security- Train
                target_type.replace("-", " - "),      # Security-Train -> Security - Train
                target_type.replace("-Train", "- Train"),  # Security-Train -> Security- Train
                target_type.replace("-Train", " - Train"),
                # Exact portal labels observed in screenshot
                "Security- Train",
                "Punctuality- Train",
                "Electrical Equipment- Train",
            ]

        # Log available Type options before selection
        available_options = await report_root.evaluate(
            """() => {
                const el = document.querySelector('#complaintTypeInput');
                if (!el) return [];
                return Array.from(el.options).map(o => ({
                    value: o.value,
                    text: o.text.trim()
                }));
            }"""
        )

        log_automation_event(
            logger,
            "comprehensive1013_type_options_available",
            section_id=section_config.section_id,
            target_type=target_type,
            available_options=available_options[:15] if available_options else [],
        )

        # Select Type with fresh locator query
        type_result = await report_root.evaluate(
            """(labels) => {
                const el = document.querySelector('#complaintTypeInput');
                if (!el || el.tagName !== 'SELECT') return { selected: '', success: false };
                
                // Priority 1: Exact match
                for (const label of labels) {
                    const labelLower = label.toLowerCase().trim();
                    for (let i = 0; i < el.options.length; i++) {
                        const optText = (el.options[i].text || '').trim();
                        if (optText.toLowerCase() === labelLower) {
                            el.selectedIndex = i;
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                            return { selected: optText, success: true, matchType: 'exact' };
                        }
                    }
                }
                
                // Priority 2: Option includes target (partial match)
                for (const label of labels) {
                    const labelLower = label.toLowerCase().trim();
                    if (labelLower === 'all') continue;  // Skip ALL for partial match
                    for (let i = 0; i < el.options.length; i++) {
                        const optText = (el.options[i].text || '').trim();
                        const optLower = optText.toLowerCase();
                        // Match if option contains key parts of the label
                        if (optLower.includes(labelLower) || 
                            (labelLower.includes('security') && optLower.includes('security')) ||
                            (labelLower.includes('punctuality') && optLower.includes('punctuality')) ||
                            (labelLower.includes('electrical') && optLower.includes('electrical'))) {
                            el.selectedIndex = i;
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                            return { selected: optText, success: true, matchType: 'partial' };
                        }
                    }
                }
                
                return { selected: el.options[el.selectedIndex]?.text || '', success: false };
            }""",
            type_labels,
        )

        selected_type = type_result.get("selected", "")
        success = type_result.get("success", False)
        match_type = type_result.get("matchType", "none")

        log_automation_event(
            logger,
            "comprehensive1013_type_selected",
            section_id=section_config.section_id,
            target_type=target_type,
            selected_type=selected_type,
            success=success,
            match_type=match_type,
        )

        # Verify Type selection for non-ALL sections
        if target_type.lower() != "all":
            readback = await report_root.evaluate(
                """() => {
                    const el = document.querySelector('#complaintTypeInput');
                    if (!el) return '';
                    return (el.options[el.selectedIndex]?.text || '').trim();
                }"""
            )

            if readback.lower() == "all":
                log_automation_event(
                    logger,
                    "comprehensive1013_type_selection_failed",
                    section_id=section_config.section_id,
                    target_type=target_type,
                    readback=readback,
                    available_options=available_options,
                )
                raise ReportGenerationError(
                    f"{section_config.section_id.upper()}_TYPE_STILL_ALL: "
                    f"expected '{target_type}', but Type is still 'ALL'. "
                    f"Available options: {[o.get('text') for o in (available_options or [])[:10]]}"
                )

        await wait_for_portal_settle(
            report_root,
            page,
            reason="type_selection_settle",
            report_slug="comprehensive-10-13",
        )
        return selected_type

    async def _reset_stale_filters(
        self,
        report_root: Any,
        page: "Page",
        section_config: SectionConfig,
    ) -> None:
        """Reset Department, Mode, and Type to ALL before applying section-specific filters.

        Uses fast JavaScript-based reset for speed optimization.
        """
        try:
            await report_root.evaluate("""() => {
                const selectors = ['#complaintDeptInput', '#complaintModeInput', '#complaintTypeInput'];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el && el.tagName === 'SELECT') {
                        for (let i = 0; i < el.options.length; i++) {
                            const txt = (el.options[i].text || '').trim().toUpperCase();
                            if (txt === 'ALL' || txt === '--ALL--') {
                                el.selectedIndex = i;
                                el.dispatchEvent(new Event('change', { bubbles: true }));
                                break;
                            }
                        }
                    }
                }
            }""")
            log_automation_event(
                logger,
                "comprehensive1013_filters_reset_fast",
                section_id=section_config.section_id,
            )
        except Exception as exc:
            log_automation_event(
                logger,
                "comprehensive1013_filter_reset_failed",
                section_id=section_config.section_id,
                error=str(exc),
            )
        await wait_for_portal_settle(
            report_root,
            page,
            reason="filters_reset_settle",
            report_slug="comprehensive-10-13",
        )

    async def _wait_for_received_header(self, page: "Page", section_id: str) -> None:
        try:
            await page.locator(
                "th:has-text('Received'), td:has-text('Received')"
            ).first.wait_for(state="visible", timeout=15_000)
        except Exception:
            log_automation_event(
                logger,
                "comprehensive1013_received_header_wait_timeout",
                section_id=section_id,
            )

    async def _sort_received(
        self,
        report_root: Any,
        page: "Page",
        report_slug: str,
        section_id: str,
    ) -> None:
        try:
            await self.click_received_twice(
                report_root, page, report_slug=report_slug
            )
        except ReceivedSortError as exc:
            raise ReportGenerationError(
                f"Received descending sort failed for {section_id}: {exc}"
            ) from exc

    async def _extract_section(
        self,
        report_root: Any,
        report: ReportDefinition,
        section_config: SectionConfig,
        extracted_dir: Path,
    ) -> tuple[Path, int]:
        from app.automation.table_extractor import ExtractionResult

        extractor = TableExtractor(output_dir=extracted_dir)
        data = await extractor.extract_table_data(report_root)
        if not data:
            raise ReportGenerationError(
                f"Could not extract table data for {section_config.section_id}"
            )

        html = await extractor.extract_table_html(report_root)
        extraction_result = ExtractionResult(
            success=True,
            data=data,
            html=html,
            row_count=len(data),
            column_count=len(data[0]) if data else 0,
        )
        if await self.reject_empty_table(extraction_result):
            raise ReportGenerationError(
                f"Empty table for {section_config.section_id}"
            )

        csv_path = extracted_dir / f"{section_config.section_id}.csv"
        self._save_section_csv(data, csv_path)
        return csv_path, max(len(data) - 1, 0)

    async def _save_section_failure_artifacts(
        self,
        page: "Page",
        section_id: str,
        attempt: int,
        error: str,
    ) -> None:
        dest = ensure_directory(Path(config.screenshots_dir) / "comprehensive1013_failures")
        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        meta = dest / f"failure_{stamp}_{section_id}_attempt{attempt}.txt"
        meta.write_text(error, encoding="utf-8")
        try:
            html_path = dest / f"failure_{stamp}_{section_id}_attempt{attempt}.html"
            html_path.write_text(await page.content(), encoding="utf-8")
        except Exception:
            pass
        try:
            shot = dest / f"failure_{stamp}_{section_id}_attempt{attempt}.png"
            await page.screenshot(path=str(shot), full_page=True)
        except Exception:
            pass

    @staticmethod
    def _save_section_csv(data: list[list[str]], csv_path: Path) -> None:
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            for row in data:
                writer.writerow(row)
