"""Apply and verify RailMadad From Date before Report Submit (Phase 1/2/3)."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from playwright.async_api import Locator, Page

from app.automation.config import config
from app.automation.date_range import (
    ReportDateRange,
    get_context_date_range,
    resolve_phase1_from_date,
    resolve_phase1_to_date,
    resolve_portal_from_date,
)
from app.automation.filters import FilterService
from app.automation.report_keys import canonicalize_report_key
from app.automation.run_context import get_run_context
from app.automation.utils import ensure_directory, log_automation_event

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

PHASE2_REPORT_KEYS = frozenset({"train-no", "types"})
PHASE3_REPORT_KEYS = frozenset({"scr-train", "scr-station"})
PHASE1_TO_DATE_WAIT_MS = 10_000
PHASE1_TO_DATE_POLL_MS = 200

FROM_DATE_SELECTORS: tuple[str, ...] = (
    "div.fromDate input",
    "div.fromDate .form-group input",
    "label:text-is('From Date') + input",
    "div.form-group:has(label:text-is('From Date')) input",
    "label[for='fromInput'] + input",
    "#fromInput",
)

TO_DATE_SELECTORS: tuple[str, ...] = (
    "div.toDate input",
    "div.toDate .form-group input",
    "label:text-is('To Date') + input",
    "div.form-group:has(label:text-is('To Date')) input",
    "label[for='toInput'] + input",
    "#toInput",
)

_DISPATCH_EVENTS_JS = """(el, value) => {
    el.value = value;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    el.dispatchEvent(new Event('blur', { bubbles: true }));
}"""

_NATIVE_SETTER_JS = """(el, value) => {
    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype, 'value'
    ).set;
    nativeInputValueSetter.call(el, value);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    el.dispatchEvent(new Event('blur', { bubbles: true }));
}"""


class PortalFromDateError(Exception):
    """Raised when From Date cannot be applied or verified before Submit."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _is_phase2_report(report_slug: str) -> bool:
    return canonicalize_report_key(report_slug) in PHASE2_REPORT_KEYS


def _is_phase3_report(report_slug: str) -> bool:
    return canonicalize_report_key(report_slug) in PHASE3_REPORT_KEYS


def _event_prefix(report_slug: str) -> str:
    if _is_phase3_report(report_slug):
        return "phase3"
    if _is_phase2_report(report_slug):
        return "phase2"
    return "phase1"


def get_phase1_from_date() -> str:
    """Return the immutable run-level From Date (YYYY-MM-DD)."""
    ctx = get_run_context()
    if ctx is not None and ctx.phase1_from_date:
        return ctx.phase1_from_date
    return resolve_phase1_from_date()


def _resolve_expected_date_range() -> ReportDateRange:
    return get_context_date_range()


def _resolve_expected_from_date(report_slug: str) -> str:
    """Return the expected From Date for the given report slug."""
    _ = report_slug
    return _resolve_expected_date_range().iso_from()


def _resolve_expected_to_date(report_slug: str) -> str:
    """Return the expected To Date for the given report slug."""
    _ = report_slug
    return _resolve_expected_date_range().iso_to()


async def _resolve_locator(
    root: Locator,
    selectors: tuple[str, ...],
) -> tuple[Locator | None, str | None]:
    for selector in selectors:
        locator = root.locator(selector).first
        try:
            if await locator.count() > 0:
                return locator, selector
        except Exception:
            continue
    return None, None


async def _read_input_value(locator: Locator) -> str:
    try:
        value = await locator.input_value()
        if value is not None:
            return str(value).strip()
    except Exception:
        pass
    try:
        return str(
            await locator.evaluate("el => (el.value ?? '').trim()")
        ).strip()
    except Exception:
        return ""


async def _clear_and_fill(locator: Locator, value: str) -> None:
    try:
        await locator.focus()
    except Exception:
        pass
    try:
        await locator.fill("")
    except Exception:
        await locator.evaluate("(el) => { el.value = ''; }")
    try:
        await locator.fill(value)
    except Exception:
        await locator.click()
        await locator.fill(value)
    await locator.evaluate(_DISPATCH_EVENTS_JS, value)


async def _native_setter_fill(locator: Locator, value: str) -> None:
    await locator.evaluate(_NATIVE_SETTER_JS, value)


