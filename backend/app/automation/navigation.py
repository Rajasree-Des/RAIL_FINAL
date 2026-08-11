"""Portal navigation helpers for in-process Playwright automation."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from app.automation.config import config
from app.automation.reports import ReportDefinition
from app.automation.utils import ensure_directory, log_automation_event
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)

JSP_QUERY_SUFFIX = "archiveFlag=N&Id=null&mobile=null&email=null"


def url_matches_report_fragment(page_url: str, fragment: str) -> bool:
    """True when page URL targets the exact MIS report path (not a prefix sibling).

    ``mis_reports/report1`` must not match ``mis_reports/report16``.
    """
    if not page_url or not fragment:
        return False
    needle = fragment.strip("/").lower()
    hay = page_url.lower()
    parsed = urlparse(hay)
    page_param = parse_qs(parsed.query).get("page", [""])[0].strip("/").lower()
    if page_param:
        return page_param == needle or page_param.endswith("/" + needle)
    # Fallback: fragment as whole path segment, not a numeric prefix of another report
    pattern = re.compile(rf"(?:^|[?&/=]){re.escape(needle)}(?!\d)")
    return pattern.search(hay) is not None


class NavigationError(AppException):
    """Raised when portal navigation or page verification fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="NAVIGATION_ERROR")


class NavigationService:
    """Navigates the RailMadad portal to report pages on an existing tab."""

    def build_report_url(self, current_url: str, page_path: str) -> str:
        """Build a RailMadad JSP report URL from the active tab origin."""
        parsed = urlparse(current_url)
        if not parsed.scheme or not parsed.netloc:
            raise NavigationError(f"Cannot derive portal origin from URL: {current_url}")

        normalized_path = page_path if page_path.startswith("/") else f"/{page_path}"
        origin = f"{parsed.scheme}://{parsed.netloc}"
        return (
            f"{origin}/rmmis/admin/home.jsp"
            f"?page={normalized_path}&{JSP_QUERY_SUFFIX}"
        )

    async def verify_report_page(self, page: Page, report: ReportDefinition) -> bool:
        """Return True when the page URL matches the expected report."""
        return url_matches_report_fragment(page.url, report.url_fragment)

    def _log_report_verified(self, report: ReportDefinition, page: Page) -> None:
        log_automation_event(
            logger,
            "report_page_verified",
            report=report.slug,
            url=page.url,
        )

    async def navigate_to_report(self, page: Page, report: ReportDefinition) -> None:
        """Navigate to a report page, skipping goto when already verified."""
        timeout_ms = config.timeout * 1000

        if await self.verify_report_page(page, report):
            log_automation_event(
                logger,
                "report_navigate_skip",
                report=report.slug,
                url=page.url,
                reason="already_on_report_page",
            )
            self._log_report_verified(report, page)
            return

        target_url = self.build_report_url(page.url, report.page_path)
        log_automation_event(
            logger,
            "report_navigate_start",
            report=report.slug,
            target_url=target_url,
        )

        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                await page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 15_000))
            except PlaywrightTimeoutError:
                logger.debug("networkidle wait skipped after navigate to %s", report.slug)
            try:
                await page.wait_for_selector("select, table, form", timeout=10_000)
            except Exception:
                pass
        except PlaywrightTimeoutError as exc:
            raise NavigationError(
                f"Timed out navigating to {report.name} at {target_url}"
            ) from exc
        except Exception as exc:
            raise NavigationError(
                f"Failed to navigate to {report.name}: {exc}"
            ) from exc

        if not await self.verify_report_page(page, report):
            # One retry — portal sometimes keeps prior report fragment briefly
            try:
                await page.goto(target_url, wait_until="domcontentloaded", timeout=timeout_ms)
                try:
                    await page.wait_for_selector("select, table, form", timeout=10_000)
                except Exception:
                    pass
            except Exception:
                pass
            if not await self.verify_report_page(page, report):
                raise NavigationError(
                    f"Report page verification failed for {report.name}. "
                    f"Expected URL fragment '{report.url_fragment}', got '{page.url}'"
                )

        self._log_report_verified(report, page)

    async def capture_debug_screenshot(
        self,
        page: Page,
        dest_dir: str | Path,
        filename: str,
    ) -> str:
        """Save a full-page debug screenshot and return the file path."""
        directory = ensure_directory(Path(dest_dir))
        path = directory / filename
        await page.screenshot(path=str(path), full_page=True)
        log_automation_event(
            logger,
            "report_screenshot_saved",
            path=str(path),
        )
        logger.info("Debug screenshot saved to %s", path)
        return str(path)

    async def open_reports_page(self, page: Page) -> None:
        """Navigate to the first report in the catalog."""
        from app.automation.reports import catalog

        await self.navigate_to_report(page, catalog.first_report())
