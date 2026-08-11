"""Feedback modal extractor for Reports 5 and 6 (Zone Wise with Unsatisfactory drill-down)."""

from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, Locator, TimeoutError as PlaywrightTimeout

from app.automation.config import config
from app.automation.formatting.scr import mode_matches
from app.automation.utils import log_automation_event, ensure_directory, resolve_report_dir

logger = logging.getLogger(__name__)

ZONE_WISE_HEADERS = [
    "Organisation",
    "Feedback Received",
    "% Feedback",
    "Excellent",
    "Satisfactory",
    "Unsatisfactory",
    "% Unsatisfactory",
]

LIST_OF_COMPLAINTS_HEADERS = [
    "Ref. No.",
    "Train/Station",
    "Mode",
]


@dataclass
class ZoneWiseData:
    """Data extracted from the Zone Wise table."""
    
    zone_name: str
    feedback_received: int
    unsatisfactory_count: int
    unsatisfactory_percent: float


@dataclass
class ComplaintRow:
    """A single complaint row from the List of Complaints modal."""
    
    ref_no: str
    mode: str
    data: dict[str, str]


@dataclass
class FeedbackExtractionResult:
    """Result from feedback extraction operation."""
    
    success: bool
    zone_data: ZoneWiseData | None = None
    complaints: list[ComplaintRow] | None = None
    error: str | None = None
    extracted_count: int = 0
    expected_count: int = 0


