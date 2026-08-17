"""State-based page wait helpers for RailMadad browser automation.

Prefer condition polling over fixed sleeps. Every wait is bounded and logged.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from app.automation.table_refresh import LOADING_SELECTORS, wait_for_loaders
from app.automation.utils import log_automation_event
from app.automation.wait_utils import poll_until

if TYPE_CHECKING:
    from app.automation.filters import ReportRoot

logger = logging.getLogger(__name__)

CheckFn = Callable[[], Any | Awaitable[Any]]


def _ctx(
    *,
    report_slug: str = "",
    action: str = "",
    condition: str = "",
) -> dict[str, str]:
    out: dict[str, str] = {}
    if report_slug:
        out["report_slug"] = report_slug
    if action:
        out["action"] = action
    if condition:
        out["wait_condition"] = condition
    return out


async def wait_for_state(
    check: CheckFn,
    *,
    timeout_seconds: float = 30.0,
    interval_seconds: float = 0.08,
    reason: str = "",
    report_slug: str = "",
    action: str = "",
    condition: str = "",
) -> bool:
    """Poll until ``check`` returns truthy or timeout elapses."""
    log_automation_event(
        logger,
        "page_wait_started",
        reason=reason or condition or "state_poll",
        timeout_seconds=timeout_seconds,
        **_ctx(report_slug=report_slug, action=action, condition=condition),
    )
    started = time.perf_counter()
    ok = await poll_until(
        check,
        interval_seconds=interval_seconds,
        timeout_seconds=timeout_seconds,
        reason=reason or condition or "page_wait",
    )
    log_automation_event(
        logger,
        "page_wait_completed",
        reason=reason or condition or "state_poll",
        success=ok,
        elapsed_seconds=round(time.perf_counter() - started, 3),
        **_ctx(report_slug=report_slug, action=action, condition=condition),
    )
    return ok


async def wait_for_portal_settle(
    root: Any,
    page: Page,
    *,
    timeout_seconds: float = 4.0,
    reason: str = "portal_settle",
    report_slug: str = "",
    action: str = "",
) -> bool:
    """Wait until loading overlays disappear after a filter/DOM change."""

    async def _loaders_cleared() -> bool:
        for selector in LOADING_SELECTORS:
            for scope in (root, page):
                try:
                    loader = scope.locator(selector)
                    if await loader.count() > 0 and await loader.first.is_visible():
                        return False
                except Exception:
                    continue
        return True

    async def _ready() -> bool:
        await wait_for_loaders(root, page, timeout_ms=min(int(timeout_seconds * 1000), 2_000))
        return await _loaders_cleared()

    return await wait_for_state(
        _ready,
        timeout_seconds=timeout_seconds,
        interval_seconds=0.05,
        reason=reason,
        report_slug=report_slug,
        action=action,
        condition="loaders_cleared",
    )


async def wait_for_cascade_settle(
    root: Any,
    page: Page,
    *,
    field_name: str = "",
    timeout_seconds: float = 3.0,
    report_slug: str = "",
) -> bool:
    """Wait after cascading select change until portal finishes updating dependents."""
    action = f"filter_cascade:{field_name}" if field_name else "filter_cascade"
    return await wait_for_portal_settle(
        root,
        page,
        timeout_seconds=timeout_seconds,
        reason="cascading_filter_settle",
        report_slug=report_slug,
        action=action,
    )


async def wait_for_report_form_controls(
    page: Page,
    *,
    timeout_seconds: float = 12.0,
    report_slug: str = "",
) -> bool:
    """Wait until report form controls exist on main page or in an iframe."""

    async def _controls_present() -> bool:
        if await page.locator("select, input, textarea, form").count() > 0:
            return True
        iframe_count = await page.locator("iframe").count()
        for index in range(iframe_count):
            frame_loc = page.frame_locator("iframe").nth(index)
            try:
                if await frame_loc.locator("input, select, textarea").count() > 0:
                    return True
            except Exception:
                continue
        return False

    return await wait_for_state(
        _controls_present,
        timeout_seconds=timeout_seconds,
        interval_seconds=0.1,
        reason="report_form_controls",
        report_slug=report_slug,
        action="navigation",
        condition="form_controls_visible",
    )


async def wait_for_navigation_settled(
    page: Page,
    *,
    timeout_seconds: float = 15.0,
    report_slug: str = "",
    url_fragment: str = "",
) -> bool:
    """Wait for DOM ready + optional URL fragment after navigation."""
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=int(timeout_seconds * 1000))
    except PlaywrightTimeoutError:
        pass

    if url_fragment:
        from app.automation.navigation import url_matches_report_fragment

        async def _url_ok() -> bool:
            return url_matches_report_fragment(page.url, url_fragment)

        if not await wait_for_state(
            _url_ok,
            timeout_seconds=min(timeout_seconds, 8.0),
            interval_seconds=0.1,
            reason="nav_url_fragment",
            report_slug=report_slug,
            action="navigation",
            condition=f"url_contains:{url_fragment}",
        ):
            return False

    return await wait_for_report_form_controls(
        page,
        timeout_seconds=min(timeout_seconds, 10.0),
        report_slug=report_slug,
    )


async def wait_for_menu_item(
    visibility_check: CheckFn,
    *,
    timeout_seconds: float = 6.0,
    report_slug: str = "",
    menu_item: str = "",
) -> bool:
    """Poll until a sidebar/menu item becomes visible (MIS Reports expansion)."""
    return await wait_for_state(
        visibility_check,
        timeout_seconds=timeout_seconds,
        interval_seconds=0.08,
        reason="menu_item_visible",
        report_slug=report_slug,
        action="menu_navigation",
        condition=f"menu_visible:{menu_item}" if menu_item else "menu_visible",
    )


async def wait_for_form_context(
    resolve_fn: Callable[[], Awaitable[Any | None]],
    *,
    timeout_seconds: float = 25.0,
    report_slug: str = "",
    form_name: str = "",
) -> Any:
    """Poll until ``resolve_fn`` returns a non-None form context (page/frame)."""
    result: Any = None

    async def _resolved() -> bool:
        nonlocal result
        result = await resolve_fn()
        return result is not None

    ok = await wait_for_state(
        _resolved,
        timeout_seconds=timeout_seconds,
        interval_seconds=0.1,
        reason="form_context",
        report_slug=report_slug,
        action="navigation",
        condition=f"form_ready:{form_name}" if form_name else "form_ready",
    )
    if not ok or result is None:
        return None
    return result
