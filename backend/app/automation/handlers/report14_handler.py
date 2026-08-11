"""Report 14 handler: Train Watering Complaints — Previous + Upcoming dual extract."""

from __future__ import annotations

import csv
import logging
import re
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.automation.config import config
from app.automation.filters import (
    FilterError,
    discover_and_log_fields,
    save_filter_failure_artifacts,
)
from app.automation.generator import ReportGenerationError
from app.automation.portal_from_date import (
    apply_previous_from_date,
    log_phase1_submit_clicked,
)
from app.automation.report14_filters import (
    ALL_SOURCE_CONFIGS,
    REPORT14_REQUIRED_HEADERS,
    REPORT14_TAB_LABEL,
    SECTION_ORDER,
    SOURCE_PREVIOUS_LABEL,
    SOURCE_UPCOMING_LABEL,
    VIEW_DIVISION_WISE,
    ZONE_SCR,
    Report14SourceConfig,
)
from app.automation.report14_navigation import (
    Report14NavigationError,
    navigate_report14_via_menu,
)
from app.automation.reports import ReportDefinition
from app.automation.run_context import get_run_context
from app.automation.schemas import ReportResult
from app.automation.table_extractor import TableExtractor
from app.automation.table_sort import ReceivedSortError
from app.automation.utils import (
    ensure_directory,
    log_automation_event,
    resolve_report_dir,
)
from app.automation.wait_utils import tracked_sleep

from .base import BaseReportHandler

if TYPE_CHECKING:
    from playwright.async_api import Page

    from app.automation.session import SessionManager

logger = logging.getLogger(__name__)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).lower()


