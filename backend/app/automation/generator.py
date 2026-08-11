"""Report generation (view/load) without download for in-process automation."""

from __future__ import annotations

import logging
from pathlib import Path

from playwright.async_api import FrameLocator, Page

from app.automation.config import config
from app.automation.filters import ReportRoot
from app.automation.selectors import selectors
from app.automation.table_refresh import (
    table_fingerprint,
    wait_for_loaders,
    wait_for_table_refresh,
)
from app.automation.utils import ensure_directory, log_automation_event
from app.automation.wait_utils import poll_until
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)

PHASE5_BEFORE_SCREENSHOT = "phase5_before_generate.png"
PHASE5_AFTER_SCREENSHOT = "phase5_report_loaded.png"

EXPORT_KEYWORDS = ("export", "download", "excel", "pdf", "xlsx")
NON_REPORT_BUTTON_KEYWORDS = ("search complaint", "register complaint", "dashboard", "logout")
GENERATE_BUTTON_TEXTS = (
    "Submit",
    "Generate",
    "View Report",
    "Show Report",
    "Search",
    "View",
)


class ReportGenerationError(AppException):
    """Raised when report generation or results verification fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="REPORT_GENERATION_ERROR")


class ReportGeneratorService:
    """Clicks generate/view and verifies the report grid is visible."""

    async def capture_before_generate(self, page: Page) -> str:
        path = await self._capture(page, PHASE5_BEFORE_SCREENSHOT)
        log_automation_event(logger, "report_before_generate_screenshot", path=path)
        return path

    async def capture_report_loaded(self, page: Page) -> str:
        path = await self._capture(page, PHASE5_AFTER_SCREENSHOT)
        log_automation_event(logger, "report_screenshot_saved", path=path, stage="report_loaded")
        return path

    async def _capture(self, page: Page, filename: str) -> str:
        directory = ensure_directory(Path(config.debug_screenshots_dir))
        path = directory / filename
        await page.screenshot(path=str(path), full_page=True)
        return str(path)

    async def generate_report(self, root: ReportRoot, page: Page) -> None:
        """Click the generate/submit button and wait for the report to load."""
        button = await self._find_generate_button(root)
        if button is None:
            raise ReportGenerationError("Generate/View Report button not found")

        old_fp = await table_fingerprint(root)
        button_text = await self._button_label(button)
        log_automation_event(
            logger,
            "report_generate_click",
            button_text=button_text,
            table_fingerprint_before=(old_fp or "")[:120],
        )
        await button.click()

        refreshed = await wait_for_table_refresh(
            root,
            page,
            old_fp,
            timeout_seconds=min(float(config.timeout), 60.0),
        )
        if not refreshed:
            if not await self._wait_until_report_surface_exists(root, page, config.timeout * 1000):
                raise ReportGenerationError(
                    "Report table/grid did not refresh after generate"
                )

    async def _wait_for_report_loaded(self, root: ReportRoot, page: Page) -> None:
        """Legacy hook — refresh is handled in generate_report."""
        await wait_for_loaders(root, page)

    async def _wait_until_report_surface_exists(
        self, root: ReportRoot, page: Page, timeout_ms: int
    ) -> bool:
        deadline_seconds = timeout_ms / 1000

        async def _visible() -> bool:
            await wait_for_loaders(root, page, timeout_ms=2_000)
            return await self.verify_report_displayed(root)

        return await poll_until(
            _visible,
            interval_seconds=0.1,
            timeout_seconds=min(deadline_seconds, 30.0),
            reason="report_surface_poll",
        )

    async def _wait_for_loading_indicators(self, root: ReportRoot, page: Page, timeout_ms: int) -> None:
        await wait_for_loaders(root, page, timeout_ms=min(timeout_ms, 8_000))

    async def _find_generate_button(self, root: ReportRoot):
        candidates = [
            root.locator("#submitbtn"),
            root.locator("[name='submitbtn']"),
            root.locator("form:has(#dateRange) #submitbtn"),
            root.locator("form:has(#fromDate) input[type='submit']"),
            root.locator("form:has(#fromDate) button[type='submit']"),
            root.locator(selectors.report1_generate),
        ]
        for text in GENERATE_BUTTON_TEXTS:
            candidates.extend(
                [
                    root.locator(f"input[type='submit'][value*='{text}']"),
                    root.locator(f"button:has-text('{text}')"),
                    root.locator(f"input[value*='{text}']"),
                    root.locator(f"a:has-text('{text}')"),
                ]
            )
        candidates.extend(
            [
                root.locator("input[type='submit']"),
                root.locator("button[type='submit']"),
            ]
        )

        best_candidate = None
        best_score = -1
        for locator in candidates:
            count = await locator.count()
            for index in range(count):
                candidate = locator.nth(index)
                if not await candidate.is_visible():
                    continue
                if await self._is_export_button(candidate):
                    continue
                if await self._is_non_report_button(candidate):
                    continue
                score = await self._button_score(candidate)
                if score > best_score:
                    best_score = score
                    best_candidate = candidate
        return best_candidate

    async def _button_score(self, locator) -> int:
        score = 0
        label = (await self._button_label(locator)).lower()
        try:
            element_id = (await locator.get_attribute("id") or "").lower()
            element_name = (await locator.get_attribute("name") or "").lower()
            element_type = (await locator.get_attribute("type") or "").lower()
        except Exception:
            element_id = ""
            element_name = ""
            element_type = ""

        if element_id == "submitbtn" or element_name == "submitbtn":
            score += 100
        if element_type == "submit":
            score += 30
        if any(text.lower() == label for text in GENERATE_BUTTON_TEXTS):
            score += 20
        if any(text.lower() in label for text in GENERATE_BUTTON_TEXTS):
            score += 10
        return score

    async def _button_label(self, locator) -> str:
        try:
            text = (await locator.inner_text()).strip()
            if text:
                return text
        except Exception:
            pass
        try:
            return (await locator.get_attribute("value") or "").strip()
        except Exception:
            return ""

    async def _is_export_button(self, locator) -> bool:
        label = (await self._button_label(locator)).lower()
        combined = label
        try:
            combined = f"{label} {(await locator.get_attribute('value') or '').lower()}"
        except Exception:
            pass
        return any(keyword in combined for keyword in EXPORT_KEYWORDS)

    async def _is_non_report_button(self, locator) -> bool:
        label = (await self._button_label(locator)).lower()
        try:
            element_id = (await locator.get_attribute("id") or "").lower()
            element_name = (await locator.get_attribute("name") or "").lower()
        except Exception:
            element_id = ""
            element_name = ""
        if element_id == "submitbtn" or element_name == "submitbtn":
            return False
        return any(keyword in label for keyword in NON_REPORT_BUTTON_KEYWORDS)

    async def count_rows(self, root: ReportRoot) -> int:
        """Best-effort count of rows in the report results table."""
        table = root.locator(selectors.report1_table).first
        if await table.count() == 0:
            table = root.locator(selectors.report1_grid).first
        if await table.count() == 0:
            return 0
        rows = table.locator("tbody tr")
        if await rows.count() == 0:
            rows = table.locator("tr")
        return await rows.count()

    async def verify_report_displayed(self, root: ReportRoot) -> bool:
        table = root.locator(selectors.report1_table).first
        grid = root.locator(selectors.report1_grid).first
        for target in (table, grid):
            if await target.count() == 0:
                continue
            if await target.is_visible():
                return True
        return await self.count_rows(root) > 0

    async def log_report_metadata(self, page: Page, row_count: int) -> None:
        try:
            page_title = await page.title()
        except Exception:
            page_title = ""
        log_automation_event(
            logger,
            "report_generated",
            page_url=page.url,
            page_title=page_title,
            row_count=row_count,
        )
