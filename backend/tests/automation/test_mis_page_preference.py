"""Session MIS page preference must not return a wrong report tab."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.automation.session import MisSessionStatus, SessionManager


@pytest.mark.asyncio
async def test_ensure_authenticated_mis_page_rejects_wrong_report_fragment():
    session = SessionManager(railmadad_url="https://railmadad.indianrailways.gov.in")
    wrong = MagicMock()
    wrong.url = (
        "https://railmadad.indianrailways.gov.in/rmmis/admin/home.jsp"
        "?page=/mis_reports/report16&archiveFlag=N"
    )
    wrong.is_closed = MagicMock(return_value=False)

    preferred = MagicMock()
    preferred.url = (
        "https://railmadad.indianrailways.gov.in/rmmis/admin/home.jsp"
        "?page=/mis_reports/report1&archiveFlag=N"
    )
    preferred.is_closed = MagicMock(return_value=False)

    browser = MagicMock()

    with (
        patch.object(
            session,
            "verify_mis_session",
            AsyncMock(return_value=MisSessionStatus(valid=True)),
        ),
        patch.object(session, "activate_tab", AsyncMock()),
        patch.object(
            session,
            "find_authenticated_mis_page",
            AsyncMock(return_value=preferred),
        ) as find_mock,
    ):
        page = await session.ensure_authenticated_mis_page(
            browser,
            wrong,
            prefer_url_fragment="mis_reports/report1",
        )

    assert page is preferred
    find_mock.assert_awaited()


def test_url_matches_report_fragment_not_prefix_sibling():
    from app.automation.navigation import url_matches_report_fragment

    report16 = (
        "https://railmadad.indianrailways.gov.in/rmmis/admin/home.jsp"
        "?page=/mis_reports/report16&archiveFlag=N"
    )
    report1 = (
        "https://railmadad.indianrailways.gov.in/rmmis/admin/home.jsp"
        "?page=/mis_reports/report1&archiveFlag=N"
    )
    assert url_matches_report_fragment(report16, "mis_reports/report16") is True
    assert url_matches_report_fragment(report16, "mis_reports/report1") is False
    assert url_matches_report_fragment(report1, "mis_reports/report1") is True
    assert url_matches_report_fragment(report1, "mis_reports/report16") is False
