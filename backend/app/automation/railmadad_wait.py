"""Adaptive two-phase waits for slow RailMadad portal data loading."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from playwright.async_api import Page

from app.automation.config import config
from app.automation.run_context import get_run_context
from app.automation.utils import log_automation_event

from app.automation.report_errors import ReportStageError

logger = logging.getLogger(__name__)

ReadyCheck = Callable[[], bool | Awaitable[bool]]
LoadingCheck = Callable[[], bool | Awaitable[bool]]
TerminalCheck = Callable[[], str | None | Awaitable[str | None]]


@dataclass
class RailMadadWaitResult:
    success: bool
    elapsed_seconds: float
    normal_elapsed: float
    extended_elapsed: float
    entered_extended: bool
    stage: str
    report_slug: str
    error_code: str | None = None


async def _resolve(awaitable: bool | Awaitable[bool]) -> bool:
    if asyncio.iscoroutine(awaitable) or asyncio.isfuture(awaitable):
        return bool(await awaitable)
    return bool(awaitable)


async def _resolve_optional(awaitable: str | None | Awaitable[str | None]) -> str | None:
    if asyncio.iscoroutine(awaitable) or asyncio.isfuture(awaitable):
        value = await awaitable
    else:
        value = awaitable
    return str(value).strip() if value else None


def _record_slow_load_event(
    *,
    report_slug: str,
    stage: str,
    normal_elapsed: float,
    extended_elapsed: float,
    total_elapsed: float,
    result: str,
    entered_extended: bool,
) -> None:
    event = {
        "report_slug": report_slug,
        "stage": stage,
        "normal_elapsed": round(normal_elapsed, 3),
        "extended_elapsed": round(extended_elapsed, 3),
        "total_elapsed": round(total_elapsed, 3),
        "result": result,
        "entered_extended": entered_extended,
    }
    ctx = get_run_context()
    if ctx is not None:
        ctx.timing.record_slow_load_event(event)
    log_automation_event(
        logger,
        "railmadad_wait_completed",
        run_id=ctx.run_id if ctx is not None else "",
        **event,
    )


async def wait_for_railmadad_result(
    *,
    stage: str,
    report_slug: str,
    ready_check: ReadyCheck,
    is_loading: LoadingCheck | None = None,
    is_terminal_error: TerminalCheck | None = None,
    normal_timeout: float | None = None,
    max_timeout: float | None = None,
    poll_interval: float | None = None,
) -> RailMadadWaitResult:
    """Poll until ready, extending up to max_timeout only while portal is still loading."""
    normal_limit = float(
        normal_timeout if normal_timeout is not None else config.railmadad_normal_load_timeout
    )
    max_limit = float(
        max_timeout if max_timeout is not None else config.railmadad_slow_load_timeout
    )
    if max_limit < normal_limit:
        max_limit = normal_limit
    interval = float(
        poll_interval
        if poll_interval is not None
        else config.railmadad_poll_interval_ms / 1000.0
    )

    started = time.perf_counter()
    entered_extended = False
    ctx = get_run_context()
    log_automation_event(
        logger,
        "railmadad_wait_started",
        run_id=ctx.run_id if ctx is not None else "",
        report_slug=report_slug,
        stage=stage,
        normal_timeout=normal_limit,
        max_timeout=max_limit,
    )

    while True:
        now = time.perf_counter()
        elapsed = now - started

        if is_terminal_error is not None:
            terminal = await _resolve_optional(is_terminal_error())
            if terminal:
                _record_slow_load_event(
                    report_slug=report_slug,
                    stage=stage,
                    normal_elapsed=min(elapsed, normal_limit),
                    extended_elapsed=max(0.0, elapsed - normal_limit),
                    total_elapsed=elapsed,
                    result=f"terminal:{terminal}",
                    entered_extended=entered_extended,
                )
                return RailMadadWaitResult(
                    success=False,
                    elapsed_seconds=round(elapsed, 3),
                    normal_elapsed=round(min(elapsed, normal_limit), 3),
                    extended_elapsed=round(max(0.0, elapsed - normal_limit), 3),
                    entered_extended=entered_extended,
                    stage=stage,
                    report_slug=report_slug,
                    error_code=terminal,
                )

        if await _resolve(ready_check()):
            _record_slow_load_event(
                report_slug=report_slug,
                stage=stage,
                normal_elapsed=min(elapsed, normal_limit),
                extended_elapsed=max(0.0, elapsed - normal_limit),
                total_elapsed=elapsed,
                result="success",
                entered_extended=entered_extended,
            )
            return RailMadadWaitResult(
                success=True,
                elapsed_seconds=round(elapsed, 3),
                normal_elapsed=round(min(elapsed, normal_limit), 3),
                extended_elapsed=round(max(0.0, elapsed - normal_limit), 3),
                entered_extended=entered_extended,
                stage=stage,
                report_slug=report_slug,
            )

        if elapsed >= max_limit:
            code = f"{report_slug}.railmadad_slow_load_timeout"
            _record_slow_load_event(
                report_slug=report_slug,
                stage=stage,
                normal_elapsed=min(elapsed, normal_limit),
                extended_elapsed=max(0.0, elapsed - normal_limit),
                total_elapsed=elapsed,
                result="timeout",
                entered_extended=entered_extended,
            )
            return RailMadadWaitResult(
                success=False,
                elapsed_seconds=round(elapsed, 3),
                normal_elapsed=round(min(elapsed, normal_limit), 3),
                extended_elapsed=round(max(0.0, elapsed - normal_limit), 3),
                entered_extended=entered_extended,
                stage=stage,
                report_slug=report_slug,
                error_code=code,
            )

        if elapsed >= normal_limit and not entered_extended:
            still_loading = True
            if is_loading is not None:
                still_loading = await _resolve(is_loading())
            if still_loading:
                entered_extended = True
                log_automation_event(
                    logger,
                    "railmadad_slow_load_detected",
                    run_id=ctx.run_id if ctx is not None else "",
                    report_slug=report_slug,
                    stage=stage,
                    elapsed_seconds=round(elapsed, 3),
                    max_timeout=max_limit,
                )
            else:
                code = f"{report_slug}.{stage}_timeout"
                _record_slow_load_event(
                    report_slug=report_slug,
                    stage=stage,
                    normal_elapsed=elapsed,
                    extended_elapsed=0.0,
                    total_elapsed=elapsed,
                    result="normal_timeout",
                    entered_extended=False,
                )
                return RailMadadWaitResult(
                    success=False,
                    elapsed_seconds=round(elapsed, 3),
                    normal_elapsed=round(elapsed, 3),
                    extended_elapsed=0.0,
                    entered_extended=False,
                    stage=stage,
                    report_slug=report_slug,
                    error_code=code,
                )

        await asyncio.sleep(interval)


async def detect_terminal_portal_error(page: Page) -> str | None:
    """Fail fast on session loss or explicit portal errors (not slow loading)."""
    try:
        url = (page.url or "").lower()
        title = (await page.title() or "").lower()
    except Exception:
        return None

    login_markers = ("login", "signin", "sign-in", "sessionexpired", "j_security_check")
    if any(marker in url for marker in login_markers):
        return "railmadad_session_expired"
    if "login" in title and "railmadad" in title:
        return "railmadad_session_expired"

    error_patterns = (
        "internal server error",
        "session expired",
        "session has expired",
        "service unavailable",
        "error 500",
        "error 503",
    )
    for pattern in error_patterns:
        try:
            locator = page.locator(f"text=/{pattern}/i")
            if await locator.count() > 0 and await locator.first.is_visible():
                if "session" in pattern:
                    return "railmadad_session_expired"
                return "railmadad_portal_error"
        except Exception:
            continue
    return None


async def read_select_text(report_root: Any, selector: str) -> str:
    try:
        return str(
            await report_root.locator(selector).evaluate(
                "el => el.options?.[el.selectedIndex]?.text ?? el.value ?? ''"
            )
        ).strip()
    except Exception:
        return ""


async def verify_report_filters(
    report_root: Any,
    expected: dict[str, str],
    *,
    report_slug: str,
) -> str | None:
    """Return error message when applied portal filters do not match expectations."""
    selector_map = {
        "type": "#complaintTypeInput",
        "view": "#viewType",
        "zone": "#complaintZoneInput",
        "division": "#complaintDivInput",
        "department": "#complaintDeptInput",
    }
    for key, expected_value in expected.items():
        if not expected_value:
            continue
        selector = selector_map.get(key)
        if not selector:
            continue
        actual = (await read_select_text(report_root, selector)).lower()
        exp = str(expected_value).lower()
        if not actual:
            return f"{report_slug}.filter_mismatch: {key} not applied"
        if exp in actual or actual in exp:
            continue
        tokens = [t for t in exp.replace("-", " ").split() if len(t) > 3]
        if tokens and any(t in actual for t in tokens):
            continue
        return f"{report_slug}.filter_mismatch: {key} expected {expected_value!r} got {actual!r}"
    return None
