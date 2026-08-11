"""Cooperative cancel/pause flags for in-process CDP automation runs."""

from __future__ import annotations

import asyncio
import threading

_lock = threading.Lock()
_cancelled: set[str] = set()
_pause_events: dict[str, threading.Event] = {}
_pause_requested: set[str] = set()


class RunCancelledError(Exception):
    """Raised at a cooperative checkpoint when the user cancelled the run."""

    def __init__(self, run_id: str = "") -> None:
        self.run_id = run_id
        super().__init__("Report generation stopped by user")


def _pause_event(run_id: str) -> threading.Event:
    with _lock:
        ev = _pause_events.get(run_id)
        if ev is None:
            ev = threading.Event()
            ev.set()  # cleared = paused waiting; set = running
            _pause_events[run_id] = ev
        return ev


def request_cancel(run_id: str) -> None:
    """Mark a run so the worker stops at the next checkpoint."""
    if not run_id:
        return
    with _lock:
        _cancelled.add(run_id)
        _pause_requested.discard(run_id)
    # Unblock any pause wait so cancel can proceed
    _pause_event(run_id).set()


def is_cancelled(run_id: str) -> bool:
    with _lock:
        return run_id in _cancelled


def clear_cancel(run_id: str) -> None:
    with _lock:
        _cancelled.discard(run_id)
        _pause_requested.discard(run_id)
        ev = _pause_events.pop(run_id, None)
    if ev is not None:
        ev.set()


def request_pause(run_id: str) -> None:
    if not run_id:
        return
    with _lock:
        if run_id in _cancelled:
            return
        _pause_requested.add(run_id)
    _pause_event(run_id).clear()


def clear_pause(run_id: str) -> None:
    if not run_id:
        return
    with _lock:
        _pause_requested.discard(run_id)
    _pause_event(run_id).set()


def is_pause_requested(run_id: str) -> bool:
    with _lock:
        return run_id in _pause_requested


def wait_if_paused(run_id: str, *, poll_seconds: float = 0.25) -> None:
    """Block the worker thread while paused (returns immediately if cancelled)."""
    if not run_id or is_cancelled(run_id):
        return
    ev = _pause_event(run_id)
    while not ev.is_set():
        if is_cancelled(run_id):
            return
        ev.wait(timeout=poll_seconds)


async def wait_if_paused_async(run_id: str, *, poll_seconds: float = 0.25) -> None:
    """Async-friendly pause wait for asyncio worker loops."""
    if not run_id or is_cancelled(run_id):
        return
    ev = _pause_event(run_id)
    while not ev.is_set():
        if is_cancelled(run_id):
            return
        await asyncio.sleep(poll_seconds)


async def checkpoint(run_id: str, *, label: str = "") -> None:
    """Cooperative control point: raise on cancel; wait out pause."""
    del label  # reserved for logging callers
    if not run_id:
        return
    if is_cancelled(run_id):
        raise RunCancelledError(run_id)
    await wait_if_paused_async(run_id)
    if is_cancelled(run_id):
        raise RunCancelledError(run_id)
