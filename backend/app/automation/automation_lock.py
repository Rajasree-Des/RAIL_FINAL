"""Process-wide lock: only one RailMadad CDP automation at a time."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_holder_run_id: str | None = None
_holder_report_slug: str | None = None


@dataclass(frozen=True)
class AutomationLockStatus:
    locked: bool
    run_id: str | None = None
    report_slug: str | None = None


def automation_lock_status() -> AutomationLockStatus:
    with _lock:
        if _holder_run_id is None:
            return AutomationLockStatus(locked=False)
        return AutomationLockStatus(
            locked=True,
            run_id=_holder_run_id,
            report_slug=_holder_report_slug,
        )


def try_acquire_automation_lock(run_id: str, report_slug: str) -> bool:
    """Acquire the CDP automation lock for ``run_id``. Returns False if held by another run."""
    with _lock:
        global _holder_run_id, _holder_report_slug
        if _holder_run_id is not None and _holder_run_id != run_id:
            logger.info(
                "automation_lock_busy active_run_id=%s active_slug=%s requested_run_id=%s requested_slug=%s",
                _holder_run_id,
                _holder_report_slug,
                run_id,
                report_slug,
            )
            return False
        _holder_run_id = run_id
        _holder_report_slug = report_slug
        logger.info(
            "automation_lock_acquired run_id=%s report_slug=%s",
            run_id,
            report_slug,
        )
        return True


def release_automation_lock(run_id: str) -> None:
    """Release the lock when ``run_id`` owns it. Safe to call multiple times."""
    with _lock:
        global _holder_run_id, _holder_report_slug
        if _holder_run_id != run_id:
            return
        logger.info(
            "automation_lock_released run_id=%s report_slug=%s",
            run_id,
            _holder_report_slug,
        )
        _holder_run_id = None
        _holder_report_slug = None


def reset_automation_lock_for_tests() -> None:
    """Test helper only."""
    with _lock:
        global _holder_run_id, _holder_report_slug
        _holder_run_id = None
        _holder_report_slug = None
