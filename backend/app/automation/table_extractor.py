"""HTML table extraction for Phase 7 automation."""

from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from playwright.async_api import FrameLocator, Locator, Page

from app.automation.config import config
from app.automation.filters import ReportRoot
from app.automation.selectors import selectors
from app.automation.table_validator import (
    TableValidationResult,
    get_required_headers_for_report,
    validate_extracted_data,
)
from app.automation.utils import (
    artifact_filename_timestamp,
    ensure_directory,
    log_automation_event,
)

logger = logging.getLogger(__name__)

FEEDBACK_ZONE_REQUIRED_HEADERS = frozenset(
    {
        "Organisation",
        "Feedback Received",
        "% Feedback",
        "Excellent",
        "Satisfactory",
        "Unsatisfactory",
        "% Unsatisfactory",
    }
)

# Division Wise Feedback table may use "Division" instead of "Organisation"
FEEDBACK_DIVISION_REQUIRED_HEADERS = frozenset(
    {
        "Feedback Received",
        "% Feedback",
        "Excellent",
        "Satisfactory",
        "Unsatisfactory",
        "% Unsatisfactory",
    }
)

# Headers that are equivalent (either one satisfies the requirement)
HEADER_ALIASES = {
    "organisation": {"division", "organisation"},
    "division": {"division", "organisation"},
}


@dataclass
class ExtractionResult:
    """Outcome of HTML table extraction."""

    success: bool
    html: str | None = None
    data: list[list[str]] | None = None
    csv_path: Path | None = None
    row_count: int = 0
    column_count: int = 0
    error: str | None = None
    validation_result: TableValidationResult | None = None


