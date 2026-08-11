"""Tests for the process-wide CDP automation lock."""

from __future__ import annotations

from app.automation.automation_lock import (
    automation_lock_status,
    release_automation_lock,
    reset_automation_lock_for_tests,
    try_acquire_automation_lock,
)


def setup_function() -> None:
    reset_automation_lock_for_tests()


def test_try_acquire_and_release():
    assert try_acquire_automation_lock("run-a", "report1") is True
    status = automation_lock_status()
    assert status.locked is True
    assert status.run_id == "run-a"
    assert status.report_slug == "report1"

    assert try_acquire_automation_lock("run-b", "division") is False

    release_automation_lock("run-a")
    assert automation_lock_status().locked is False
    assert try_acquire_automation_lock("run-b", "division") is True


def test_same_run_can_reacquire():
    assert try_acquire_automation_lock("run-a", "report1") is True
    assert try_acquire_automation_lock("run-a", "report1") is True
    release_automation_lock("run-a")