async def _wait_for_to_date_populated(
    to_locator: Locator,
    *,
    timeout_ms: int = PHASE1_TO_DATE_WAIT_MS,
    poll_ms: int = PHASE1_TO_DATE_POLL_MS,
) -> str:
    """Poll until the portal sets To Date (Report 1/2 JS init). Does not modify To Date."""
    deadline = asyncio.get_running_loop().time() + (timeout_ms / 1000)
    while asyncio.get_running_loop().time() < deadline:
        value = await _read_input_value(to_locator)
        if value:
            return value
        await asyncio.sleep(poll_ms / 1000)
    return ""


async def _bootstrap_phase1_to_date(
    to_locator: Locator,
    report_slug: str,
    *,
    run_id: str,
    source_name: str,
    selector_used: str | None,
    existing_from_date: str,
) -> str:
    """Initialize To Date to today when the portal leaves it blank (Report 1/2 only)."""
    expected_to_date = resolve_phase1_to_date()
    await _clear_and_fill(to_locator, expected_to_date)
    actual_to_date = await _read_input_value(to_locator)
    retry_count = 0

    if actual_to_date != expected_to_date:
        retry_count = 1
        await _native_setter_fill(to_locator, expected_to_date)
        actual_to_date = await _read_input_value(to_locator)

    if actual_to_date != expected_to_date:
        raise PortalFromDateError(
            "PORTAL_TO_DATE_MISSING",
            (
                f"To Date bootstrap failed: expected {expected_to_date}, "
                f"got {actual_to_date!r}"
            ),
        )

    _log_from_date_event(
        report_slug,
        "to_date_bootstrapped",
        run_id=run_id,
        source_name=source_name,
        expected_from_date=_resolve_expected_from_date(report_slug),
        actual_from_date=existing_from_date,
        actual_to_date=actual_to_date,
        selector_used=selector_used,
        retry_count=retry_count,
        expected_to_date=expected_to_date,
    )
    return actual_to_date