class TableExtractor:
    """Extracts rendered HTML table content from report pages."""

    def __init__(self, output_dir: Path | str | None = None) -> None:
        configured = output_dir or config.extracted_data_dir
        self.output_dir = ensure_directory(Path(configured).resolve())

    async def extract_table_html(self, root: ReportRoot) -> str | None:
        """Extract innerHTML of the report table."""
        table = await self._find_table(root)
        if table is None:
            log_automation_event(logger, "table_not_found", status="extraction_failed")
            return None

        try:
            html = await table.inner_html()
            log_automation_event(
                logger,
                "table_html_extracted",
                html_length=len(html),
            )
            return html
        except Exception as exc:
            log_automation_event(logger, "table_html_extraction_failed", error=str(exc))
            return None

    async def extract_table_data(self, root: ReportRoot) -> list[list[str]]:
        """Parse table rows/cells into structured data."""
        table = await self._find_table(root)
        if table is None:
            return []

        dt_rows = await self._extract_via_datatables(root, table)
        if dt_rows:
            return dt_rows

        batch_rows = await self._extract_table_data_batch(table)
        if batch_rows:
            return batch_rows

        rows: list[list[str]] = []

        try:
            thead = table.locator("thead tr")
            if await thead.count() > 0:
                header_row = await self._extract_row_cells(thead.first, "th")
                if not header_row:
                    header_row = await self._extract_row_cells(thead.first, "td")
                if header_row:
                    rows.append(header_row)

            tbody_rows = table.locator("tbody tr")
            row_count = await tbody_rows.count()

            if row_count == 0:
                all_rows = table.locator("tr")
                row_count = await all_rows.count()
                start_index = 1 if rows else 0
                for i in range(start_index, row_count):
                    row_data = await self._extract_row_cells(all_rows.nth(i), "td")
                    if row_data:
                        rows.append(row_data)
            else:
                for i in range(row_count):
                    row_data = await self._extract_row_cells(tbody_rows.nth(i), "td")
                    if row_data:
                        rows.append(row_data)

            log_automation_event(
                logger,
                "table_data_extracted",
                row_count=len(rows),
                column_count=len(rows[0]) if rows else 0,
            )
            return rows

        except Exception as exc:
            log_automation_event(logger, "table_data_extraction_failed", error=str(exc))
            return []

    async def _extract_via_datatables(
        self,
        root: ReportRoot,
        table: Locator,
    ) -> list[list[str]] | None:
        """If DataTables holds all rows client-side, dump via API (no pagination)."""
        try:
            page = table.page
            table_id = await table.get_attribute("id")
            payload = await page.evaluate(
                """(tableId) => {
                    const $ = window.jQuery || window.$;
                    if (!$ || !$.fn || !$.fn.dataTable) return null;
                    let api = null;
                    if (tableId && $.fn.dataTable.isDataTable('#' + tableId)) {
                        api = $('#' + tableId).DataTable();
                    } else {
                        const nodes = document.querySelectorAll('table.dataTable, table');
                        for (const node of nodes) {
                            if ($.fn.dataTable.isDataTable(node)) {
                                api = $(node).DataTable();
                                break;
                            }
                        }
                    }
                    if (!api) return null;
                    const info = api.page.info();
                    const pageLen = info.length;
                    const recordsTotal = info.recordsTotal || info.recordsDisplay || 0;
                    // -1 or length covering all displayed records => all client-side
                    const allClient =
                        pageLen === -1 ||
                        (pageLen > 0 && recordsTotal > 0 && pageLen >= recordsTotal) ||
                        (info.pages <= 1 && recordsTotal > 0);
                    if (!allClient) return { skip: true, recordsTotal, pageLen };
                    const headers = api.columns().header().toArray().map(
                        (h) => (h.textContent || '').trim()
                    );
                    const data = api.rows({ search: 'applied' }).data().toArray().map((row) => {
                        if (Array.isArray(row)) {
                            return row.map((cell) => {
                                if (cell == null) return '';
                                if (typeof cell === 'object' && cell.display != null) {
                                    return String(cell.display).trim();
                                }
                                return String(cell).replace(/<[^>]+>/g, ' ').replace(/\\s+/g, ' ').trim();
                            });
                        }
                        return Object.values(row).map((cell) =>
                            cell == null ? '' : String(cell).replace(/<[^>]+>/g, ' ').replace(/\\s+/g, ' ').trim()
                        );
                    });
                    return { headers, data, recordsTotal };
                }""",
                table_id,
            )
            if not payload or payload.get("skip"):
                return None
            headers = payload.get("headers") or []
            data = payload.get("data") or []
            if not headers or not data:
                return None
            rows = [list(headers)] + [list(r) for r in data]
            log_automation_event(
                logger,
                "table_data_extracted_datatables",
                row_count=len(rows),
                column_count=len(headers),
                records_total=payload.get("recordsTotal"),
            )
            return rows
        except Exception as exc:
            logger.debug("DataTables fast path unavailable: %s", exc)
            return None

    async def _extract_table_data_batch(self, table: Locator) -> list[list[str]] | None:
        """Single evaluate to read all visible table rows (fallback before cell-by-cell)."""
        try:
            payload = await table.evaluate(
                """(el) => {
                    const clean = (t) => (t || '').replace(/\\s+/g, ' ').trim();
                    const rows = [];
                    const headerCells = el.querySelectorAll('thead tr th, thead tr td');
                    if (headerCells.length) {
                        const hdr = Array.from(headerCells).map((c) => clean(c.textContent));
                        if (hdr.some(Boolean)) rows.push(hdr);
                    }
                    const bodyRows = el.querySelectorAll('tbody tr');
                    const trList = bodyRows.length ? bodyRows : el.querySelectorAll('tr');
                    const start = bodyRows.length ? 0 : (rows.length ? 1 : 0);
                    for (let i = start; i < trList.length; i++) {
                        const tr = trList[i];
                        const cells = tr.querySelectorAll('td, th');
                        if (!cells.length) continue;
                        const row = Array.from(cells).map((c) => clean(c.textContent));
                        const joined = row.join(' ').toLowerCase();
                        if (joined.includes('total') && row.length <= 3) continue;
                        if (row.some((c) => c.length > 0)) rows.push(row);
                    }
                    return rows.length ? rows : null;
                }"""
            )
            if not payload or len(payload) < 1:
                return None
            log_automation_event(
                logger,
                "table_data_extracted_batch",
                row_count=len(payload),
                column_count=len(payload[0]) if payload else 0,
            )
            return payload
        except Exception as exc:
            logger.debug("Batch table extract unavailable: %s", exc)
            return None

    async def _extract_row_cells(self, row: Locator, cell_tag: str) -> list[str]:
        """Extract text content from all cells in a row."""
        cells = row.locator(cell_tag)
        count = await cells.count()
        result: list[str] = []

        for i in range(count):
            try:
                text = await cells.nth(i).inner_text()
                cleaned = self._clean_cell_text(text)
                result.append(cleaned)
            except Exception:
                result.append("")

        return result

    @staticmethod
    def _clean_cell_text(text: str) -> str:
        """Clean extracted cell text."""
        cleaned = re.sub(r"\s+", " ", text.strip())
        return cleaned

    async def _find_table(self, root: ReportRoot) -> Locator | None:
        """Find the main report table in the page."""
        table_selectors = [
            selectors.report1_table,
            selectors.report1_grid,
            "table.dataTable",
            "table:has(tbody tr)",
            "#reportData table",
            ".report-table",
            "table",
        ]

        for selector in table_selectors:
            locator = root.locator(selector).first
            try:
                if await locator.count() > 0 and await locator.is_visible():
                    log_automation_event(
                        logger,
                        "table_found",
                        selector=selector,
                    )
                    return locator
            except Exception:
                continue

        return None

    @staticmethod
    def _normalize_header(text: str) -> str:
        return re.sub(r"\s+", " ", text.strip()).lower()

    def _headers_match_required(
        self,
        headers: list[str],
        required_headers: frozenset[str] | set[str],
    ) -> bool:
        normalized = {self._normalize_header(h) for h in headers}
        required = {self._normalize_header(h) for h in required_headers}
        return required.issubset(normalized)

    def _headers_match_required_with_aliases(
        self,
        headers: list[str],
        required_headers: frozenset[str] | set[str],
        require_org_or_division: bool = False,
    ) -> bool:
        """Match headers with support for Division/Organisation alias.

        If require_org_or_division is True, also checks that at least one of
        'organisation' or 'division' is present in the headers.
        """
        normalized = {self._normalize_header(h) for h in headers}
        required = {self._normalize_header(h) for h in required_headers}

        if not required.issubset(normalized):
            return False

        if require_org_or_division:
            has_org_or_div = "organisation" in normalized or "division" in normalized
            if not has_org_or_div:
                return False

        return True

    @staticmethod
    def _looks_like_department_wise(headers: list[str]) -> bool:
        normalized = {TableExtractor._normalize_header(h) for h in headers}
        has_department = any("department" in h for h in normalized)
        has_feedback_received = "feedback received" in normalized
        return has_department and not has_feedback_received

    async def _extract_rows_from_table(self, table: Locator) -> list[list[str]]:
        """Parse rows/cells from a specific table locator."""
        rows: list[list[str]] = []
        thead = table.locator("thead tr")
        if await thead.count() > 0:
            header_row = await self._extract_row_cells(thead.first, "th")
            if not header_row:
                header_row = await self._extract_row_cells(thead.first, "td")
            if header_row:
                rows.append(header_row)

        tbody_rows = table.locator("tbody tr")
        row_count = await tbody_rows.count()

        if row_count == 0:
            all_rows = table.locator("tr")
            total = await all_rows.count()
            start_index = 1 if rows else 0
            for i in range(start_index, total):
                row_data = await self._extract_row_cells(all_rows.nth(i), "td")
                if row_data:
                    rows.append(row_data)
        else:
            for i in range(row_count):
                row_data = await self._extract_row_cells(tbody_rows.nth(i), "td")
                if row_data:
                    rows.append(row_data)
        return rows

    async def extract_table_data_by_headers(
        self,
        root: ReportRoot,
        required_headers: frozenset[str] | set[str],
    ) -> list[list[str]]:
        """Find and extract the first visible table whose headers match required_headers.

        Skips Department Wise tables (have Department, lack Feedback Received).
        """
        tables = root.locator("table")
        try:
            count = await tables.count()
        except Exception as exc:
            log_automation_event(
                logger,
                "table_header_scan_failed",
                error=str(exc),
            )
            return []

        for index in range(count):
            table = tables.nth(index)
            try:
                if not await table.is_visible():
                    continue
                rows = await self._extract_rows_from_table(table)
                if not rows:
                    continue
                headers = rows[0]
                if self._looks_like_department_wise(headers):
                    log_automation_event(
                        logger,
                        "table_skipped_department_wise",
                        table_index=index,
                    )
                    continue
                if self._headers_match_required(headers, required_headers):
                    log_automation_event(
                        logger,
                        "table_matched_by_headers",
                        table_index=index,
                        column_count=len(headers),
                        row_count=len(rows),
                    )
                    return rows
            except Exception:
                continue

        log_automation_event(
            logger,
            "table_header_match_failed",
            required_headers=sorted(required_headers),
        )
        return []

    async def extract_division_feedback_table(
        self,
        root: ReportRoot,
    ) -> list[list[str]]:
        """Extract the Division Wise Feedback table specifically.

        Looks for a table with:
        - Either 'Organisation' OR 'Division' column
        - All feedback columns: Feedback Received, % Feedback, Excellent, etc.
        - NOT a Department Wise table
        """
        tables = root.locator("table")
        try:
            count = await tables.count()
            log_automation_event(
                logger,
                "report2_feedback_table_scan_started",
                table_count=count,
            )
        except Exception as exc:
            log_automation_event(
                logger,
                "report2_feedback_table_scan_failed",
                error=str(exc),
            )
            return []

        for index in range(count):
            table = tables.nth(index)
            try:
                if not await table.is_visible():
                    log_automation_event(
                        logger,
                        "report2_feedback_table_not_visible",
                        table_index=index,
                    )
                    continue

                rows = await self._extract_rows_from_table(table)
                if not rows:
                    log_automation_event(
                        logger,
                        "report2_feedback_table_no_rows",
                        table_index=index,
                    )
                    continue

                headers = rows[0]
                log_automation_event(
                    logger,
                    "report2_feedback_table_headers_found",
                    table_index=index,
                    headers=headers,
                    header_count=len(headers),
                )

                if self._looks_like_department_wise(headers):
                    log_automation_event(
                        logger,
                        "report2_feedback_table_skipped_department_wise",
                        table_index=index,
                        headers=headers,
                    )
                    continue

                if self._headers_match_required_with_aliases(
                    headers, FEEDBACK_DIVISION_REQUIRED_HEADERS, require_org_or_division=True
                ):
                    log_automation_event(
                        logger,
                        "report2_feedback_table_matched",
                        table_index=index,
                        column_count=len(headers),
                        row_count=len(rows),
                        headers=headers,
                    )
                    return rows

                log_automation_event(
                    logger,
                    "report2_feedback_table_headers_mismatch",
                    table_index=index,
                    headers=headers,
                    required=list(FEEDBACK_DIVISION_REQUIRED_HEADERS),
                )

            except Exception as exc:
                log_automation_event(
                    logger,
                    "report2_feedback_table_extraction_error",
                    table_index=index,
                    error=str(exc),
                )
                continue

        log_automation_event(
            logger,
            "report2_feedback_table_not_found",
            scanned_tables=count,
            required_headers=list(FEEDBACK_DIVISION_REQUIRED_HEADERS),
        )
        return []

    def _generate_filename(self, report_slug: str, extension: str = ".csv") -> str:
        """Generate timestamped filename (previous-day date + current time)."""
        timestamp = artifact_filename_timestamp()
        ext = extension if extension.startswith(".") else f".{extension}"
        return f"{report_slug}_{timestamp}{ext}"

    def _unique_path(self, base_path: Path) -> Path:
        """Return a non-existing path, appending _N if needed."""
        if not base_path.exists():
            return base_path

        stem = base_path.stem
        suffix = base_path.suffix
        counter = 1
        while True:
            candidate = base_path.with_name(f"{stem}_{counter}{suffix}")
            if not candidate.exists():
                return candidate
            counter += 1

    async def save_as_csv(
        self,
        data: list[list[str]],
        report_slug: str,
    ) -> Path | None:
        """Save extracted data as CSV."""
        if not data:
            log_automation_event(logger, "csv_save_skipped", reason="no_data")
            return None

        report_dir = ensure_directory(self.output_dir / report_slug)
        filename = self._generate_filename(report_slug, ".csv")
        target_path = self._unique_path(report_dir / filename)

        try:
            with target_path.open("w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerows(data)

            log_automation_event(
                logger,
                "csv_saved",
                path=str(target_path),
                row_count=len(data),
            )
            return target_path

        except Exception as exc:
            log_automation_event(logger, "csv_save_failed", error=str(exc))
            return None

    async def save_as_csv_fixed(
        self,
        data: list[list[str]],
        report_slug: str,
        filename: str,
    ) -> Path | None:
        """Save extracted data as CSV with a fixed filename (overwrites if exists)."""
        if not data:
            log_automation_event(logger, "csv_save_skipped", reason="no_data", filename=filename)
            return None

        report_dir = ensure_directory(self.output_dir / report_slug)
        target_path = report_dir / filename

        try:
            with target_path.open("w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerows(data)

            log_automation_event(
                logger,
                "csv_saved_fixed",
                path=str(target_path),
                row_count=len(data),
                filename=filename,
            )
            return target_path

        except Exception as exc:
            log_automation_event(logger, "csv_save_failed", error=str(exc), filename=filename)
            return None

    async def save_html(
        self,
        html: str,
        report_slug: str,
    ) -> Path | None:
        """Save raw HTML for debugging/archival."""
        if not html:
            return None

        report_dir = ensure_directory(self.output_dir / report_slug)
        filename = self._generate_filename(report_slug, ".html")
        target_path = self._unique_path(report_dir / filename)

        try:
            target_path.write_text(html, encoding="utf-8")
            log_automation_event(
                logger,
                "html_saved",
                path=str(target_path),
            )
            return target_path

        except Exception as exc:
            log_automation_event(logger, "html_save_failed", error=str(exc))
            return None

    async def extract_and_save(
        self,
        root: ReportRoot,
        report_slug: str,
        skip_validation: bool = False,
    ) -> ExtractionResult:
        """Full extraction pipeline: HTML + data + validation + CSV save."""
        html = await self.extract_table_html(root)
        if html is None:
            return ExtractionResult(
                success=False,
                error="Could not find or extract table HTML",
            )

        data = await self.extract_table_data(root)
        if not data:
            return ExtractionResult(
                success=False,
                html=html,
                error="Could not extract table data",
            )

        if not skip_validation:
            required_headers = get_required_headers_for_report(report_slug)
            validation = validate_extracted_data(data, required_headers)
            if not validation.valid:
                return ExtractionResult(
                    success=False,
                    html=html,
                    data=data,
                    row_count=len(data),
                    column_count=len(data[0]) if data else 0,
                    error=validation.error,
                    validation_result=validation,
                )
        else:
            validation = None

        csv_path = await self.save_as_csv(data, report_slug)

        return ExtractionResult(
            success=csv_path is not None,
            html=html,
            data=data,
            csv_path=csv_path,
            row_count=len(data),
            column_count=len(data[0]) if data else 0,
            error=None if csv_path else "Failed to save CSV",
            validation_result=validation,
        )