class Report14Handler(BaseReportHandler):
    """Execute Report 14 dual-source watering complaints workflow."""

    async def execute(
        self,
        page: "Page",
        session: "SessionManager",
        report: ReportDefinition,
    ) -> ReportResult:
        started_at = datetime.now(UTC).isoformat()
        t0 = time.perf_counter()
        # Session only — omit report= so ensure_mis_page does not URL-goto report11
        # (that leaves a blank shell; tab-11 menu navigation loads the form).
        page = await self.ensure_mis_page(page, session, f"{report.slug}_start")

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
        failed_sources: list[str] = []

        # Menu navigation only — direct report11 URL leaves a blank shell.
        try:
            await navigate_report14_via_menu(page, run_id=run_id)
        except Report14NavigationError as exc:
            log_automation_event(
                logger,
                "report14_tab11_navigation_failed",
                error=str(exc),
                stage=getattr(exc, "stage", "report14_tab11_navigation"),
                url=page.url,
            )
            return self.build_failed_result(
                report.slug,
                f"report14_tab11_navigation: {exc}",
            )

        page = await self.ensure_mis_page(page, session, f"{report.slug}_after_nav")

        for cfg in SECTION_ORDER:
            page = await self.ensure_mis_page(
                page, session, f"{report.slug}_{cfg.source_id}"
            )
            # Between sources: return to tab 11 if form is gone (do not URL-only goto).
            if cfg is not SECTION_ORDER[0]:
                try:
                    await navigate_report14_via_menu(page, run_id=run_id)
                except Report14NavigationError as exc:
                    section_results.append(
                        {
                            "source_id": cfg.source_id,
                            "section_title": cfg.section_title,
                            "watering_point": cfg.watering_point,
                            "csv_path": "",
                            "row_count": 0,
                            "status": "failed",
                            "error": f"{cfg.missing_error}: {exc}",
                            "page": page,
                        }
                    )
                    failed_sources.append(cfg.source_id)
                    continue
                page = await self.ensure_mis_page(
                    page, session, f"{report.slug}_{cfg.source_id}_renav"
                )
            outcome = await self._extract_source(
                page,
                session,
                report,
                cfg=cfg,
                extracted_dir=extracted_dir,
                run_id=run_id,
            )
            page = outcome.get("page", page)
            section_results.append(outcome)
            if outcome.get("status") == "success" and outcome.get("csv_path"):
                source_paths.append(str(outcome["csv_path"]))
                rows = int(outcome.get("row_count") or 0)
                row_counts[cfg.source_id] = rows
                total_rows += rows
            else:
                failed_sources.append(cfg.source_id)

        if failed_sources or len(source_paths) < len(ALL_SOURCE_CONFIGS):
            missing_errors = [
                o.get("error") or "REPORT14_TABLE_MISSING"
                for o in section_results
                if o.get("status") != "success"
            ]
            error_code = missing_errors[0] if missing_errors else "REPORT14_TABLE_MISSING"
            return self.build_failed_result(
                report.slug,
                error_code,
                source_paths=source_paths,
                row_counts=row_counts,
            )

        combined_path = extracted_dir / "report14_combined_index.csv"
        self._write_combined_index(combined_path, section_results)
        log_automation_event(
            logger,
            "report14_index_saved",
            path=str(combined_path),
            success_count=len(source_paths),
            run_id=run_id,
            tab=REPORT14_TAB_LABEL,
            date_from=self._ctx_date_from(),
            date_to=self._ctx_date_to(),
        )

        extraction_seconds = time.perf_counter() - t0
        log_automation_event(
            logger,
            "report_extraction_completed",
            slug=report.slug,
            section_count=len(source_paths),
            total_rows=total_rows,
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

        if not result.ingestion_success:
            return self.build_failed_result(
                report.slug,
                "REPORT14_INGESTION_FAILED",
                source_paths=source_paths,
                row_counts=row_counts,
                source_csv_path=str(combined_path),
                source_row_count=total_rows,
            )

        if not result.processing_success:
            err = (result.error or "").upper()
            if "PDF" in err:
                code = "REPORT14_PDF_FAILED"
            elif "XLSX" in err or "EXCEL" in err:
                code = "REPORT14_XLSX_FAILED"
            else:
                code = result.error or "REPORT14_XLSX_FAILED"
            return self.build_failed_result(
                report.slug,
                code,
                source_paths=source_paths,
                row_counts=row_counts,
                ingestion_success=True,
                source_csv_path=str(combined_path),
                source_row_count=total_rows,
            )

        log_automation_event(
            logger,
            "processing:report14",
            excel_path=result.excel_path,
            pdf_path=result.pdf_path,
            processing_success=result.processing_success,
            duration_seconds=round(processing_seconds, 3),
        )
        if ctx is not None:
            ctx.timing.spans["processing:report14"] = round(processing_seconds, 3)
            ctx.timing.record_report_span("report14", "processing", processing_seconds)

        return result

    def _write_combined_index(
        self,
        combined_path: Path,
        section_results: list[dict[str, Any]],
    ) -> None:
        with combined_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "source_id",
                    "section_title",
                    "watering_point",
                    "csv_path",
                    "row_count",
                    "status",
                    "error",
                ]
            )
            by_id = {r.get("source_id"): r for r in section_results}
            for cfg in SECTION_ORDER:
                outcome = by_id.get(cfg.source_id) or {
                    "source_id": cfg.source_id,
                    "section_title": cfg.section_title,
                    "watering_point": cfg.watering_point,
                    "csv_path": "",
                    "row_count": 0,
                    "status": "failed",
                    "error": cfg.missing_error,
                }
                writer.writerow(
                    [
                        outcome.get("source_id", cfg.source_id),
                        outcome.get("section_title", cfg.section_title),
                        outcome.get("watering_point", cfg.watering_point),
                        outcome.get("csv_path") or "",
                        outcome.get("row_count") or 0,
                        outcome.get("status", "failed"),
                        outcome.get("error") or "",
                    ]
                )

    async def _extract_source(
        self,
        page: "Page",
        session: "SessionManager",
        report: ReportDefinition,
        *,
        cfg: Report14SourceConfig,
        extracted_dir: Path,
        run_id: str,
    ) -> dict[str, Any]:
        source_name = cfg.source_id
        try:
            report_root = await self.filter_service.get_report_root(page)
            applied = await self._apply_and_verify_filters(
                report_root, page, cfg=cfg, report_slug=report.slug
            )
            log_automation_event(
                logger,
                "report14_filters_applied",
                source_id=cfg.source_id,
                applied_filters=applied,
            )

            await apply_previous_from_date(
                page,
                run_id,
                report.slug,
                source_name,
                filter_service=self.filter_service,
            )
            log_phase1_submit_clicked(run_id, report.slug, source_name)

            await self.generator.generate_report(report_root, page)
            await page.wait_for_timeout(800)
            if not await self.generator.verify_report_displayed(report_root):
                await page.wait_for_timeout(1500)
                if not await self.generator.verify_report_displayed(report_root):
                    raise ReportGenerationError(
                        f"Report {report.slug} did not display after generate ({source_name})"
                    )

            try:
                await self.click_received_twice(
                    report_root, page, report_slug=report.slug
                )
            except ReceivedSortError as exc:
                log_automation_event(
                    logger,
                    "report14_received_sort_failed",
                    source_id=source_name,
                    error=str(exc),
                )
                # Sort is best-effort — watering tables may not use DataTables.
                pass

            extractor = TableExtractor(output_dir=extracted_dir)
            data = await extractor.extract_table_data_by_headers(
                report_root,
                REPORT14_REQUIRED_HEADERS,
            )
            if not data:
                data = await extractor.extract_table_data(report_root)
            if not data or len(data) < 2:
                return {
                    "source_id": cfg.source_id,
                    "section_title": cfg.section_title,
                    "watering_point": cfg.watering_point,
                    "csv_path": "",
                    "row_count": 0,
                    "status": "failed",
                    "error": cfg.missing_error,
                    "page": page,
                }

            csv_path = extracted_dir / cfg.filename
            self._save_csv(data, csv_path)
            data_rows = max(len(data) - 1, 0)
            log_automation_event(
                logger,
                "report14_source_extracted",
                source_id=cfg.source_id,
                watering_point=cfg.watering_point,
                row_count=data_rows,
                csv_path=str(csv_path),
                tab=REPORT14_TAB_LABEL,
                date_from=self._ctx_date_from(),
                date_to=self._ctx_date_to(),
            )
            return {
                "source_id": cfg.source_id,
                "section_title": cfg.section_title,
                "watering_point": cfg.watering_point,
                "csv_path": str(csv_path),
                "row_count": data_rows,
                "status": "success",
                "error": "",
                "page": page,
            }
        except (FilterError, ReportGenerationError, ReceivedSortError) as exc:
            try:
                discovered = await discover_and_log_fields(
                    page, report.slug, missing_field=str(exc)
                )
                await save_filter_failure_artifacts(
                    page, report.slug, str(exc)[:80], discovered
                )
            except Exception:
                pass
            log_automation_event(
                logger,
                "report14_source_failed",
                source_id=cfg.source_id,
                error=str(exc),
            )
            return {
                "source_id": cfg.source_id,
                "section_title": cfg.section_title,
                "watering_point": cfg.watering_point,
                "csv_path": "",
                "row_count": 0,
                "status": "failed",
                "error": f"{cfg.missing_error}: {exc}",
                "page": page,
            }
        except Exception as exc:
            log_automation_event(
                logger,
                "report14_source_unexpected_error",
                source_id=cfg.source_id,
                error=str(exc),
            )
            return {
                "source_id": cfg.source_id,
                "section_title": cfg.section_title,
                "watering_point": cfg.watering_point,
                "csv_path": "",
                "row_count": 0,
                "status": "failed",
                "error": f"{cfg.missing_error}: {exc}",
                "page": page,
            }

    async def _apply_and_verify_filters(
        self,
        report_root: Any,
        page: "Page",
        *,
        cfg: Report14SourceConfig,
        report_slug: str,
    ) -> dict[str, str]:
        """Apply Zone/View/Division/Output via in-page JS and fail if not verified.

        Playwright select_option and compound label selectors can hang or skip on the
        Train Watering form; DOM evaluate + read-back matches comprehensive-10-13.
        """
        want_previous = "previous" in _norm(cfg.watering_point)
        output_labels = list(cfg.option_aliases)
        if want_previous and SOURCE_PREVIOUS_LABEL not in output_labels:
            output_labels.insert(0, SOURCE_PREVIOUS_LABEL)
        if not want_previous and SOURCE_UPCOMING_LABEL not in output_labels:
            output_labels.insert(0, SOURCE_UPCOMING_LABEL)

        # Wait briefly for core selects to attach after tab load.
        for sel in ("#complaintZoneInput", "#viewType", "#fromInput"):
            try:
                await page.wait_for_selector(sel, state="attached", timeout=8_000)
                break
            except Exception:
                continue

        apply_js = """(payload) => {
            const results = {};
            const selectByLabel = (selectors, targetLabels) => {
                const sels = Array.isArray(selectors) ? selectors : [selectors];
                let el = null;
                for (const s of sels) {
                    el = document.querySelector(s);
                    if (el && el.tagName === 'SELECT') break;
                    el = null;
                }
                if (!el) return null;
                const labels = Array.isArray(targetLabels) ? targetLabels : [targetLabels];
                for (const label of labels) {
                    const labelLower = String(label).toLowerCase().trim();
                    for (let i = 0; i < el.options.length; i++) {
                        const optText = (el.options[i].text || '').trim();
                        if (optText.toLowerCase() === labelLower) {
                            if (el.selectedIndex !== i) {
                                el.selectedIndex = i;
                                el.dispatchEvent(new Event('change', { bubbles: true }));
                                el.dispatchEvent(new Event('input', { bubbles: true }));
                            }
                            return optText;
                        }
                    }
                }
                for (const label of labels) {
                    const labelLower = String(label).toLowerCase().trim();
                    for (let i = 0; i < el.options.length; i++) {
                        const optText = (el.options[i].text || '').trim();
                        if (optText.toLowerCase().includes(labelLower)) {
                            if (el.selectedIndex !== i) {
                                el.selectedIndex = i;
                                el.dispatchEvent(new Event('change', { bubbles: true }));
                                el.dispatchEvent(new Event('input', { bubbles: true }));
                            }
                            return optText;
                        }
                    }
                }
                return (el.options[el.selectedIndex]?.text || '').trim();
            };

            const findSelectByRowLabel = (labelText) => {
                const needle = String(labelText).toLowerCase().trim();
                const nodes = document.querySelectorAll('tr, .form-group, .row, div, label, td, th');
                for (const node of nodes) {
                    const t = (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                    if (!t || t.length > 80) continue;
                    if (t === needle || t.startsWith(needle + ' ') || t === needle + ':') {
                        const sel = node.querySelector('select')
                            || (node.parentElement && node.parentElement.querySelector('select'))
                            || (node.closest('tr') && node.closest('tr').querySelector('select'));
                        if (sel && sel.tagName === 'SELECT') return sel;
                    }
                }
                return null;
            };

            const selectByRow = (rowLabel, targetLabels) => {
                const el = findSelectByRowLabel(rowLabel);
                if (!el) return null;
                const labels = Array.isArray(targetLabels) ? targetLabels : [targetLabels];
                for (const label of labels) {
                    const labelLower = String(label).toLowerCase().trim();
                    for (let i = 0; i < el.options.length; i++) {
                        const optText = (el.options[i].text || '').trim();
                        if (optText.toLowerCase() === labelLower || optText.toLowerCase().includes(labelLower)) {
                            if (el.selectedIndex !== i) {
                                el.selectedIndex = i;
                                el.dispatchEvent(new Event('change', { bubbles: true }));
                            }
                            return optText;
                        }
                    }
                }
                return (el.options[el.selectedIndex]?.text || '').trim();
            };

            results.zone = selectByLabel(
                ['#complaintZoneInput', "select[name*='zone' i]", "select[id*='zone' i]"],
                payload.zoneLabels
            ) || selectByRow('Zone', payload.zoneLabels);

            results.view = selectByLabel(
                ['#viewType', "select[name*='view' i]", "select[id*='view' i]"],
                payload.viewLabels
            ) || selectByRow('View', payload.viewLabels);

            results.sub_type = selectByLabel(
                ['#complaintSubTypeInput', "select[id*='subType' i]"],
                ['ALL', 'All']
            ) || selectByRow('Sub Type', ['ALL', 'All']);

            results.division = selectByLabel(
                ['#complaintDivInput', "select[id*='Div' i]", "select[name*='div' i]"],
                ['ALL', 'All', '--All--']
            ) || selectByRow('Division', ['ALL', 'All']);

            results.output = selectByLabel(
                [
                    '#outputTypeInput',
                    '#outputInput',
                    "select[id*='output' i]",
                    "select[name*='output' i]"
                ],
                payload.outputLabels
            ) || selectByRow('Output', payload.outputLabels);

            results.zoneOptionCount = (document.querySelector('#complaintZoneInput') || {options: []}).options.length || 0;
            results.viewOptionCount = (document.querySelector('#viewType') || {options: []}).options.length || 0;
            return results;
        }"""

        payload = {
            "zoneLabels": [ZONE_SCR, "SCR", "SOUTH CENTRAL RAILWAY"],
            "viewLabels": [VIEW_DIVISION_WISE, "DivisionWise", "DIVISION WISE"],
            "outputLabels": output_labels,
        }

        last_error: Exception | None = None
        applied: dict[str, Any] = {}
        for attempt in range(4):
            try:
                applied = await report_root.evaluate(apply_js, payload)
            except Exception:
                applied = await page.evaluate(apply_js, payload)

            if not isinstance(applied, dict):
                applied = {}

            # After Zone change, Division options may repopulate.
            await tracked_sleep(0.25, reason="report14_zone_cascade")
            try:
                div_applied = await report_root.evaluate(
                    """() => {
                        const el = document.querySelector('#complaintDivInput');
                        if (!el || el.tagName !== 'SELECT') return null;
                        for (let i = 0; i < el.options.length; i++) {
                            const t = (el.options[i].text || '').trim().toLowerCase();
                            if (t === 'all' || t === '--all--') {
                                el.selectedIndex = i;
                                el.dispatchEvent(new Event('change', { bubbles: true }));
                                return (el.options[i].text || '').trim();
                            }
                        }
                        return (el.options[el.selectedIndex]?.text || '').trim();
                    }"""
                )
                if div_applied:
                    applied["division"] = div_applied
            except Exception:
                pass

            # Re-apply Output after cascade in case the form reset it.
            try:
                out_re = await report_root.evaluate(
                    """(labels) => {
                        const selectors = [
                            '#outputTypeInput', '#outputInput',
                            "select[id*='output' i]", "select[name*='output' i]"
                        ];
                        let el = null;
                        for (const s of selectors) {
                            el = document.querySelector(s);
                            if (el && el.tagName === 'SELECT') break;
                            el = null;
                        }
                        if (!el) return null;
                        for (const label of labels) {
                            const ll = String(label).toLowerCase().trim();
                            for (let i = 0; i < el.options.length; i++) {
                                const t = (el.options[i].text || '').trim();
                                if (t.toLowerCase() === ll || t.toLowerCase().includes(ll)) {
                                    el.selectedIndex = i;
                                    el.dispatchEvent(new Event('change', { bubbles: true }));
                                    return t;
                                }
                            }
                        }
                        return (el.options[el.selectedIndex]?.text || '').trim();
                    }""",
                    output_labels,
                )
                if out_re:
                    applied["output"] = out_re
            except Exception:
                pass

            # Read-back from live selects (truth), not just what we tried to set.
            try:
                live = await report_root.evaluate(
                    """() => {
                        const read = (sel) => {
                            const el = document.querySelector(sel);
                            if (!el || el.tagName !== 'SELECT') return '';
                            return (el.options[el.selectedIndex]?.text || el.value || '').trim();
                        };
                        return {
                            zone: read('#complaintZoneInput'),
                            division: read('#complaintDivInput'),
                            view: read('#viewType'),
                            sub_type: read('#complaintSubTypeInput'),
                            output: read('#outputTypeInput')
                                || read('#outputInput')
                                || (() => {
                                    const all = Array.from(document.querySelectorAll('select'));
                                    for (const el of all) {
                                        const id = (el.id || el.name || '').toLowerCase();
                                        if (id.includes('output')) {
                                            return (el.options[el.selectedIndex]?.text || '').trim();
                                        }
                                    }
                                    return '';
                                })()
                        };
                    }"""
                )
                if isinstance(live, dict):
                    for key, val in live.items():
                        if val:
                            applied[key] = val
            except Exception:
                pass

            try:
                self._verify_core_filters(applied, cfg=cfg, report_slug=report_slug)
                last_error = None
                break
            except FilterError as exc:
                last_error = exc
                log_automation_event(
                    logger,
                    "report14_filter_retry",
                    attempt=attempt + 1,
                    error=str(exc),
                    applied=applied,
                )
                await tracked_sleep(0.4, reason="report14_filter_retry_wait")

        if last_error is not None:
            raise last_error

        log_automation_event(
            logger,
            "report14_filters_verified",
            report_slug=report_slug,
            source_id=cfg.source_id,
            applied=applied,
        )
        return {k: str(v) for k, v in applied.items() if v is not None and not str(k).endswith("OptionCount")}

    @staticmethod
    def _verify_core_filters(
        applied: dict[str, Any],
        *,
        cfg: Report14SourceConfig,
        report_slug: str,
    ) -> None:
        """Fail closed when Zone / View / Output were not applied correctly."""
        zone = str(applied.get("zone") or "")
        view = str(applied.get("view") or "")
        output = str(applied.get("output") or "")
        znorm = _norm(zone)
        vnorm = _norm(view)
        onorm = _norm(output)

        if not znorm or ("south central" not in znorm and znorm != "scr"):
            log_automation_event(
                logger,
                "report14_filter_mismatch",
                filter_name="zone",
                expected=ZONE_SCR,
                actual=zone,
                report_slug=report_slug,
            )
            raise FilterError(
                f"REPORT14_ZONE_FILTER_NOT_APPLIED: expected '{ZONE_SCR}', got '{zone}'"
            )

        if not vnorm or "division" not in vnorm:
            log_automation_event(
                logger,
                "report14_filter_mismatch",
                filter_name="view",
                expected=VIEW_DIVISION_WISE,
                actual=view,
                report_slug=report_slug,
            )
            raise FilterError(
                f"REPORT14_VIEW_FILTER_NOT_APPLIED: expected '{VIEW_DIVISION_WISE}', got '{view}'"
            )

        want_previous = "previous" in _norm(cfg.watering_point)
        output_ok = (
            ("previous" in onorm and want_previous)
            or (("upcoming" in onorm or "next" in onorm) and not want_previous)
            or any(_norm(a) in onorm or onorm in _norm(a) for a in cfg.option_aliases if a)
        )
        if not output_ok:
            log_automation_event(
                logger,
                "report14_filter_mismatch",
                filter_name="output",
                expected=cfg.watering_point,
                actual=output,
                report_slug=report_slug,
            )
            raise FilterError(
                f"REPORT14_OUTPUT_FILTER_NOT_APPLIED: expected '{cfg.watering_point}', got '{output}'"
            )

    async def _apply_watering_source(
        self,
        page: "Page",
        report_root: Any,
        *,
        cfg: Report14SourceConfig,
        report_slug: str,
    ) -> str:
        """Backward-compatible alias → full apply/verify path."""
        applied = await self._apply_and_verify_filters(
            report_root, page, cfg=cfg, report_slug=report_slug
        )
        return str(applied.get("output") or cfg.watering_point)

    @staticmethod
    def _save_csv(rows: list[list[str]], csv_path: Path) -> None:
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerows(rows)

    def _ctx_date_from(self) -> str:
        ctx = get_run_context()
        if ctx is None:
            return ""
        from app.automation.date_range import get_context_date_range

        try:
            return get_context_date_range().iso_from()
        except Exception:
            return ""

    def _ctx_date_to(self) -> str:
        ctx = get_run_context()
        if ctx is None:
            return ""
        from app.automation.date_range import get_context_date_range

        try:
            return get_context_date_range().iso_to()
        except Exception:
            return ""
