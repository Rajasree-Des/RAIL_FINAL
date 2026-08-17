"""Portal recovery between report handlers (modals, navigation)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.automation.navigation import NavigationService
from app.automation.utils import log_automation_event

if TYPE_CHECKING:
    from playwright.async_api import Page

    from app.automation.reports import ReportDefinition
    from app.automation.session import SessionManager

logger = logging.getLogger(__name__)

_navigation = NavigationService()


async def close_visible_modals(page: "Page") -> None:
    """Best-effort close of open Bootstrap/jQuery modals."""
    close_buttons = page.locator(
        ".modal.show .close, .modal.show .btn-close, "
        "[role='dialog'] button[aria-label='Close'], "
        ".modal button:has-text('Close')"
    )
    if await close_buttons.count() == 0:
        return
    try:
        await close_buttons.first.click()
        await page.wait_for_selector(
            ".modal.show, #exampleModal.show",
            state="hidden",
            timeout=3_000,
        )
    except Exception:
        pass
    log_automation_event(logger, "portal_modal_closed")


async def recover_portal_between_reports(
    page: "Page",
    session: "SessionManager",
    next_report: "ReportDefinition",
) -> "Page":
    """Close stale UI state and navigate to the next report form."""
    await close_visible_modals(page)
    try:
        status = await session.verify_mis_session(page)
        if not status.valid:
            log_automation_event(
                logger,
                "portal_recovery_session_invalid",
                error_code=status.error_code,
            )
            return page
    except Exception:
        pass

    try:
        await _navigation.navigate_to_report(page, next_report)
        log_automation_event(
            logger,
            "portal_recovery_navigated",
            report_slug=next_report.slug,
            url_fragment=next_report.url_fragment,
        )
    except Exception as exc:
        log_automation_event(
            logger,
            "portal_recovery_navigation_failed",
            report_slug=next_report.slug,
            error=str(exc),
        )
    return page
