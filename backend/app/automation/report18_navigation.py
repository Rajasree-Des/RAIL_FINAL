"""Report Vande Bharat portal navigation via MIS Reports sidebar.

Opens menu item **18) Vande Bharat Report** (and close label variants).
Prefer menu navigation over URL-only goto so the form shell loads correctly.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from playwright.async_api import FrameLocator, Page, TimeoutError as PlaywrightTimeoutError

from app.automation.config import config
from app.automation.report18_filters import (
    FORM_CONTROL_LABELS,
    FORM_HEADING_MARKERS,
    REPORT18_LOG_PREFIX,
    REPORT18_TAB_LABEL,
    REPORT18_URL_FRAGMENT,
)
from app.automation.utils import ensure_directory, log_automation_event
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)

MIS_REPORTS_LABEL = "MIS Reports"
TAB18_MENU_LABEL = REPORT18_TAB_LABEL
TAB18_MENU_PATTERN = re.compile(
    r"^18\)\s*Vande\s*Bharat(?:\s*Report)?$",
    re.IGNORECASE,
)
_TAB18_MAX_LABEL_LEN = 56

NAV_STAGE = "report18_navigation"
NAV_ERROR_MESSAGE = (
    "Report Vande Bharat failed: form did not load after selecting "
    "MIS Reports → 18) Vande Bharat Report."
)


class Report18NavigationError(AppException):
    """Raised when Report 18 menu navigation / form load fails."""

    def __init__(self, message: str = NAV_ERROR_MESSAGE, *, stage: str = NAV_STAGE) -> None:
        super().__init__(message=message, code="REPORT18_NAVIGATION_FAILED")
        self.stage = stage


def normalize_menu_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ").strip())


def menu_text_matches_tab18(text: str) -> bool:
    """True for the leaf sidebar row 18) Vande Bharat Report."""
    compact = normalize_menu_text(text)
    if not compact:
        return False
    if len(compact) > _TAB18_MAX_LABEL_LEN:
        return False
    # Reject multi-item sidebar blobs that include neighboring numbers.
    if re.search(r"(?<!\d)(?:16|17|19|20)\)", compact):
        return False
    if normalize_menu_text(TAB18_MENU_LABEL).lower() == compact.lower():
        return True
    if TAB18_MENU_PATTERN.match(compact):
        return True
    # Broader leaf match: starts with 18) and mentions Vande Bharat.
    return bool(
        re.match(r"^18\)", compact, re.IGNORECASE)
        and re.search(r"vande\s*bharat", compact, re.IGNORECASE)
    )


def _log_step(message: str, **fields: Any) -> None:
    logger.info("%s %s", REPORT18_LOG_PREFIX, message)
    log_automation_event(logger, f"report18_{message.lower().replace(' ', '_')}", **fields)


async def _save_nav_diagnostics(
    page: Page,
    *,
    run_id: str,
    reason: str,
    mis_expanded: bool | None = None,
    tab18_clicked: bool | None = None,
) -> None:
    dest = ensure_directory(Path(config.debug_screenshots_dir) / "report18_nav")
    stem = f"report18_nav_{run_id[:8]}_{reason}"
    try:
        await page.screenshot(path=str(dest / f"{stem}.png"), full_page=True)
    except Exception as exc:
        logger.warning("report18 nav screenshot failed: %s", exc)
    try:
        html = await page.content()
        (dest / f"{stem}.html").write_text(html[:500_000], encoding="utf-8")
    except Exception as exc:
        logger.warning("report18 nav html dump failed: %s", exc)

    log_automation_event(
        logger,
        "report18_navigation_failed",
        stage=NAV_STAGE,
        reason=reason,
        url=page.url,
        mis_expanded=mis_expanded,
        tab18_clicked=tab18_clicked,
        diagnostic_dir=str(dest),
    )


async def _find_mis_reports_control(page: Page) -> Any:
    candidates = [
        page.get_by_role("button", name=MIS_REPORTS_LABEL, exact=True),
        page.get_by_role("link", name=MIS_REPORTS_LABEL, exact=True),
        page.get_by_text(MIS_REPORTS_LABEL, exact=True),
        page.locator(f"text={MIS_REPORTS_LABEL}"),
    ]
    for loc in candidates:
        try:
            first = loc.first
            if await first.count() > 0 and await first.is_visible():
                return first
        except Exception:
            continue
    all_mis = page.locator("body *").filter(
        has_text=re.compile(r"^\s*MIS\s*Reports\s*$", re.I)
    )
    if await all_mis.count() > 0:
        return all_mis.first
    return None


async def _find_tab18_control(page: Page) -> Any:
    for ctor in (
        lambda: page.get_by_role("link", name=TAB18_MENU_LABEL, exact=True),
        lambda: page.get_by_role("button", name=TAB18_MENU_LABEL, exact=True),
        lambda: page.get_by_role("menuitem", name=TAB18_MENU_LABEL, exact=True),
        lambda: page.get_by_text(TAB18_MENU_LABEL, exact=True),
    ):
        try:
            loc = ctor().first
            if await loc.count() > 0 and await loc.is_visible():
                return loc
        except Exception:
            continue

    pattern_loc = page.get_by_text(
        re.compile(r"18\)\s*Vande\s*Bharat(?:\s*Report)?", re.I)
    )
    try:
        pcount = min(await pattern_loc.count(), 20)
    except Exception:
        pcount = 0
    pattern_hits: list[tuple[int, Any]] = []
    for i in range(pcount):
        item = pattern_loc.nth(i)
        try:
            text = normalize_menu_text(await item.inner_text(timeout=500))
            if not menu_text_matches_tab18(text):
                continue
            if await item.is_visible():
                pattern_hits.append((len(text), item))
        except Exception:
            continue
    if pattern_hits:
        pattern_hits.sort(key=lambda t: t[0])
        return pattern_hits[0][1]

    candidates = page.locator(
        "a, button, li, span, div, td, [role='menuitem'], [role='treeitem']"
    )
    try:
        count = min(await candidates.count(), 250)
    except Exception:
        count = 0
    hits: list[tuple[int, Any]] = []
    for i in range(count):
        item = candidates.nth(i)
        try:
            text = normalize_menu_text(await item.inner_text(timeout=500))
        except Exception:
            continue
        if not menu_text_matches_tab18(text):
            continue
        try:
            if not await item.is_visible():
                continue
        except Exception:
            pass
        hits.append((len(text), item))
    if hits:
        hits.sort(key=lambda t: t[0])
        return hits[0][1]
    return None


async def _is_tab18_visible(page: Page) -> bool:
    loc = await _find_tab18_control(page)
    if loc is None:
        return False
    try:
        return await loc.is_visible()
    except Exception:
        return False


async def ensure_mis_reports_expanded(page: Page) -> bool:
    if await _is_tab18_visible(page):
        log_automation_event(logger, "report18_mis_already_expanded")
        return True

    control = await _find_mis_reports_control(page)
    if control is None:
        log_automation_event(logger, "report18_mis_reports_not_found")
        return False

    log_automation_event(logger, "report18_mis_reports_click")
    await control.click(timeout=8_000)

    for _ in range(20):
        if await _is_tab18_visible(page):
            log_automation_event(logger, "report18_mis_submenu_expanded")
            return True
        try:
            await page.wait_for_timeout(250)
        except Exception:
            pass

    if not await _is_tab18_visible(page):
        control = await _find_mis_reports_control(page)
        if control is not None:
            await control.click(timeout=5_000)
            for _ in range(12):
                if await _is_tab18_visible(page):
                    return True
                await page.wait_for_timeout(250)
    return await _is_tab18_visible(page)


async def click_tab18_vande_bharat(page: Page) -> bool:
    loc = await _find_tab18_control(page)
    if loc is None:
        return False
    try:
        await loc.scroll_into_view_if_needed(timeout=5_000)
    except Exception:
        pass
    _log_step("Opening Report 18", label=TAB18_MENU_LABEL)
    await loc.click(timeout=8_000)
    return True


async def _text_present(ctx: Page | FrameLocator, text: str) -> bool:
    try:
        if await ctx.get_by_text(text, exact=False).count() > 0:
            return True
    except Exception:
        pass
    try:
        if await ctx.locator(f"text={text}").count() > 0:
            return True
    except Exception:
        pass
    return False


async def _count_form_signals(ctx: Page | FrameLocator) -> tuple[int, list[str]]:
    found: list[str] = []
    for label in FORM_CONTROL_LABELS:
        try:
            loc = ctx.locator(
                f"text={label}, label:has-text('{label}'), "
                f"td:has-text('{label}'), th:has-text('{label}'), "
                f"button:has-text('{label}'), input[value='{label}']"
            ).first
            if await loc.count() > 0:
                found.append(label)
        except Exception:
            continue
    for heading in FORM_HEADING_MARKERS:
        if await _text_present(ctx, heading):
            found.append(f"heading:{heading}")
            break
    for sel in ("#fromInput", "#toInput", "select", "form", "table"):
        try:
            if await ctx.locator(sel).count() > 0:
                found.append(f"sel:{sel}")
        except Exception:
            pass
    return len(found), found


async def is_vande_bharat_form(ctx: Page | FrameLocator) -> tuple[bool, list[str]]:
    """True only for Vande Bharat Train Report — never Comprehensive / other MIS forms.

    Report 1 shares From/To/Submit controls, and the sidebar always contains
    "18) Vande Bharat Report", so date-only or short-label matches are rejected.
    """
    score, found = await _count_form_signals(ctx)
    has_heading = any(f.startswith("heading:") for f in found)
    # Require the unique page title; generic date fields alone are not enough.
    if has_heading and score >= 2:
        return True, found
    return False, found


def url_is_vande_bharat(page_url: str) -> bool:
    """True when the admin shell targets vandebharatreport (not report1 / others)."""
    from app.automation.navigation import url_matches_report_fragment

    return url_matches_report_fragment(page_url or "", REPORT18_URL_FRAGMENT)


async def resolve_report18_form_context(page: Page) -> Page | FrameLocator | None:
    # Prefer URL identity when the shell already landed on vandebharatreport.
    url_ok = url_is_vande_bharat(page.url)

    try:
        for frame in page.frames:
            if frame == page.main_frame:
                continue
            try:
                fl = None
                if frame.name:
                    fl = page.frame_locator(f"iframe[name='{frame.name}']")
                if fl is None and frame.url:
                    fl = page.frame_locator(
                        "iframe[src*='vandebharatreport'], iframe[src*='mis_reports']"
                    )
                if fl is not None:
                    ok, found = await is_vande_bharat_form(fl)
                    if ok:
                        log_automation_event(
                            logger,
                            "report18_form_frame_resolved",
                            found=found[:12],
                            frame_url=frame.url,
                            url_ok=url_ok,
                        )
                        return fl
            except Exception:
                continue
    except Exception:
        pass

    from app.automation.selectors import selectors

    for frame_selector in (selectors.report1_frame or "").split(","):
        frame_selector = frame_selector.strip()
        if not frame_selector:
            continue
        try:
            fl = page.frame_locator(frame_selector).first
            ok, found = await is_vande_bharat_form(fl)
            if ok:
                log_automation_event(
                    logger,
                    "report18_form_frame_resolved",
                    found=found[:12],
                    frame_selector=frame_selector,
                    url_ok=url_ok,
                )
                return fl
        except Exception:
            continue

    ok, found = await is_vande_bharat_form(page)
    if ok:
        log_automation_event(
            logger,
            "report18_form_main_page_resolved",
            found=found[:12],
            url_ok=url_ok,
            url=page.url,
        )
        return page

    # URL already on vandebharatreport but heading not yet painted — treat as pending.
    if url_ok:
        log_automation_event(
            logger,
            "report18_url_matched_waiting_heading",
            url=page.url,
        )
    return None


async def wait_for_report18_form(page: Page, *, timeout_ms: int = 25_000) -> Page | FrameLocator:
    deadline_slices = max(timeout_ms // 500, 10)
    last_score = 0
    last_found: list[str] = []
    for _ in range(deadline_slices):
        ctx = await resolve_report18_form_context(page)
        if ctx is not None:
            return ctx
        score, found = await _count_form_signals(page)
        last_score, last_found = score, found
        try:
            await page.wait_for_timeout(500)
        except Exception:
            pass
    log_automation_event(
        logger,
        "report18_form_wait_timeout",
        last_score=last_score,
        last_found=last_found,
        url=page.url,
    )
    raise Report18NavigationError(NAV_ERROR_MESSAGE)


async def navigate_report18_via_menu(
    page: Page,
    *,
    run_id: str = "",
) -> Page | FrameLocator:
    """Open MIS Reports → 18) Vande Bharat Report and wait for the form."""
    log_automation_event(
        logger,
        "report18_menu_navigation_started",
        url=page.url,
        run_id=run_id,
        target_tab=TAB18_MENU_LABEL,
    )
    _log_step("Opening MIS Reports", run_id=run_id)

    try:
        existing = await resolve_report18_form_context(page)
        if existing is not None:
            _log_step("Opening Report 18", run_id=run_id, already_loaded=True)
            log_automation_event(
                logger,
                "report18_form_already_loaded",
                url=page.url,
                run_id=run_id,
            )
            return existing
    except Exception:
        pass

    try:
        await page.wait_for_load_state("domcontentloaded", timeout=15_000)
    except PlaywrightTimeoutError:
        pass
    try:
        await page.get_by_text("MIS Reports", exact=True).first.wait_for(
            state="visible", timeout=20_000
        )
    except Exception as exc:
        await _save_nav_diagnostics(page, run_id=run_id or "na", reason="no_mis_shell")
        raise Report18NavigationError(
            f"{NAV_ERROR_MESSAGE} (admin shell / MIS Reports not ready: {exc})"
        ) from exc

    expanded = await ensure_mis_reports_expanded(page)
    if not expanded:
        await _save_nav_diagnostics(
            page, run_id=run_id or "na", reason="submenu_not_expanded", mis_expanded=False
        )
        raise Report18NavigationError(
            f"{NAV_ERROR_MESSAGE} (MIS Reports submenu did not expand)."
        )

    clicked = await click_tab18_vande_bharat(page)
    if not clicked:
        await ensure_mis_reports_expanded(page)
        clicked = await click_tab18_vande_bharat(page)
    if not clicked:
        await _save_nav_diagnostics(
            page,
            run_id=run_id or "na",
            reason="tab18_not_found",
            mis_expanded=True,
            tab18_clicked=False,
        )
        raise Report18NavigationError(
            f"{NAV_ERROR_MESSAGE} (menu item '{TAB18_MENU_LABEL}' not found)."
        )

    try:
        form_ctx = await wait_for_report18_form(page)
    except Report18NavigationError:
        await _save_nav_diagnostics(
            page,
            run_id=run_id or "na",
            reason="form_blank_after_tab18",
            mis_expanded=True,
            tab18_clicked=True,
        )
        raise

    log_automation_event(
        logger,
        "report18_menu_navigation_succeeded",
        url=page.url,
        run_id=run_id,
        target_tab=TAB18_MENU_LABEL,
    )
    return form_ctx
