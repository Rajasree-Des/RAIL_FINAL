"""Central CDP session health checks and MIS page reacquisition."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from playwright.async_api import Error as PlaywrightError

from app.automation.utils import log_automation_event

if TYPE_CHECKING:
    from playwright.async_api import Browser, Page

    from app.automation.browser import BrowserManager
    from app.automation.session import SessionManager

logger = logging.getLogger(__name__)

RECOVERABLE_CONNECTION_MARKERS = (
    "connection closed",
    "target closed",
    "page closed",
    "browser disconnected",
    "driver pipe closed",
    "browser has been closed",
)


def _preferred_url_ok(page_url: str, prefer_url_fragment: str | None) -> bool:
    if prefer_url_fragment is None:
        return True
    from app.automation.navigation import url_matches_report_fragment

    return url_matches_report_fragment(page_url, prefer_url_fragment)


def is_recoverable_connection_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    if isinstance(exc, PlaywrightError) and any(m in message for m in RECOVERABLE_CONNECTION_MARKERS):
        return True
    return any(m in message for m in RECOVERABLE_CONNECTION_MARKERS)


def connection_error_code(exc: BaseException) -> str:
    message = str(exc).lower()
    if "mis session" in message or "not logged in" in message:
        return "MIS_SESSION_LOST"
    if "playwright" in message and "closed" in message:
        return "PLAYWRIGHT_DRIVER_CLOSED"
    return "CDP_CONNECTION_LOST"


async def ensure_live_mis_page(
    *,
    run_id: str,
    report_slug: str,
    manager: "BrowserManager",
    session: "SessionManager",
    page: "Page | None",
    prefer_url_fragment: str | None = None,
) -> "Page":
    """Verify Playwright/CDP and return a live authenticated MIS page reference."""
    browser = manager.browser
    if browser is None or not manager.is_browser_connected():
        log_automation_event(
            logger,
            "browser_connection_lost",
            run_id=run_id,
            report_slug=report_slug,
            stage="ensure_live_mis_page",
        )
        browser = await manager.reconnect()
        session.bind_browser(browser)
        page = None
        log_automation_event(
            logger,
            "browser_reconnect_succeeded",
            run_id=run_id,
            report_slug=report_slug,
        )

    if page is not None and not page.is_closed():
        try:
            status = await session.verify_mis_session(page)
            preferred_ok = _preferred_url_ok(page.url or "", prefer_url_fragment)
            if status.valid and preferred_ok:
                await session.activate_tab(page)
                log_automation_event(
                    logger,
                    "mis_page_resolved",
                    run_id=run_id,
                    report_slug=report_slug,
                    page_url=page.url,
                    connection_state="healthy",
                )
                return page
        except Exception as exc:
            if not is_recoverable_connection_error(exc):
                raise
            log_automation_event(
                logger,
                "browser_connection_lost",
                run_id=run_id,
                report_slug=report_slug,
                stage="verify_current_page",
                error=str(exc),
            )

    live_page = await session.ensure_authenticated_mis_page(
        browser,
        None if page is not None and page.is_closed() else page,
        prefer_url_fragment=prefer_url_fragment,
    )
    log_automation_event(
        logger,
        "mis_page_resolved",
        run_id=run_id,
        report_slug=report_slug,
        page_url=live_page.url,
        connection_state="reacquired",
    )
    return live_page


async def reconnect_browser_session(
    *,
    run_id: str,
    report_slug: str,
    manager: "BrowserManager",
    session: "SessionManager",
) -> tuple["Browser", "Page"]:
    """Reconnect Playwright/CDP and resolve a fresh MIS page (no stale locators)."""
    log_automation_event(
        logger,
        "browser_reconnect_started",
        run_id=run_id,
        report_slug=report_slug,
    )
    try:
        browser = await manager.reconnect()
    except Exception as exc:
        log_automation_event(
            logger,
            "browser_reconnect_failed",
            run_id=run_id,
            report_slug=report_slug,
            error=str(exc),
        )
        raise
    session.bind_browser(browser)
    page = await ensure_live_mis_page(
        run_id=run_id,
        report_slug=report_slug,
        manager=manager,
        session=session,
        page=None,
    )
    log_automation_event(
        logger,
        "browser_reconnect_succeeded",
        run_id=run_id,
        report_slug=report_slug,
        page_url=page.url,
    )
    return browser, page
