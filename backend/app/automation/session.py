"""Browser session and tab management via CDP attach."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import Browser, Page

from app.automation.utils import ensure_directory, normalize_url
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)

# URL patterns that indicate the login page
LOGIN_URL_PATTERNS = (
    "/login",
    "/signin",
    "/madad/final/login",
    "/madad/final/index",
    "index.jsp",
)

# Selectors that indicate a login form is present
LOGIN_PAGE_SELECTORS = (
    "input[name='userName']",
    "input[name='username']",
    "input[name='password']",
    "form[action*='login']",
    "#loginForm",
    "#login-form",
    "button:has-text('Login')",
    "input[type='submit'][value*='Login']",
    "input[type='submit'][value*='Sign']",
)

MIS_URL_PATTERNS = (
    "/rmmis/admin",
    "mis_reports/",
    "/rmmis/",
)

MIS_MENU_SELECTORS = (
    "a:has-text('Report')",
    "a:has-text('MIS')",
    "[id*='menu']",
    ".menu",
    "nav",
)


class RailMadadTabNotFoundError(AppException):
    """Raised when no open tab matches the RailMadad portal URL."""

    def __init__(self, message: str = "RailMadad tab not found among open tabs") -> None:
        super().__init__(message=message, code="RAILMADAD_TAB_NOT_FOUND")


@dataclass
class MisSessionStatus:
    """Result of MIS session verification."""

    valid: bool
    error_code: str | None = None
    error: str | None = None


class MisSessionError(Exception):
    """Raised when MIS session is lost or invalid."""

    def __init__(self, status: MisSessionStatus) -> None:
        self.status = status
        super().__init__(status.error or "MIS session invalid")


@dataclass(frozen=True)
class TabInfo:
    """Metadata for a single browser tab discovered over CDP."""

    context_index: int
    tab_index: int
    url: str
    title: str
    is_railmadad: bool
    page: Page

    def format_line(self) -> str:
        label = " (RailMadad)" if self.is_railmadad else ""
        return f"[ctx={self.context_index} tab={self.tab_index}] {self.url}{label}"


@dataclass
class AttachResult:
    """Outcome of a CDP attach and tab-discovery run."""

    success: bool
    tabs: list[TabInfo]
    railmadad_tab: TabInfo | None = None
    screenshot_path: str | None = None
    error: str | None = None


class SessionManager:
    """Tracks the active browser session and RailMadad page."""

    def __init__(
        self,
        browser: Browser | None = None,
        railmadad_url: str = "https://railmadad.indianrail.gov.in",
    ) -> None:
        self._browser = browser
        self._page: Page | None = None
        self._railmadad_url = railmadad_url
        self._tabs: list[TabInfo] = []

    @property
    def browser(self) -> Browser | None:
        return self._browser

    @property
    def page(self) -> Page | None:
        return self._page

    @property
    def tabs(self) -> list[TabInfo]:
        return list(self._tabs)

    def bind_browser(self, browser: Browser) -> None:
        """Associate a connected browser with this session."""
        self._browser = browser

    def bind_page(self, page: Page) -> None:
        """Set the active RailMadad page."""
        self._page = page

    @staticmethod
    def is_railmadad_url(page_url: str, base_url: str) -> bool:
        """Return True if page_url belongs to the RailMadad portal."""
        if not page_url or page_url in ("about:blank", "chrome://newtab/"):
            return False

        normalized_page = normalize_url(page_url)
        normalized_base = normalize_url(base_url)

        if normalized_page.startswith(normalized_base):
            return True

        host = urlparse(page_url).netloc.lower()
        return "railmadad" in host

    async def discover_tabs(self, browser: Browser) -> list[TabInfo]:
        """Enumerate all browser contexts and open tabs."""
        self.bind_browser(browser)
        tabs: list[TabInfo] = []

        contexts = browser.contexts
        logger.info("Discovered %d browser context(s)", len(contexts))

        for context_index, context in enumerate(contexts):
            pages = context.pages
            for tab_index, page in enumerate(pages):
                url = page.url

                # Skip pages with empty or problematic URLs to avoid hangs
                if not url or url in ("about:blank", "chrome://newtab/", ""):
                    logger.debug(
                        "Skipping page with empty/blank URL: ctx=%d tab=%d",
                        context_index,
                        tab_index,
                    )
                    continue

                # Use timeout to prevent hanging on unresponsive pages
                title = ""
                try:
                    title = await asyncio.wait_for(page.title(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning(
                        "Timeout getting title for page: ctx=%d tab=%d url=%s",
                        context_index,
                        tab_index,
                        url[:100],
                    )
                except Exception as exc:
                    logger.debug("Error getting page title: %s", exc)

                is_railmadad = self.is_railmadad_url(url, self._railmadad_url)
                tab = TabInfo(
                    context_index=context_index,
                    tab_index=tab_index,
                    url=url,
                    title=title,
                    is_railmadad=is_railmadad,
                    page=page,
                )
                tabs.append(tab)

        self._tabs = tabs
        logger.info("Discovered %d open tab(s) across %d context(s)", len(tabs), len(contexts))
        return tabs

    @staticmethod
    def _tab_priority(tab: TabInfo, prefer_url_fragment: str | None = None) -> int:
        """Score RailMadad tabs — higher is preferred for automation attach."""
        from app.automation.navigation import url_matches_report_fragment

        url = tab.url.lower()
        if prefer_url_fragment and url_matches_report_fragment(url, prefer_url_fragment):
            return 200
        if "mis_reports" in url:
            return 100
        if "/rmmis/admin" in url:
            return 80
        if "/madad/final" in url:
            return 10
        return 50

    def find_railmadad_tab(
        self,
        tabs: list[TabInfo] | None = None,
        prefer_url_fragment: str | None = None,
    ) -> TabInfo | None:
        """Return the best RailMadad tab, preferring admin MIS report pages."""
        source = tabs if tabs is not None else self._tabs
        railmadad_tabs = [tab for tab in source if tab.is_railmadad]
        if not railmadad_tabs:
            return None
        return max(
            railmadad_tabs,
            key=lambda tab: self._tab_priority(tab, prefer_url_fragment),
        )

    async def activate_tab(self, page: Page) -> None:
        """Bring an existing tab to the foreground without navigation."""
        await page.bring_to_front()
        self.bind_page(page)

    async def is_login_page(self, page: Page) -> bool:
        """Check if current page is RailMadad login page (not logged in)."""
        url = page.url.lower()

        # Check URL patterns that indicate login page
        for pattern in LOGIN_URL_PATTERNS:
            if pattern in url:
                logger.info("Login page detected via URL pattern: %s", pattern)
                return True

        # Check for login form elements on the page
        for selector in LOGIN_PAGE_SELECTORS:
            try:
                count = await asyncio.wait_for(
                    page.locator(selector).count(),
                    timeout=2.0,
                )
                if count > 0:
                    logger.info("Login page detected via selector: %s", selector)
                    return True
            except asyncio.TimeoutError:
                logger.debug("Timeout checking selector: %s", selector)
            except Exception as exc:
                logger.debug("Error checking selector %s: %s", selector, exc)

        return False

    async def capture_screenshot(self, page: Page, dest_dir: Path) -> str:
        """Capture a full-page screenshot and return the saved file path."""
        directory = ensure_directory(dest_dir)
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        path = directory / f"failure_{timestamp}.png"
        await page.screenshot(path=str(path), full_page=True)
        logger.info("Failure screenshot saved to %s", path)
        return str(path)

    def first_available_page(self, tabs: list[TabInfo] | None = None) -> Page | None:
        """Return the first page from discovered tabs, if any."""
        source = tabs if tabs is not None else self._tabs
        if not source:
            return None
        return source[0].page

    async def verify_mis_session(self, page: Page) -> MisSessionStatus:
        """Verify the current page is an authenticated MIS admin page.

        Checks:
        1. URL contains MIS patterns (/rmmis/admin, mis_reports/)
        2. Not on login page
        3. MIS menu elements are visible (optional fallback)

        Returns MisSessionStatus with valid=True or error_code.
        """
        url = page.url.lower()

        has_mis_url = any(pattern in url for pattern in MIS_URL_PATTERNS)
        if not has_mis_url:
            # Public portal pages (not MIS admin)
            public_patterns = ("/madad/final", "/madad/final/home", "/madad/final/index")
            is_public = any(p in url for p in public_patterns)
            if is_public:
                logger.warning("MIS session lost: URL is public portal: %s", url[:100])
                return MisSessionStatus(
                    valid=False,
                    error_code="MIS_SESSION_LOST",
                    error="Current page is public RailMadad portal, not authenticated MIS",
                )

        if await self.is_login_page(page):
            logger.warning("MIS session lost: login page detected")
            return MisSessionStatus(
                valid=False,
                error_code="RAILMADAD_NOT_LOGGED_IN",
                error="Session expired or not logged in",
            )

        if not has_mis_url:
            menu_visible = await self._verify_mis_menu(page)
            if not menu_visible:
                logger.warning("MIS session lost: no MIS URL pattern and menu not visible")
                return MisSessionStatus(
                    valid=False,
                    error_code="MIS_SESSION_LOST",
                    error="Not on MIS admin page",
                )

        logger.debug("MIS session verified: %s", url[:100])
        return MisSessionStatus(valid=True)

    async def _verify_mis_menu(self, page: Page) -> bool:
        """Check if MIS menu elements are visible on the page."""
        for selector in MIS_MENU_SELECTORS:
            try:
                count = await asyncio.wait_for(
                    page.locator(selector).count(),
                    timeout=2.0,
                )
                if count > 0:
                    visible = await page.locator(selector).first.is_visible()
                    if visible:
                        return True
            except asyncio.TimeoutError:
                continue
            except Exception as exc:
                logger.debug("Error checking MIS menu selector %s: %s", selector, exc)
        return False

    def _is_authenticated_mis_url(self, url: str) -> bool:
        lower = url.lower()
        if any(p in lower for p in ("/madad/final",)):
            # Public portal — not MIS admin
            if "/rmmis/" not in lower:
                return False
        return any(pattern in lower for pattern in MIS_URL_PATTERNS)

    async def find_authenticated_mis_page(
        self,
        browser: Browser,
        *,
        prefer_url_fragment: str | None = None,
    ) -> Page | None:
        """Scan all contexts/pages and return a valid MIS admin page if any."""
        tabs = await self.discover_tabs(browser)
        candidates: list[TabInfo] = []
        for tab in tabs:
            url = tab.url.lower()
            if "/rmmis/admin" in url or "mis_reports/" in url or "/rmmis/" in url:
                if "/madad/final" in url and "/rmmis/" not in url:
                    continue
                candidates.append(tab)

        if not candidates:
            return None

        best = max(
            candidates,
            key=lambda tab: self._tab_priority(tab, prefer_url_fragment),
        )
        status = await self.verify_mis_session(best.page)
        if status.valid:
            return best.page

        # Prefer any candidate that is not a login page even if menu check is soft
        for tab in sorted(
            candidates,
            key=lambda t: self._tab_priority(t, prefer_url_fragment),
            reverse=True,
        ):
            if await self.is_login_page(tab.page):
                continue
            if self._is_authenticated_mis_url(tab.url):
                return tab.page
        return None

    async def ensure_authenticated_mis_page(
        self,
        browser: Browser,
        current_page: Page | None = None,
        *,
        prefer_url_fragment: str | None = None,
        allow_home_retry: bool = True,
    ) -> Page:
        """Return an authenticated MIS page, reacquiring from other tabs if needed.

        Ignores public RailMadad tabs when a valid /rmmis/admin page still exists.
        Raises MisSessionError only when no authenticated MIS page exists.
        """
        # 1) Prefer current page if it is already valid MIS (and matches preferred report)
        if current_page is not None:
            status = await self.verify_mis_session(current_page)
            if status.valid:
                from app.automation.navigation import url_matches_report_fragment

                preferred_ok = (
                    prefer_url_fragment is None
                    or url_matches_report_fragment(
                        current_page.url or "", prefer_url_fragment
                    )
                )
                if preferred_ok:
                    await self.activate_tab(current_page)
                    return current_page

            # Current page may be public / popup / wrong report — look for sibling MIS tab
            mis_page = await self.find_authenticated_mis_page(
                browser,
                prefer_url_fragment=prefer_url_fragment,
            )
            if mis_page is not None:
                await self.activate_tab(mis_page)
                logger.info(
                    "Reacquired MIS page after public/popup diversion: %s",
                    mis_page.url[:120],
                )
                return mis_page

            if allow_home_retry and self._is_authenticated_mis_url(current_page.url):
                # Soft retry: navigate once to MIS home
                try:
                    origin = f"{urlparse(current_page.url).scheme}://{urlparse(current_page.url).netloc}"
                    home = f"{origin}/rmmis/admin/home.jsp"
                    await current_page.goto(home, wait_until="domcontentloaded", timeout=30000)
                    status = await self.verify_mis_session(current_page)
                    if status.valid:
                        await self.activate_tab(current_page)
                        return current_page
                except Exception as exc:
                    logger.warning("MIS home retry failed: %s", exc)

            # Prefer fragment mismatch is recoverable via caller navigate; only raise when invalid.
            if not status.valid:
                raise MisSessionError(status)
            # Valid MIS but wrong report — return current so caller can navigate_to_report.
            await self.activate_tab(current_page)
            return current_page

        # 2) No current page — scan browser
        mis_page = await self.find_authenticated_mis_page(
            browser,
            prefer_url_fragment=prefer_url_fragment,
        )
        if mis_page is not None:
            await self.activate_tab(mis_page)
            return mis_page

        # 3) Last resort: from any RailMadad tab, navigate once to MIS admin home
        if allow_home_retry:
            tabs = await self.discover_tabs(browser)
            for tab in tabs:
                if not tab.is_railmadad:
                    continue
                try:
                    parsed = urlparse(tab.url)
                    if not parsed.scheme or not parsed.netloc:
                        continue
                    home = f"{parsed.scheme}://{parsed.netloc}/rmmis/admin/home.jsp"
                    logger.info("Attempting MIS home navigation from %s -> %s", tab.url[:80], home)
                    await tab.page.goto(home, wait_until="domcontentloaded", timeout=30000)
                    status = await self.verify_mis_session(tab.page)
                    if status.valid:
                        await self.activate_tab(tab.page)
                        return tab.page
                except Exception as exc:
                    logger.warning("MIS home navigation failed: %s", exc)

        raise MisSessionError(
            MisSessionStatus(
                valid=False,
                error_code="MIS_SESSION_LOST",
                error="No authenticated MIS admin page found in browser",
            )
        )

    async def close_temporary_and_reacquire(
        self,
        browser: Browser,
        temporary_page: Page,
        mis_page: Page,
    ) -> Page:
        """Close a popup/print page and reacquire the original MIS page."""
        try:
            if temporary_page != mis_page and not temporary_page.is_closed():
                await temporary_page.close()
        except Exception as exc:
            logger.debug("Could not close temporary page: %s", exc)
        return await self.ensure_authenticated_mis_page(browser, mis_page)
