"""Report 5 handler: SCR Train Mode Unsatisfactory modal extraction."""

from __future__ import annotations

import csv
import logging
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from app.automation.config import config
from app.automation.formatting.scr import mode_matches
from app.automation.report5_filters import REPORT_5_FILTERS
from app.automation.reports import ReportDefinition
from app.automation.schemas import ReportResult
from app.automation.table_extractor import FEEDBACK_ZONE_REQUIRED_HEADERS
from app.automation.scr_field_map import (
    REPORT5_CANONICAL_CSV_HEADERS,
    build_csv_fieldnames,
    canonicalize_scr_rows,
    verify_scr_csv,
)
from app.automation.utils import ensure_directory, log_automation_event, resolve_report_dir, resolve_run_scoped_dir
from app.automation.wait_utils import poll_until, tracked_sleep
from app.automation.run_context import get_run_context

from .base import BaseReportHandler

if TYPE_CHECKING:
    from playwright.async_api import Page

    from app.automation.session import SessionManager

logger = logging.getLogger(__name__)

ZONE_WISE_HEADERS = list(FEEDBACK_ZONE_REQUIRED_HEADERS)


class Report5Handler(BaseReportHandler):
    """Execute Report 5 SCR Train Unsatisfactory workflow."""

    expected_mode = "Train"
    scr_report_num = 5
    canonical_csv_headers = REPORT5_CANONICAL_CSV_HEADERS
    _last_unsatisfactory_percent: float | None = None

    async def execute(
        self,
        page: "Page",
        session: "SessionManager",
        report: ReportDefinition,
    ) -> ReportResult:
        started_at = datetime.now(UTC).isoformat()
        t0 = time.perf_counter()
        ctx = get_run_context()
        if ctx is not None:
            ctx.freeze_report_from_date(report.slug)
        page = await self.ensure_mis_page(page, session, f"{report.slug}_start", report=report)
        await self.navigation.navigate_to_report(page, report)
        page = await self.ensure_mis_page(page, session, f"{report.slug}_after_nav", report=report)

        report_root, _, _ = await self.apply_filters_and_submit(
            page,
            report,
            filters=REPORT_5_FILTERS,
            session=session,
            source_name="scr_train_feedback",
        )
        log_automation_event(
            logger,
            "phase3_table_refreshed",
            run_id=ctx.run_id if ctx is not None else "",
            report_slug=report.slug,
            source_name="scr_train_feedback",
            mode="Train",
        )
        await self.click_received_twice(
            report_root, page, feedback=True, report_slug=report.slug
        )

        expected_count, complaints, error = await self._extract_scr_complaints(
            page, report_root, report.slug
        )

        page = await self.ensure_mis_page(
            page, session, f"{report.slug}_after_modal", report=report
        )

        if error:
            prefix = "REPORT5_FRESH_EXTRACTION_FAILED"
            log_automation_event(
                logger,
                "phase3_terminal_status",
                run_id=ctx.run_id if ctx is not None else "",
                report_slug=report.slug,
                status="failed",
                failure_stage="extraction",
                error=f"{prefix}: {error}",
            )
            return self.build_failed_result(report.slug, f"{prefix}: {error}")

        csv_path = self._save_complaints_csv(complaints, report.slug)
        validation_error = await self._validate_scr_extraction(
            page, report.slug, complaints, csv_path
        )
        if validation_error:
            return validation_error

        source_paths = [str(csv_path)]
        row_counts: dict[str, int | float] = {
            "unsatisfactory": len(complaints),
            "expected": expected_count,
        }
        if self._last_unsatisfactory_percent is not None:
            row_counts["unsatisfactory_percent"] = self._last_unsatisfactory_percent

        if len(complaints) != expected_count:
            return self.build_failed_result(
                report.slug,
                f"Count mismatch: expected {expected_count}, got {len(complaints)}",
                partial=bool(complaints),
                source_paths=source_paths,
                row_counts=row_counts,
                source_csv_path=str(csv_path),
                source_row_count=len(complaints),
            )

        await self.archive_pdf(page, report_root, report.slug, session=session)

        extraction_seconds = time.perf_counter() - t0
        log_automation_event(
            logger,
            "report_extraction_completed",
            slug=report.slug,
            extracted_count=len(complaints),
            expected_count=expected_count,
            unsatisfactory_percent=self._last_unsatisfactory_percent,
            duration_seconds=round(extraction_seconds, 3),
        )
        log_automation_event(
            logger,
            "phase3_rows_extracted",
            run_id=ctx.run_id if ctx is not None else "",
            report_slug=report.slug,
            extracted_count=len(complaints),
            expected_count=expected_count,
            mode=self.expected_mode,
        )
        result = await self.finalize_after_extract(
            slug=report.slug,
            csv_path=csv_path,
            source_paths=source_paths,
            row_counts=row_counts,
            source_row_count=len(complaints),
            ingest_source="scr_modal_csv",
            started_at=started_at,
            extraction_seconds=round(extraction_seconds, 3),
        )
        log_automation_event(
            logger,
            "phase3_terminal_status",
            run_id=ctx.run_id if ctx is not None else "",
            report_slug=report.slug,
            status=result.status,
            failure_stage=None if result.status == "success" else "finalize",
        )
        return result

    async def _extract_scr_complaints(
        self,
        page: "Page",
        report_root,
        report_slug: str,
    ) -> tuple[int, list[dict[str, str]], str | None]:
        table = await self._find_zone_wise_table(report_root)
        if table is None:
            return 0, [], "Zone Wise table not found"

        expected_count, target_row_idx = await self._get_scr_unsatisfactory_target(table)
        if expected_count == 0 or target_row_idx is None:
            return 0, [], "SCR Unsatisfactory count is 0 or not found"

        if not await self._click_unsatisfactory_row(page, table, target_row_idx):
            return expected_count, [], "Failed to open complaints modal"

        log_automation_event(
            logger,
            "phase3_details_opened",
            report_slug=report_slug,
            mode=self.expected_mode,
            expected_count=expected_count,
        )

        complaints = await self._extract_modal_pages(page)
        await self._close_modal(page)

        # Prefer Mode-column filter; portal uses T/S (or Train/Station).
        if complaints and any(k.lower() == "mode" for k in complaints[0]):
            mode_key = next(k for k in complaints[0] if k.lower() == "mode")
            filtered = [
                row
                for row in complaints
                if self._mode_matches(row.get(mode_key, ""))
            ]
        else:
            filtered = complaints

        return expected_count, filtered, None

    def _mode_matches(self, mode_value: str) -> bool:
        """Match portal Mode codes (T/S) or full labels (Train/Station)."""
        return mode_matches(self.expected_mode, mode_value)

    async def _find_zone_wise_table(self, report_root):
        tables = report_root.locator("table")
        count = await tables.count()
        for idx in range(count):
            table = tables.nth(idx)
            headers = await self._extract_table_headers(table)
            if self._is_zone_wise_table(headers):
                return table
        return None

    async def _extract_table_headers(self, table, page: "Page | None" = None) -> list[str]:
        headers: list[str] = []
        if page is not None:
            try:
                js_headers = await page.evaluate(
                    """(tableEl) => {
                      if (!tableEl) return [];
                      const seen = new Set();
                      const out = [];
                      const push = (text) => {
                        const t = (text || '').replace(/\\s+/g, ' ').trim();
                        if (t && !seen.has(t)) { seen.add(t); out.push(t); }
                      };
                      tableEl.querySelectorAll('thead th, thead td').forEach(el => push(el.textContent));
                      if (out.length) return out;
                      const first = tableEl.querySelector('tr');
                      if (first) first.querySelectorAll('th, td').forEach(el => push(el.textContent));
                      return out;
                    }""",
                    await table.element_handle(),
                )
                if js_headers:
                    return list(js_headers)
            except Exception:
                pass
        # Prefer explicit thead
        thead_cells = table.locator("thead tr").first.locator("th, td")
        if await table.locator("thead tr").count() > 0 and await thead_cells.count() > 0:
            for idx in range(await thead_cells.count()):
                headers.append((await thead_cells.nth(idx).inner_text()).strip())
            return headers

        # Fallback: first row that looks like headers
        first_row = table.locator("tr").first
        cells = first_row.locator("th, td")
        for idx in range(await cells.count()):
            headers.append((await cells.nth(idx).inner_text()).strip())
        return headers

    @staticmethod
    def _is_zone_wise_table(headers: list[str]) -> bool:
        joined = " | ".join(headers).lower()
        has_org = "organisation" in joined or "organization" in joined
        has_feedback = "feedback received" in joined
        has_unsat = "unsatisfactory" in joined
        # Department-wise table usually lists departments; still has Organisation header.
        # Prefer the first matching feedback table (zone/division view when Zone=SCR).
        return has_org and has_feedback and has_unsat

    def _column_index(self, headers: list[str], *names: str) -> int | None:
        lower = [h.lower() for h in headers]
        for name in names:
            for idx, header in enumerate(lower):
                if name.lower() == header or name.lower() in header:
                    return idx
        return None

    @staticmethod
    def _parse_percent(text: str) -> float | None:
        cleaned = (text or "").strip().replace("%", "").replace(",", "")
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            digits = re.sub(r"[^\d.]", "", cleaned)
            if not digits:
                return None
            try:
                return float(digits)
            except ValueError:
                return None

    async def _read_row_percent(
        self, cells, percent_idx: int | None
    ) -> float | None:
        if percent_idx is None:
            return None
        if await cells.count() <= percent_idx:
            return None
        return self._parse_percent(await cells.nth(percent_idx).inner_text())

    async def _get_scr_unsatisfactory_target(
        self, table
    ) -> tuple[int, int | None]:
        """Return (count, row_index) for SCR or Total row.

        Also sets ``_last_unsatisfactory_percent`` from the same target row's
        ``% Unsatisfactory`` cell when available.
        """
        self._last_unsatisfactory_percent = None
        headers = await self._extract_table_headers(table)
        org_idx = self._column_index(headers, "Organisation", "Organization")
        unsat_idx = self._column_index(headers, "Unsatisfactory")
        # Prefer exact "% Unsatisfactory" over substring match on "Unsatisfactory"
        percent_idx = self._column_index(headers, "% Unsatisfactory")
        if percent_idx is None:
            for idx, header in enumerate(headers):
                if header.strip().lower().startswith("%") and "unsatisfactory" in header.lower():
                    percent_idx = idx
                    break
        if org_idx is None or unsat_idx is None:
            # Common layout with leading S.No.
            org_idx = 1 if len(headers) > 1 else 0
            unsat_idx = 6 if len(headers) > 6 else 5
            if percent_idx is None and len(headers) > 7:
                percent_idx = 7

        rows = table.locator("tbody tr, tfoot tr")
        row_count = await rows.count()
        # If Total is outside tbody/tfoot, also scan all tr except header
        if row_count == 0:
            rows = table.locator("tr")
            row_count = await rows.count()
        total_row_idx: int | None = None
        total_count = 0
        total_percent: float | None = None
        scr_row_idx: int | None = None
        scr_count = 0
        scr_percent: float | None = None

        start = 0
        # Skip header row if scanning all tr
        first_cells = rows.nth(0).locator("th, td") if row_count else None
        if first_cells is not None and await first_cells.count() > 0:
            first_text = (await first_cells.nth(0).inner_text()).strip().lower()
            if first_text in {"s.no.", "s.no", "organisation", "organization"}:
                start = 1

        for idx in range(start, row_count):
            row = rows.nth(idx)
            cells = row.locator("td")
            cell_count = await cells.count()
            if cell_count <= max(org_idx, unsat_idx):
                continue
            org_text = (await cells.nth(org_idx).inner_text()).strip()
            unsat_text = (await cells.nth(unsat_idx).inner_text()).strip()
            digits = re.sub(r"[^\d]", "", unsat_text)
            try:
                count = int(digits) if digits else 0
            except ValueError:
                count = 0
            percent = await self._read_row_percent(cells, percent_idx)

            org_lower = org_text.lower()
            if (
                "south central railway" in org_lower
                or org_text.strip().upper() == "SCR"
                or org_lower == "south central"
            ):
                scr_row_idx = idx
                scr_count = count
                scr_percent = percent
            if org_lower == "total" or org_lower.startswith("total"):
                total_row_idx = idx
                total_count = count
                total_percent = percent

        # Fallback: if Zone is SCR-filtered and no Total/SCR row, sum division Unsatisfactory
        if scr_row_idx is None and total_row_idx is None and row_count > start:
            summed = 0
            last_data_idx = None
            for idx in range(start, row_count):
                row = rows.nth(idx)
                cells = row.locator("td")
                if await cells.count() <= unsat_idx:
                    continue
                org_text = (await cells.nth(org_idx).inner_text()).strip().lower()
                if not org_text or org_text == "total":
                    continue
                unsat_text = (await cells.nth(unsat_idx).inner_text()).strip()
                digits = re.sub(r"[^\d]", "", unsat_text)
                if not digits:
                    continue
                try:
                    summed += int(digits)
                    last_data_idx = idx
                except ValueError:
                    continue
            if summed > 0:
                # Prefer clicking Total if present as a linkable cell elsewhere;
                # otherwise click first row with a link in Unsatisfactory column.
                for idx in range(start, row_count):
                    row = rows.nth(idx)
                    cells = row.locator("td")
                    if await cells.count() <= unsat_idx:
                        continue
                    link = cells.nth(unsat_idx).locator("a")
                    if await link.count() > 0:
                        self._last_unsatisfactory_percent = await self._read_row_percent(
                            cells, percent_idx
                        )
                        return summed, idx
                if last_data_idx is not None:
                    cells = rows.nth(last_data_idx).locator("td")
                    self._last_unsatisfactory_percent = await self._read_row_percent(
                        cells, percent_idx
                    )
                return summed, last_data_idx

        if scr_row_idx is not None and scr_count > 0:
            self._last_unsatisfactory_percent = scr_percent
            return scr_count, scr_row_idx
        if total_row_idx is not None and total_count > 0:
            self._last_unsatisfactory_percent = total_percent
            return total_count, total_row_idx
        return 0, None

    async def _click_unsatisfactory_row(
        self, page: "Page", table, row_idx: int
    ) -> bool:
        headers = await self._extract_table_headers(table)
        unsat_idx = self._column_index(headers, "Unsatisfactory")
        if unsat_idx is None:
            unsat_idx = 6

        # Use same row set as _get_scr_unsatisfactory_target (tbody + tfoot)
        rows = table.locator("tbody tr, tfoot tr")
        if await rows.count() == 0:
            rows = table.locator("tr")
        row = rows.nth(row_idx)
        cells = row.locator("td")
        if await cells.count() <= unsat_idx:
            return False

        # Prefer explicit UNSAT drill link when present
        unsat_link = row.locator("a.drill[id*='UNSAT'], a[id*='UNSAT']")
        if await unsat_link.count() > 0:
            await unsat_link.first.click()
        else:
            unsat_cell = cells.nth(unsat_idx)
            link = unsat_cell.locator("a")
            if await link.count() > 0:
                await link.first.click()
            else:
                await unsat_cell.click()

        try:
            await page.wait_for_selector(
                ".modal.show, .modal.fade.show, #exampleModal.show",
                timeout=20000,
            )
            # Wait for modal data rows (DataTables loads async)
            await page.wait_for_selector(
                "#exampleModal table tbody tr td, .modal.show table tbody tr td",
                timeout=20000,
            )
            return True
        except Exception:
            return False

    async def _click_unsatisfactory(self, page: "Page", table) -> bool:
        _, row_idx = await self._get_scr_unsatisfactory_target(table)
        if row_idx is None:
            return False
        return await self._click_unsatisfactory_row(page, table, row_idx)

    async def _extract_modal_page_rows(
        self, page: "Page", modal_table, headers: list[str]
    ) -> list[dict[str, str]]:
        """Extract all visible modal rows in one browser evaluate (includes hidden cells)."""
        try:
            handle = await modal_table.element_handle()
            if handle is None:
                return []
            payload = await page.evaluate(
                """(tableEl) => {
                  if (!tableEl) return { headers: [], rows: [] };
                  const norm = (t) => (t || '').replace(/\\s+/g, ' ').trim();
                  const headerEls = tableEl.querySelectorAll('thead th, thead td');
                  let headers = [...headerEls].map(el => norm(el.textContent)).filter(Boolean);
                  if (!headers.length) {
                    const first = tableEl.querySelector('tr');
                    if (first) {
                      headers = [...first.querySelectorAll('th, td')]
                        .map(el => norm(el.textContent)).filter(Boolean);
                    }
                  }
                  const rows = [];
                  tableEl.querySelectorAll('tbody tr').forEach(tr => {
                    const cells = [...tr.querySelectorAll('td')].map(el => norm(el.textContent));
                    if (cells.length >= 3) rows.push(cells);
                  });
                  return { headers, rows };
                }""",
                handle,
            )
        except Exception:
            return []

        if not isinstance(payload, dict):
            return []
        js_headers = list(payload.get("headers") or [])
        effective_headers = js_headers if js_headers else headers
        page_rows: list[dict[str, str]] = []
        for cells in payload.get("rows") or []:
            if not isinstance(cells, list):
                continue
            row_data: dict[str, str] = {}
            for col_idx, value in enumerate(cells):
                header = (
                    effective_headers[col_idx]
                    if col_idx < len(effective_headers)
                    else f"Col{col_idx}"
                )
                row_data[header] = str(value or "").strip()
            if row_data:
                page_rows.append(row_data)
        return page_rows

    async def _read_modal_portal_total(self, page: "Page") -> int | None:
        """Parse DataTables info text, e.g. 'Showing 1 to 6 of 6 entries'."""
        import re

        try:
            text = await page.evaluate(
                """() => {
                  const el = document.querySelector(
                    '.modal.show .dataTables_info, #exampleModal .dataTables_info, ' +
                    '.modal .dataTables_info, .dataTables_info'
                  );
                  return el ? (el.textContent || '') : '';
                }"""
            )
        except Exception:
            return None
        if not text:
            return None
        match = re.search(r"of\s+([\d,]+)\s+entries", str(text), flags=re.IGNORECASE)
        if not match:
            return None
        try:
            return int(match.group(1).replace(",", ""))
        except ValueError:
            return None

    async def _extract_modal_pages(self, page: "Page") -> list[dict[str, str]]:
        all_complaints: list[dict[str, str]] = []
        seen_refs: set[str] = set()

        while True:
            modal_table = page.locator(
                "#exampleModal.show table, .modal.show table, "
                ".modal table, [role='dialog'] table"
            ).first

            try:
                await modal_table.wait_for(state="visible", timeout=5000)
            except Exception:
                break

            headers = await self._extract_table_headers(modal_table, page)
            try:
                await page.wait_for_function(
                    """() => {
                      const t = document.querySelector('#exampleModal.show table tbody, .modal.show table tbody');
                      return t && t.querySelectorAll('tr').length > 0;
                    }""",
                    timeout=10000,
                )
            except Exception:
                pass

            page_rows = await self._extract_modal_page_rows(page, modal_table, headers)
            if not page_rows:
                break

            for row_data in page_rows:
                ref_no = row_data.get("Ref. No.", "")
                if ref_no and ref_no not in seen_refs:
                    seen_refs.add(ref_no)
                    all_complaints.append(row_data)

            next_button = page.locator(
                ".modal.show .dataTables_paginate .next:not(.disabled), "
                ".pagination .next:not(.disabled), "
                "button:has-text('Next'):not([disabled]), "
                "a:has-text('Next'):not(.disabled)"
            )
            if await next_button.count() > 0 and await next_button.first.is_visible():
                await next_button.first.click()
                advanced = await poll_until(
                    lambda: self._modal_has_rows(page),
                    interval_seconds=0.08,
                    timeout_seconds=3.0,
                    reason="scr_modal_pagination",
                )
                if not advanced:
                    await tracked_sleep(0.08, reason="scr_modal_pagination_fallback")
            else:
                break

        return all_complaints

    async def _modal_has_rows(self, page: "Page") -> bool:
        return (await self._modal_row_count(page)) > 0

    async def _modal_row_count(self, page: "Page") -> int:
        try:
            count = await page.evaluate(
                """() => {
                  const t = document.querySelector('#exampleModal.show table tbody, .modal.show table tbody');
                  return t ? t.querySelectorAll('tr').length : 0;
                }"""
            )
            return int(count or 0)
        except Exception:
            return 0

    async def _close_modal(self, page: "Page") -> None:
        close_buttons = page.locator(
            ".modal.show .close, .modal.show .btn-close, "
            "[role='dialog'] button[aria-label='Close'], "
            ".modal button:has-text('Close')"
        )
        if await close_buttons.count() > 0:
            await close_buttons.first.click()
            try:
                await page.wait_for_selector(".modal.show", state="hidden", timeout=5000)
            except Exception:
                pass

    async def _validate_scr_extraction(
        self,
        page: "Page",
        report_slug: str,
        complaints: list[dict[str, str]],
        csv_path: Path,
    ) -> ReportResult | None:
        verification = verify_scr_csv(
            complaints,
            report_num=self.scr_report_num,
            report_slug=report_slug,
            source_csv_path=str(csv_path),
        )
        log_automation_event(
            logger,
            "scr_csv_verification",
            slug=report_slug,
            source_csv_path=str(csv_path),
            source_row_count=verification.row_count,
            source_headers=verification.source_headers,
            canonical_fields_mapped=verification.canonical_fields_mapped,
            missing_required_fields=verification.missing_required_fields,
            empty_required_fields=verification.empty_required_fields,
            sample_values=verification.sample_values,
        )
        if complaints and not verification.ok:
            await self._save_extraction_debug_artifacts(page, report_slug, verification)
            missing = verification.missing_required_fields + verification.empty_required_fields
            return self.build_failed_result(
                report_slug,
                f"SCR extraction missing required fields: {', '.join(missing)}",
                source_paths=[str(csv_path)],
                source_csv_path=str(csv_path),
                source_row_count=len(complaints),
            )
        return None

    async def _save_extraction_debug_artifacts(
        self,
        page: "Page",
        report_slug: str,
        verification,
    ) -> None:
        debug_dir = ensure_directory(Path(config.debug_screenshots_dir))
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        try:
            screenshot = debug_dir / f"scr_extract_fail_{report_slug}_{timestamp}.png"
            await page.screenshot(path=str(screenshot), full_page=True)
        except Exception:
            pass
        try:
            html_path = debug_dir / f"scr_extract_fail_{report_slug}_{timestamp}.html"
            html_path.write_text(await page.content(), encoding="utf-8")
        except Exception:
            pass
        try:
            import json

            meta_path = debug_dir / f"scr_extract_fail_{report_slug}_{timestamp}_headers.json"
            meta_path.write_text(
                json.dumps(
                    {
                        "source_headers": verification.source_headers,
                        "missing_required_fields": verification.missing_required_fields,
                        "empty_required_fields": verification.empty_required_fields,
                        "canonical_fields_mapped": verification.canonical_fields_mapped,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _uses_run_scoped_extract(self) -> bool:
        from app.automation.run_context import get_run_context
        from app.features.reports.scr_fresh import is_scr_manual_fresh

        ctx = get_run_context()
        if ctx is None:
            return False
        return is_scr_manual_fresh(ctx.manual_config)

    def _save_complaints_csv(
        self,
        complaints: list[dict[str, str]],
        report_slug: str,
    ) -> Path:
        from app.automation.run_context import get_run_context

        ctx = get_run_context()
        if self._uses_run_scoped_extract() and ctx is not None:
            extracted_dir = ensure_directory(
                resolve_run_scoped_dir(config.extracted_data_dir, report_slug, ctx.run_id)
            )
            log_automation_event(
                logger,
                "current_run_source_saved",
                run_id=ctx.run_id,
                report_slug=report_slug,
                source_dir=str(extracted_dir),
            )
        else:
            extracted_dir = ensure_directory(resolve_report_dir(config.extracted_data_dir, report_slug))
        csv_path = extracted_dir / f"{report_slug}_complaints_raw.csv"

        if not complaints:
            csv_path.write_text(
                ",".join(self.canonical_csv_headers) + "\n",
                encoding="utf-8",
            )
        else:
            canonical_rows = canonicalize_scr_rows(complaints)
            headers = build_csv_fieldnames(complaints)

            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
                writer.writeheader()
                for row in canonical_rows:
                    writer.writerow({h: row.get(h, "") for h in headers})

        if ctx is not None and self._uses_run_scoped_extract():
            ctx.current_run_sources[report_slug] = str(csv_path.resolve())
            log_automation_event(
                logger,
                "current_run_source_verified",
                run_id=ctx.run_id,
                report_slug=report_slug,
                source_path=str(csv_path),
                row_count=len(complaints),
            )

        return csv_path
