"""Report table sorting helpers for in-process Playwright automation."""

from __future__ import annotations

import logging
import re

from playwright.async_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from app.automation.filters import ReportRoot
from app.automation.selectors import selectors
from app.automation.utils import log_automation_event
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)

LOADING_SELECTORS = (
    ".loading",
    ".loader",
    "[class*='loading']",
    "[class*='spinner']",
    "[class*='Loader']",
    "#loading",
    "#loader",
    "text=/Loading\\.?\\.?/i",
)

HEADER_WAIT_TIMEOUT_MS = 30_000
STABILITY_TIMEOUT_MS = 30_000

RECEIVED_COLUMN = "Received"
FEEDBACK_RECEIVED_COLUMN = "Feedback Received"


class ReceivedSortError(AppException):
    """Raised when a numeric count column cannot be sorted descending."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="RECEIVED_SORT_ERROR")


class ReceivedColumnService:
    """Double-clicks count column headers to sort descending before extract/export."""

    async def sort_received_descending(self, root: ReportRoot, page: Page) -> None:
        """Click Received header twice and verify descending sort."""
        await self.sort_column_descending(root, page, RECEIVED_COLUMN)

    async def sort_feedback_received_descending(self, root: ReportRoot, page: Page) -> None:
        """Click Feedback Received header twice and verify descending sort."""
        await self.sort_column_descending(root, page, FEEDBACK_RECEIVED_COLUMN)

    async def sort_column_descending(
        self,
        root: ReportRoot,
        page: Page,
        column_header: str,
    ) -> None:
        """Click the given header twice and verify descending sort (one retry)."""
        header = await self._find_column_header(root, page, column_header)
        if header is None:
            raise ReceivedSortError(f"{column_header} column header not found")

        log_automation_event(
            logger,
            "sort_header_found",
            column=column_header,
        )

        for attempt in range(2):
            await self._perform_two_click_sequence(header, root, page, column_header)
            if await self._verify_descending_sort(root, page, header, column_header):
                log_automation_event(
                    logger,
                    "sort_verified",
                    column=column_header,
                    attempt=attempt + 1,
                )
                return

            # DataTables cycles unsorted→asc→desc. Two clicks from an
            # already-sorted table can land on unsorted/asc; one recovery
            # click typically reaches descending without restarting.
            await header.click()
            log_automation_event(
                logger,
                "sort_click_recovery",
                column=column_header,
                attempt=attempt + 1,
            )
            await self._wait_for_table_stable(root, page)
            if await self._verify_descending_sort(root, page, header, column_header):
                log_automation_event(
                    logger,
                    "sort_verified",
                    column=column_header,
                    attempt=attempt + 1,
                    recovered=True,
                )
                return

            log_automation_event(
                logger,
                "sort_verification_failed",
                column=column_header,
                attempt=attempt + 1,
            )

        raise ReceivedSortError(
            f"{column_header} column sort verification failed after two full click sequences"
        )

    async def _find_column_header(
        self,
        root: ReportRoot,
        page: Page,
        column_header: str,
    ) -> Locator | None:
        search_roots: list[ReportRoot] = [root]
        if root is not page:
            search_roots.append(page)

        # Normalize the target header for comparison (collapse whitespace)
        normalized_target = re.sub(r"\s+", " ", column_header.strip()).lower()
        exact = re.compile(rf"^{re.escape(column_header)}$", re.I)
        
        candidates: list[Locator] = []
        for search_root in search_roots:
            if column_header == RECEIVED_COLUMN:
                candidates.append(search_root.locator(selectors.report1_received_header))
            candidates.extend([
                search_root.locator("table thead th").filter(has_text=exact),
                search_root.locator(".dataTables_wrapper th").filter(has_text=exact),
                search_root.get_by_role("columnheader", name=exact),
            ])

        # First pass: exact match
        for locator in candidates:
            try:
                count = await locator.count()
                for index in range(count):
                    candidate = locator.nth(index)
                    if not await candidate.is_visible():
                        continue
                    text = (await candidate.inner_text()).strip()
                    if not exact.match(text):
                        continue
                    if not await self._is_enabled(candidate):
                        continue
                    await candidate.wait_for(state="visible", timeout=HEADER_WAIT_TIMEOUT_MS)
                    return candidate
            except PlaywrightTimeoutError:
                continue
            except Exception as exc:
                logger.debug("Error locating %s header: %s", column_header, exc)

        # Second pass: partial/fuzzy match (for headers with extra whitespace or variants)
        for search_root in search_roots:
            all_headers = search_root.locator("table thead th, .dataTables_wrapper th")
            try:
                count = await all_headers.count()
                for index in range(count):
                    candidate = all_headers.nth(index)
                    if not await candidate.is_visible():
                        continue
                    text = (await candidate.inner_text()).strip()
                    # Normalize whitespace in header text for comparison
                    normalized_text = re.sub(r"\s+", " ", text).lower()
                    if normalized_target in normalized_text or normalized_text in normalized_target:
                        if not await self._is_enabled(candidate):
                            continue
                        log_automation_event(
                            logger,
                            "sort_header_fuzzy_match",
                            column=column_header,
                            found_text=text,
                        )
                        await candidate.wait_for(state="visible", timeout=HEADER_WAIT_TIMEOUT_MS)
                        return candidate
            except PlaywrightTimeoutError:
                continue
            except Exception as exc:
                logger.debug("Error in fuzzy search for %s header: %s", column_header, exc)

        return None

    async def _find_received_header(self, root: ReportRoot, page: Page) -> Locator | None:
        """Backward-compatible alias for Received header lookup."""
        return await self._find_column_header(root, page, RECEIVED_COLUMN)

    async def _perform_two_click_sequence(
        self,
        header: Locator,
        root: ReportRoot,
        page: Page,
        column_header: str = RECEIVED_COLUMN,
    ) -> None:
        await header.click()
        log_automation_event(logger, "sort_click_1", column=column_header)
        await self._wait_for_table_stable(root, page)

        await header.click()
        log_automation_event(logger, "sort_click_2", column=column_header)
        await self._wait_for_table_stable(root, page)

    async def _wait_for_table_stable(self, root: ReportRoot, page: Page) -> None:
        for selector in LOADING_SELECTORS:
            loader = root.locator(selector)
            if await loader.count() == 0:
                continue
            try:
                await loader.first.wait_for(state="hidden", timeout=STABILITY_TIMEOUT_MS)
            except PlaywrightTimeoutError:
                logger.debug("Loader still visible for selector %s", selector)

        try:
            await page.wait_for_load_state("domcontentloaded", timeout=min(STABILITY_TIMEOUT_MS, 10_000))
        except PlaywrightTimeoutError:
            logger.debug("domcontentloaded timeout while waiting for table stability")
        # Prefer table/header readiness over full networkidle (up to 5s each sort click)
        try:
            table = root.locator("table").first
            await table.wait_for(state="visible", timeout=3_000)
        except PlaywrightTimeoutError:
            logger.debug("Table not visible after sort click")

    async def _verify_descending_sort(
        self,
        root: ReportRoot,
        page: Page,
        header: Locator,
        column_header: str = RECEIVED_COLUMN,
    ) -> bool:
        if await self._header_indicates_descending(header):
            return True
        return await self._rows_indicate_descending(root, column_header)

    async def _header_indicates_descending(self, header: Locator) -> bool:
        try:
            class_attr = (await header.get_attribute("class") or "").lower()
            if "sorting_desc" in class_attr:
                return True
            aria_sort = (await header.get_attribute("aria-sort") or "").lower()
            if aria_sort == "descending":
                return True
        except Exception as exc:
            logger.debug("Could not read header sort state: %s", exc)
        return False

    async def _rows_indicate_descending(
        self,
        root: ReportRoot,
        column_header: str = RECEIVED_COLUMN,
    ) -> bool:
        values = await self._read_column_values(root, column_header)
        if len(values) < 2:
            return False
        return all(values[index] >= values[index + 1] for index in range(len(values) - 1))

    async def _read_column_values(self, root: ReportRoot, column_header: str) -> list[int]:
        table = root.locator(selectors.report1_table).first
        if await table.count() == 0:
            table = root.locator(selectors.report1_grid).first
        if await table.count() == 0:
            return []

        target = column_header.strip().lower()
        try:
            handle = await table.element_handle()
            if handle is not None:
                values = await table.page.evaluate(
                    """([tableEl, targetHeader]) => {
                      if (!tableEl) return [];
                      const norm = (t) => (t || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                      const headers = [...tableEl.querySelectorAll('thead th, thead td')]
                        .map(el => norm(el.textContent));
                      let col = headers.indexOf(norm(targetHeader));
                      if (col < 0) {
                        col = headers.findIndex(h => h.includes(norm(targetHeader)));
                      }
                      if (col < 0) return [];
                      const out = [];
                      for (const tr of tableEl.querySelectorAll('tbody tr')) {
                        const rowText = norm(tr.textContent);
                        if (rowText.includes('total')) continue;
                        const cells = tr.querySelectorAll('td');
                        if (cells.length <= col) continue;
                        const digits = (cells[col].textContent || '').replace(/[^\\d]/g, '');
                        if (digits) out.push(parseInt(digits, 10));
                        if (out.length >= 10) break;
                      }
                      return out;
                    }""",
                    [handle, target],
                )
                if isinstance(values, list):
                    return [int(v) for v in values if isinstance(v, (int, float))]
        except Exception:
            pass

        headers = table.locator("thead th")
        header_count = await headers.count()
        column_index = -1
        target = column_header.strip().lower()
        for index in range(header_count):
            text = (await headers.nth(index).inner_text()).strip().lower()
            if text == target:
                column_index = index
                break

        if column_index < 0:
            return []

        rows = table.locator("tbody tr")
        row_count = await rows.count()
        values: list[int] = []
        for row_index in range(min(row_count, 15)):
            row = rows.nth(row_index)
            try:
                row_text = (await row.inner_text()).strip().lower()
            except Exception:
                row_text = ""
            # Footer/total rows (sum) break numeric descending checks.
            if "total" in row_text:
                continue
            cells = row.locator("td")
            if await cells.count() <= column_index:
                continue
            raw = (await cells.nth(column_index).inner_text()).strip()
            digits = re.sub(r"[^\d]", "", raw)
            if digits:
                values.append(int(digits))
            if len(values) >= 10:
                break
        return values

    async def _read_received_column_values(self, root: ReportRoot) -> list[int]:
        """Backward-compatible alias for Received column values."""
        return await self._read_column_values(root, RECEIVED_COLUMN)

    async def _is_enabled(self, locator: Locator) -> bool:
        try:
            disabled = await locator.get_attribute("disabled")
            if disabled is not None:
                return False
            class_attr = (await locator.get_attribute("class") or "").lower()
            if "disabled" in class_attr:
                return False
            return True
        except Exception:
            return True
