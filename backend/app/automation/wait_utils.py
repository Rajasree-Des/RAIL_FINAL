"""Condition-based waits with optional fixed-sleep accounting."""

from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Awaitable, Callable
from typing import Any

from app.automation.run_context import get_run_context


async def _resolve_check(check: Callable[[], Any]) -> bool:
    result = check()
    if inspect.isawaitable(result):
        result = await result
    return bool(result)


async def tracked_sleep(seconds: float, *, reason: str = "") -> None:
    """Sleep while recording fixed-delay time on the active run."""
    if seconds <= 0:
        return
    ctx = get_run_context()
    if ctx is not None:
        ctx.timing.record_fixed_sleep(seconds, reason=reason)
    await asyncio.sleep(seconds)


async def poll_until(
    check: Callable[[], Any],
    *,
    interval_seconds: float = 0.1,
    timeout_seconds: float = 30.0,
    reason: str = "",
) -> bool:
    """Poll `check` until it returns True or timeout elapses."""
    deadline = time.perf_counter() + timeout_seconds
    while time.perf_counter() < deadline:
        if await _resolve_check(check):
            return True
        await tracked_sleep(interval_seconds, reason=reason or "poll_until")
    return await _resolve_check(check)
