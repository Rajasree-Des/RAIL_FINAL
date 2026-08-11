"""Playwright browser connection via Chrome DevTools Protocol."""

import logging
from typing import TYPE_CHECKING

import httpx
from playwright.async_api import Browser, async_playwright
from playwright.async_api import Error as PlaywrightError

from app.core.exceptions import AppException

if TYPE_CHECKING:
    from playwright.async_api import Playwright

logger = logging.getLogger(__name__)

DEFAULT_CDP_URL = "http://127.0.0.1:9222"


class BrowserConnectionError(AppException):
    """Raised when Playwright cannot start or attach to a Chromium CDP endpoint."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="BROWSER_CONNECTION_ERROR")


CDP_PROBE_TIMEOUT_SECONDS = 2.0


async def probe_cdp_reachable(
    cdp_url: str = DEFAULT_CDP_URL,
    *,
    timeout: float = CDP_PROBE_TIMEOUT_SECONDS,
) -> None:
    """Verify the Chromium CDP endpoint responds before starting automation."""
    url = cdp_url.rstrip("/") + "/json/version"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
        if response.status_code != 200:
            raise BrowserConnectionError(
                f"Cannot connect to Chromium at {cdp_url} (HTTP {response.status_code}). "
                "Is Chrome running with --remote-debugging-port=9222?"
            )
    except BrowserConnectionError:
        raise
    except Exception as exc:
        raise BrowserConnectionError(
            f"Cannot connect to Chromium at {cdp_url}. "
            "Is Chrome running with --remote-debugging-port=9222?"
        ) from exc


def _log_browser_state(browser: Browser, stage: str) -> None:
    """Log browser context and page counts with URLs for CDP diagnostics."""
    contexts = browser.contexts
    total_pages = sum(len(context.pages) for context in contexts)
    logger.info(
        "CDP browser state [%s]: %d context(s), %d page(s)",
        stage,
        len(contexts),
        total_pages,
    )
    for context_index, context in enumerate(contexts):
        pages = context.pages
        logger.info(
            "CDP browser state [%s]: context=%d has %d page(s)",
            stage,
            context_index,
            len(pages),
        )
        for page_index, page in enumerate(pages):
            logger.info(
                "CDP browser state [%s]: context=%d page=%d url=%s",
                stage,
                context_index,
                page_index,
                page.url,
            )


class BrowserManager:
    """Manages a Playwright session attached to an existing Chromium browser."""

    def __init__(self, cdp_url: str = DEFAULT_CDP_URL) -> None:
        self._cdp_url = cdp_url
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    @property
    def browser(self) -> Browser | None:
        return self._browser

    def is_browser_connected(self) -> bool:
        """Return True when the Playwright CDP browser handle is still usable."""
        if self._browser is None:
            return False
        try:
            _ = self._browser.contexts
            return True
        except PlaywrightError:
            return False
        except Exception:
            return False

    async def reconnect(self) -> Browser:
        """Drop a dead Playwright session and attach again to the CDP endpoint."""
        logger.info("browser_reconnect_start cdp_url=%s", self._cdp_url)
        await self.close()
        browser = await self.connect()
        logger.info("playwright_driver_started cdp_connected contexts=%d", len(browser.contexts))
        return browser

    async def connect(self) -> Browser:
        """Start Playwright and attach to Chromium over CDP."""
        if self._browser is not None:
            raise BrowserConnectionError("BrowserManager is already connected")

        logger.info("playwright_driver_started")
        try:
            self._playwright = await async_playwright().start()
        except PlaywrightError as exc:
            cause = exc.__cause__ or exc.__context__
            if isinstance(cause, NotImplementedError):
                logger.exception("Failed to start Playwright (event loop subprocess unsupported)")
                raise BrowserConnectionError(
                    "Failed to start Playwright: event loop does not support subprocesses. "
                    "On Windows, restart the backend; Playwright runs in a worker thread."
                ) from exc
            detail = str(exc).strip() or repr(exc)
            logger.exception("Failed to start Playwright")
            raise BrowserConnectionError(f"Failed to start Playwright: {detail}") from exc
        except NotImplementedError as exc:
            logger.exception("Failed to start Playwright (event loop subprocess unsupported)")
            raise BrowserConnectionError(
                "Failed to start Playwright: event loop does not support subprocesses. "
                "On Windows, restart the backend after updating; Playwright runs in a worker thread."
            ) from exc
        except Exception as exc:
            logger.exception("Failed to start Playwright")
            raise BrowserConnectionError(f"Failed to start Playwright: {exc}") from exc

        logger.info("cdp_connect_start: attaching to Chromium via CDP at %s", self._cdp_url)
        try:
            self._browser = await self._playwright.chromium.connect_over_cdp(self._cdp_url)
        except PlaywrightError as exc:
            logger.exception(
                "cdp_connect_failed: cannot attach to Chromium at %s", self._cdp_url
            )
            await self._stop_playwright()
            raise BrowserConnectionError(
                f"Cannot connect to Chromium at {self._cdp_url}. "
                "Is Chrome running with --remote-debugging-port=9222?"
            ) from exc
        except Exception as exc:
            logger.exception(
                "cdp_connect_failed: cannot attach to Chromium at %s", self._cdp_url
            )
            await self._stop_playwright()
            raise BrowserConnectionError(
                f"Cannot connect to Chromium at {self._cdp_url}. "
                "Is Chrome running with --remote-debugging-port=9222?"
            ) from exc

        logger.info(
            "cdp_connected contexts=%d cdp_url=%s",
            len(self._browser.contexts),
            self._cdp_url,
        )
        _log_browser_state(self._browser, "after_connect")
        return self._browser

    async def close(self) -> None:
        """Disconnect from the browser and stop Playwright. Safe to call multiple times."""
        if self._browser is None and self._playwright is None:
            logger.info("cdp_disconnect_skip: no active Playwright or browser session")
            return

        logger.info("Closing browser connection")

        if self._browser is not None:
            _log_browser_state(self._browser, "before_disconnect")
            logger.info("cdp_disconnect_start: closing browser CDP session")
            try:
                await self._browser.close()
            except PlaywrightError as exc:
                logger.warning("Error closing browser connection: %s", exc)
            except Exception as exc:
                logger.warning("Error closing browser connection: %s", exc)
            finally:
                self._browser = None

        if self._playwright is not None:
            logger.info("cdp_disconnect_start: stopping Playwright")
        await self._stop_playwright()

    async def _stop_playwright(self) -> None:
        if self._playwright is None:
            return

        try:
            await self._playwright.stop()
        except PlaywrightError as exc:
            logger.warning("Error stopping Playwright: %s", exc)
        except Exception as exc:
            logger.warning("Error stopping Playwright: %s", exc)
        finally:
            self._playwright = None