async def save_portal_from_date_failure_artifacts(
    page: Page,
    report_slug: str,
    *,
    run_id: str,
    source_name: str,
    error_code: str,
    expected_from_date: str,
    actual_from_date: str,
    actual_to_date: str,
    selector_used: str | None,
    retry_count: int,
) -> str | None:
    dest = ensure_directory(Path(config.screenshots_dir) / "filter_failures")
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    screenshot_path: str | None = None

    try:
        url = page.url
    except Exception:
        url = None

    meta_lines = [
        f"run_id={run_id}",
        f"report_slug={report_slug}",
        f"source_name={source_name}",
        f"error_code={error_code}",
        f"expected_from_date={expected_from_date}",
        f"actual_from_date={actual_from_date}",
        f"actual_to_date={actual_to_date}",
        f"selector_used={selector_used}",
        f"retry_count={retry_count}",
        f"url={url}",
        f"timestamp={timestamp}",
    ]
    meta_path = dest / f"portal_date_{timestamp}_{report_slug}.txt"
    try:
        meta_path.write_text("\n".join(meta_lines) + "\n", encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not write portal from-date failure metadata: %s", exc)

    try:
        html = await page.content()
        html_path = dest / f"portal_date_{timestamp}_{report_slug}.html"
        html_path.write_text(html, encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not write portal from-date failure HTML: %s", exc)

    try:
        screenshot_file = dest / f"portal_date_{timestamp}_{report_slug}.png"
        await page.screenshot(path=str(screenshot_file), full_page=True)
        screenshot_path = str(screenshot_file)
    except Exception as exc:
        logger.warning("Could not capture portal from-date failure screenshot: %s", exc)

    return screenshot_path


def _log_from_date_event(
    report_slug: str,
    event_suffix: str,
    *,
    run_id: str,
    source_name: str,
    expected_from_date: str,
    actual_from_date: str,
    actual_to_date: str,
    selector_used: str | None,
    retry_count: int,
    **extra: object,
) -> None:
    prefix = _event_prefix(report_slug)
    log_kwargs: dict[str, object] = {
        "run_id": run_id,
        "report_slug": report_slug,
        "expected_from_date": expected_from_date,
        "actual_from_date": actual_from_date,
        "actual_to_date": actual_to_date,
        "selector_used": selector_used,
        "retry_count": retry_count,
    }
    if prefix == "phase2":
        log_kwargs["section_name"] = source_name
    else:
        log_kwargs["source_name"] = source_name
    log_kwargs.update(extra)
    log_automation_event(logger, f"{prefix}_from_date_{event_suffix}", **log_kwargs)


async def apply_portal_date_range(
    page: Page,
    run_id: str,
    report_slug: str,
    source_name: str,
    *,
    filter_service: FilterService | None = None,
    expected_range: ReportDateRange | None = None,
) -> None:
    """Locate From/To Date by label, fill YYYY-MM-DD range, verify, gate Submit."""
    service = filter_service or FilterService()
    expected = expected_range or _resolve_expected_date_range()
    expected_from_date = expected.iso_from()
    expected_to_date = expected.iso_to()
    retry_count = 0
    from_selector: str | None = None
    to_selector: str | None = None
    actual_from_date = ""
    actual_to_date = ""

    _log_from_date_event(
        report_slug,
        "started",
        run_id=run_id,
        source_name=source_name,
        expected_from_date=expected_from_date,
        actual_from_date=actual_from_date,
        actual_to_date=actual_to_date,
        selector_used=from_selector,
        retry_count=retry_count,
        expected_to_date=expected_to_date,
    )

    report_root = await service.get_report_root(page)
    from_locator, from_selector = await _resolve_locator(report_root, FROM_DATE_SELECTORS)
    if from_locator is None:
        await _fail(
            page,
            report_slug=report_slug,
            run_id=run_id,
            source_name=source_name,
            error_code="PORTAL_FROM_DATE_FIELD_NOT_FOUND",
            message="From Date field not found by label/form group",
            expected_from_date=expected_from_date,
            expected_to_date=expected_to_date,
            actual_from_date=actual_from_date,
            actual_to_date=actual_to_date,
            selector_used=from_selector,
            retry_count=retry_count,
        )

    to_locator, to_selector = await _resolve_locator(report_root, TO_DATE_SELECTORS)
    if to_locator is None:
        await _fail(
            page,
            report_slug=report_slug,
            run_id=run_id,
            source_name=source_name,
            error_code="PORTAL_TO_DATE_FIELD_NOT_FOUND",
            message="To Date field not found by label/form group",
            expected_from_date=expected_from_date,
            expected_to_date=expected_to_date,
            actual_from_date=actual_from_date,
            actual_to_date=actual_to_date,
            selector_used=to_selector,
            retry_count=retry_count,
        )

    _log_from_date_event(
        report_slug,
        "field_found",
        run_id=run_id,
        source_name=source_name,
        expected_from_date=expected_from_date,
        actual_from_date=await _read_input_value(from_locator),
        actual_to_date=await _read_input_value(to_locator),
        selector_used=from_selector,
        retry_count=retry_count,
        expected_to_date=expected_to_date,
    )

    await _clear_and_fill(from_locator, expected_from_date)
    await _clear_and_fill(to_locator, expected_to_date)

    actual_from_date = await _read_input_value(from_locator)
    actual_to_date = await _read_input_value(to_locator)

    _log_from_date_event(
        report_slug,
        "set",
        run_id=run_id,
        source_name=source_name,
        expected_from_date=expected_from_date,
        actual_from_date=actual_from_date,
        actual_to_date=actual_to_date,
        selector_used=from_selector,
        retry_count=retry_count,
        expected_to_date=expected_to_date,
    )

    if actual_from_date != expected_from_date:
        retry_count += 1
        await _native_setter_fill(from_locator, expected_from_date)
        actual_from_date = await _read_input_value(from_locator)

    if actual_to_date != expected_to_date:
        retry_count += 1
        await _native_setter_fill(to_locator, expected_to_date)
        actual_to_date = await _read_input_value(to_locator)

    if actual_from_date != expected_from_date or actual_to_date != expected_to_date:
        await _fail(
            page,
            report_slug=report_slug,
            run_id=run_id,
            source_name=source_name,
            error_code="PORTAL_DATE_RANGE_MISMATCH",
            message=(
                f"Portal date range mismatch: expected {expected_from_date}–{expected_to_date}, "
                f"got {actual_from_date!r}–{actual_to_date!r}"
            ),
            expected_from_date=expected_from_date,
            expected_to_date=expected_to_date,
            actual_from_date=actual_from_date,
            actual_to_date=actual_to_date,
            selector_used=from_selector,
            retry_count=retry_count,
        )

    _log_from_date_event(
        report_slug,
        "verified",
        run_id=run_id,
        source_name=source_name,
        expected_from_date=expected_from_date,
        actual_from_date=actual_from_date,
        actual_to_date=actual_to_date,
        selector_used=from_selector,
        retry_count=retry_count,
        expected_to_date=expected_to_date,
    )


async def apply_previous_from_date(
    page: Page,
    run_id: str,
    report_slug: str,
    source_name: str,
    *,
    filter_service: FilterService | None = None,
) -> None:
    """Apply and verify the run snapshot date range before RailMadad Submit."""
    await apply_portal_date_range(
        page,
        run_id,
        report_slug,
        source_name,
        filter_service=filter_service,
    )


async def _fail(
    page: Page,
    *,
    run_id: str,
    report_slug: str,
    source_name: str,
    error_code: str,
    message: str,
    expected_from_date: str,
    expected_to_date: str,
    actual_from_date: str,
    actual_to_date: str,
    selector_used: str | None,
    retry_count: int,
) -> None:
    _log_from_date_event(
        report_slug,
        "failed",
        run_id=run_id,
        source_name=source_name,
        expected_from_date=expected_from_date,
        actual_from_date=actual_from_date,
        actual_to_date=actual_to_date,
        selector_used=selector_used,
        retry_count=retry_count,
        error_code=error_code,
        error=message,
        expected_to_date=expected_to_date,
    )
    await save_portal_from_date_failure_artifacts(
        page,
        report_slug,
        run_id=run_id,
        source_name=source_name,
        error_code=error_code,
        expected_from_date=expected_from_date,
        actual_from_date=actual_from_date,
        actual_to_date=actual_to_date,
        selector_used=selector_used,
        retry_count=retry_count,
    )
    raise PortalFromDateError(error_code, message)


def log_phase1_submit_clicked(
    run_id: str,
    report_slug: str,
    source_name: str,
    *,
    expected_from_date: str | None = None,
    actual_from_date: str | None = None,
    actual_to_date: str | None = None,
    selector_used: str | None = None,
    retry_count: int = 0,
) -> None:
    """Log immediately before Submit is clicked (Phase 1 reports)."""
    log_automation_event(
        logger,
        "phase1_submit_clicked",
        run_id=run_id,
        report_slug=report_slug,
        source_name=source_name,
        expected_from_date=expected_from_date or get_phase1_from_date(),
        actual_from_date=actual_from_date or "",
        actual_to_date=actual_to_date or "",
        selector_used=selector_used,
        retry_count=retry_count,
    )


def log_phase2_submit_clicked(
    run_id: str,
    report_slug: str,
    section_name: str,
    *,
    expected_from_date: str | None = None,
    actual_from_date: str | None = None,
    actual_to_date: str | None = None,
    selector_used: str | None = None,
    retry_count: int = 0,
) -> None:
    """Log immediately before Submit is clicked (Phase 2 reports)."""
    log_automation_event(
        logger,
        "phase2_submit_clicked",
        run_id=run_id,
        report_slug=report_slug,
        section_name=section_name,
        expected_from_date=expected_from_date or _resolve_expected_from_date(report_slug),
        actual_from_date=actual_from_date or "",
        actual_to_date=actual_to_date or "",
        selector_used=selector_used,
        retry_count=retry_count,
    )


def log_phase3_submit_clicked(
    run_id: str,
    report_slug: str,
    source_name: str,
    *,
    expected_from_date: str | None = None,
    actual_from_date: str | None = None,
    actual_to_date: str | None = None,
    selector_used: str | None = None,
    retry_count: int = 0,
) -> None:
    """Log immediately before Submit is clicked (Phase 3 reports)."""
    log_automation_event(
        logger,
        "phase3_submit_clicked",
        run_id=run_id,
        report_slug=report_slug,
        source_name=source_name,
        expected_from_date=expected_from_date or _resolve_expected_from_date(report_slug),
        actual_from_date=actual_from_date or "",
        actual_to_date=actual_to_date or "",
        selector_used=selector_used,
        retry_count=retry_count,
    )
