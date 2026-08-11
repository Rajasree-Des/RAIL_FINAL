"""Unit tests for session management and MIS guards (Phase 9)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.automation.session import (
    MIS_URL_PATTERNS,
    MisSessionStatus,
    SessionManager,
)


@pytest.mark.asyncio
async def test_verify_mis_session_valid_mis_url():
    session = SessionManager()
    page = MagicMock()
    page.url = "https://railmadad.indianrail.gov.in/rmmis/admin/home.jsp?page=/mis_reports/report1"

    session.is_login_page = AsyncMock(return_value=False)

    result = await session.verify_mis_session(page)

    assert result.valid is True
    assert result.error_code is None


@pytest.mark.asyncio
async def test_verify_mis_session_public_portal_rejected():
    session = SessionManager()
    page = MagicMock()
    page.url = "https://railmadad.indianrail.gov.in/madad/final/home.jsp"

    session.is_login_page = AsyncMock(return_value=False)
    session._verify_mis_menu = AsyncMock(return_value=False)

    result = await session.verify_mis_session(page)

    assert result.valid is False
    assert result.error_code == "MIS_SESSION_LOST"


@pytest.mark.asyncio
async def test_verify_mis_session_login_page_rejected():
    session = SessionManager()
    page = MagicMock()
    page.url = "https://railmadad.indianrail.gov.in/rmmis/admin/home.jsp"

    session.is_login_page = AsyncMock(return_value=True)

    result = await session.verify_mis_session(page)

    assert result.valid is False
    assert result.error_code == "RAILMADAD_NOT_LOGGED_IN"


@pytest.mark.asyncio
async def test_verify_mis_session_fallback_to_menu_check():
    session = SessionManager()
    page = MagicMock()
    page.url = "https://railmadad.indianrail.gov.in/some/other/page"

    session.is_login_page = AsyncMock(return_value=False)
    session._verify_mis_menu = AsyncMock(return_value=True)

    result = await session.verify_mis_session(page)

    assert result.valid is True


@pytest.mark.asyncio
async def test_verify_mis_session_no_menu_no_mis_url_rejected():
    session = SessionManager()
    page = MagicMock()
    page.url = "https://railmadad.indianrail.gov.in/some/other/page"

    session.is_login_page = AsyncMock(return_value=False)
    session._verify_mis_menu = AsyncMock(return_value=False)

    result = await session.verify_mis_session(page)

    assert result.valid is False
    assert result.error_code == "MIS_SESSION_LOST"


@pytest.mark.asyncio
async def test_verify_mis_menu_finds_menu():
    session = SessionManager()
    page = MagicMock()

    locator = MagicMock()
    locator.count = AsyncMock(return_value=1)
    locator.first.is_visible = AsyncMock(return_value=True)
    page.locator.return_value = locator

    result = await session._verify_mis_menu(page)

    assert result is True


@pytest.mark.asyncio
async def test_verify_mis_menu_no_menu():
    session = SessionManager()
    page = MagicMock()

    locator = MagicMock()
    locator.count = AsyncMock(return_value=0)
    page.locator.return_value = locator

    result = await session._verify_mis_menu(page)

    assert result is False


def test_mis_session_status_dataclass():
    status = MisSessionStatus(valid=False, error_code="MIS_SESSION_LOST", error="Test error")
    assert status.valid is False
    assert status.error_code == "MIS_SESSION_LOST"
    assert status.error == "Test error"


def test_mis_url_patterns_cover_expected():
    assert "/rmmis/admin" in MIS_URL_PATTERNS
    assert "mis_reports/" in MIS_URL_PATTERNS