class FeedbackModalExtractor:
    """Extract data from Feedback report Zone Wise table and Unsatisfactory modal."""

    def __init__(self, page: Page) -> None:
        self.page = page

    def find_zone_wise_table(self) -> Locator | None:
        """Find the Zone Wise table by its headers (not Department Wise)."""
        tables = self.page.locator("table")
        count = tables.count()

        for idx in range(count):
            table = tables.nth(idx)
            headers = self._extract_table_headers(table)
            
            if self._is_zone_wise_table(headers):
                log_automation_event(
                    logger,
                    "zone_wise_table_found",
                    table_index=idx,
                    headers=headers,
                )
                return table

        log_automation_event(
            logger,
            "zone_wise_table_not_found",
            tables_checked=count,
        )
        return None

    def _extract_table_headers(self, table: Locator) -> list[str]:
        """Extract header text from a table."""
        headers = []
        header_cells = table.locator("thead th, tr:first-child th, tr:first-child td")
        count = header_cells.count()
        for idx in range(count):
            text = header_cells.nth(idx).inner_text().strip()
            headers.append(text)
        return headers

    def _is_zone_wise_table(self, headers: list[str]) -> bool:
        """Check if headers match Zone Wise table (not Department Wise)."""
        required = ["Organisation", "Feedback Received", "Unsatisfactory"]
        has_all_required = all(
            any(req.lower() in h.lower() for h in headers)
            for req in required
        )
        is_department_wise = any(
            "department" in h.lower() for h in headers
        )
        return has_all_required and not is_department_wise

    def get_scr_unsatisfactory_count(self, table: Locator) -> int:
        """Read the Unsatisfactory count for SCR zone from the Zone Wise table."""
        rows = table.locator("tbody tr")
        row_count = rows.count()

        for idx in range(row_count):
            row = rows.nth(idx)
            cells = row.locator("td")
            cell_count = cells.count()
            
            if cell_count < len(ZONE_WISE_HEADERS):
                continue

            org_text = cells.nth(0).inner_text().strip()
            if "south central railway" in org_text.lower():
                unsatisfactory_cell = cells.nth(5)
                unsatisfactory_text = unsatisfactory_cell.inner_text().strip()
                try:
                    count = int(re.sub(r"[^\d]", "", unsatisfactory_text))
                    log_automation_event(
                        logger,
                        "scr_unsatisfactory_found",
                        organisation=org_text,
                        unsatisfactory_count=count,
                    )
                    return count
                except ValueError:
                    log_automation_event(
                        logger,
                        "unsatisfactory_parse_error",
                        text=unsatisfactory_text,
                    )
                    return 0

        log_automation_event(logger, "scr_not_found_in_table")
        return 0

    def click_unsatisfactory_to_open_modal(self, table: Locator) -> bool:
        """Click the Unsatisfactory count cell for SCR to open the List of Complaints modal."""
        rows = table.locator("tbody tr")
        row_count = rows.count()

        for idx in range(row_count):
            row = rows.nth(idx)
            cells = row.locator("td")
            cell_count = cells.count()
            
            if cell_count < len(ZONE_WISE_HEADERS):
                continue

            org_text = cells.nth(0).inner_text().strip()
            if "south central railway" in org_text.lower():
                unsatisfactory_cell = cells.nth(5)
                link = unsatisfactory_cell.locator("a")
                
                if link.count() > 0:
                    link.first.click()
                else:
                    unsatisfactory_cell.click()

                try:
                    self.page.wait_for_selector(
                        ".modal, [role='dialog'], #complaintListModal",
                        timeout=10000,
                    )
                    log_automation_event(logger, "complaint_modal_opened")
                    return True
                except PlaywrightTimeout:
                    log_automation_event(logger, "modal_open_timeout")
                    return False

        return False

    def extract_all_modal_pages(self, expected_mode: str) -> list[ComplaintRow]:
        """Extract all complaints from the modal, handling pagination."""
        all_complaints: list[ComplaintRow] = []
        seen_refs: set[str] = set()
        page_num = 1

        while True:
            try:
                self.page.locator(
                    ".modal table, [role='dialog'] table, #complaintListModal table"
                ).first.wait_for(state="visible", timeout=2000)
            except Exception:
                self.page.wait_for_timeout(50)

            modal_table = self.page.locator(
                ".modal table, [role='dialog'] table, #complaintListModal table"
            ).first

            if modal_table.count() == 0:
                break

            rows = modal_table.locator("tbody tr")
            row_count = rows.count()

            if row_count == 0:
                no_data = self.page.locator("text=No data available in table")
                if no_data.count() > 0:
                    break
                empty_text = modal_table.inner_text().strip()
                if not empty_text or "no data" in empty_text.lower():
                    break

            page_complaints = 0
            for row_idx in range(row_count):
                row = rows.nth(row_idx)
                cells = row.locator("td")
                cell_count = cells.count()

                if cell_count < 3:
                    continue

                all_headers = self._extract_table_headers(modal_table)
                row_data: dict[str, str] = {}
                
                for col_idx in range(min(cell_count, len(all_headers))):
                    header = all_headers[col_idx] if col_idx < len(all_headers) else f"Col{col_idx}"
                    cell_text = cells.nth(col_idx).inner_text().strip()
                    row_data[header] = cell_text

                ref_no = row_data.get("Ref. No.", "")
                mode = row_data.get("Mode", "")

                if ref_no and ref_no not in seen_refs:
                    mode_ok = mode_matches(expected_mode, mode)
                    if mode_ok:
                        seen_refs.add(ref_no)
                        all_complaints.append(ComplaintRow(
                            ref_no=ref_no,
                            mode=mode,
                            data=row_data,
                        ))
                        page_complaints += 1

            log_automation_event(
                logger,
                "modal_page_extracted",
                page=page_num,
                rows_extracted=page_complaints,
                total_so_far=len(all_complaints),
            )

            next_button = self.page.locator(
                ".pagination .next:not(.disabled), "
                "button:has-text('Next'):not([disabled]), "
                "a:has-text('Next'):not(.disabled), "
                ".dataTables_paginate .next:not(.disabled)"
            )

            if next_button.count() > 0 and next_button.first.is_visible():
                try:
                    next_button.first.click()
                    try:
                        self.page.locator(
                            ".modal table tbody tr, [role='dialog'] table tbody tr"
                        ).first.wait_for(state="attached", timeout=2000)
                    except Exception:
                        self.page.wait_for_timeout(200)
                    page_num += 1
                except Exception as e:
                    log_automation_event(logger, "pagination_click_error", error=str(e))
                    break
            else:
                break

        return all_complaints

    def close_modal(self) -> None:
        """Close the complaints modal."""
        close_buttons = self.page.locator(
            ".modal .close, [role='dialog'] button[aria-label='Close'], "
            ".modal button:has-text('Close'), .modal .btn-close"
        )
        if close_buttons.count() > 0:
            close_buttons.first.click()
            try:
                self.page.locator(".modal.show, [role='dialog']").first.wait_for(
                    state="hidden", timeout=2000
                )
            except Exception:
                self.page.wait_for_timeout(50)

    def extract_scr_complaints(
        self,
        expected_mode: str,
        save_csv: bool = True,
        report_slug: str = "report5",
    ) -> FeedbackExtractionResult:
        """Full extraction flow: find table, read count, open modal, extract all."""
        table = self.find_zone_wise_table()
        if table is None:
            return FeedbackExtractionResult(
                success=False,
                error="Zone Wise table not found",
            )

        expected_count = self.get_scr_unsatisfactory_count(table)
        if expected_count == 0:
            return FeedbackExtractionResult(
                success=False,
                error="SCR Unsatisfactory count is 0 or not found",
                expected_count=0,
            )

        if not self.click_unsatisfactory_to_open_modal(table):
            return FeedbackExtractionResult(
                success=False,
                error="Failed to open complaints modal",
                expected_count=expected_count,
            )

        complaints = self.extract_all_modal_pages(expected_mode=expected_mode)
        self.close_modal()

        if save_csv and complaints:
            self._save_complaints_csv(complaints, report_slug)

        extracted_count = len(complaints)
        success = extracted_count == expected_count

        if not success:
            log_automation_event(
                logger,
                "count_mismatch",
                expected=expected_count,
                extracted=extracted_count,
            )

        return FeedbackExtractionResult(
            success=success,
            zone_data=ZoneWiseData(
                zone_name="South Central Railway",
                feedback_received=0,
                unsatisfactory_count=expected_count,
                unsatisfactory_percent=0.0,
            ),
            complaints=complaints,
            extracted_count=extracted_count,
            expected_count=expected_count,
            error=None if success else f"Count mismatch: expected {expected_count}, got {extracted_count}",
        )

    def _save_complaints_csv(
        self,
        complaints: list[ComplaintRow],
        report_slug: str,
    ) -> Path:
        """Save extracted complaints to CSV."""
        extracted_dir = ensure_directory(resolve_report_dir(config.extracted_data_dir, report_slug))
        csv_path = extracted_dir / f"{report_slug}_complaints_raw.csv"

        if not complaints:
            return csv_path

        all_keys: set[str] = set()
        for complaint in complaints:
            all_keys.update(complaint.data.keys())

        headers = ["Ref. No.", "Mode"] + sorted(all_keys - {"Ref. No.", "Mode"})

        with csv_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
            writer.writeheader()
            for complaint in complaints:
                row_data = {"Ref. No.": complaint.ref_no, "Mode": complaint.mode}
                row_data.update(complaint.data)
                writer.writerow(row_data)

        log_automation_event(
            logger,
            "complaints_csv_saved",
            path=str(csv_path),
            row_count=len(complaints),
        )

        return csv_path
