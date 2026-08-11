"""Tests for CDP connection error classification."""

from __future__ import annotations

from playwright.async_api import Error as PlaywrightError

from app.automation.cdp_session import (
    connection_error_code,
    is_recoverable_connection_error,
)


def test_is_recoverable_connection_error_detects_playwright_disconnect():
    exc = PlaywrightError("Locator.count: Connection closed while reading from the driver")
    assert is_recoverable_connection_error(exc) is True
    assert connection_error_code(exc) == "CDP_CONNECTION_LOST"


def test_connection_error_code_for_mis_session():
    assert connection_error_code(Exception("MIS session lost")) == "MIS_SESSION_LOST"
