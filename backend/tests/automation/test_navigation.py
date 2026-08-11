"""Unit tests for NavigationService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.automation.navigation import NavigationError, NavigationService
from app.automation.reports import REPORT_1


def test_build_report_url_from_indianrailways_tab():
    service = NavigationService()
    current = (
        "https://railmadad.indianrailways.gov.in/rmmis/admin/home.jsp"
        "?page=/mis_reports/other&archiveFlag=N"
    )
    url = service.build_report_url(current, "/mis_reports/report1")
    assert url == (
        "https://railmadad.indianrailways.gov.in/rmmis/admin/home.jsp"
        "?page=/mis_reports/report1&archiveFlag=N&Id=null&mobile=null&email=null"
    )


def test_build_report_url_rejects_invalid_current_url():
    service = NavigationService()
    with pytest.raises(NavigationError, match="Cannot derive portal origin"):
        service.build_report_url("", "/mis_reports/report1")


@pytest.mark.asyncio
async def test_verify_report_page_by_url_fragment():
    service = NavigationService()
    page = MagicMock()
    page.url = (
        "https://railmadad.indianrailways.gov.in/rmmis/admin/home.jsp"
        "?page=/mis_reports/report1&archiveFlag=N"
    )
    assert await service.verify_report_page(page, REPORT_1) is True


@pytest.mark.asyncio
async def test_verify_report_page_rejects_public_portal_without_report_fragment():
    service = NavigationService()
    page = MagicMock()
    page.url = "https://railmadad.indianrailways.gov.in/madad/final/home.jsp"
    page.title = AsyncMock(return_value="RailMadad, A Grievance Redressal Mechanism")
    assert await service.verify_report_page(page, REPORT_1) is False


@pytest.mark.asyncio
async def test_navigate_from_public_portal_goes_to_report1():
    service = NavigationService()
    page = MagicMock()
    page.url = "https://railmadad.indianrailways.gov.in/madad/final/home.jsp"
    page.goto = AsyncMock()
    page.wait_for_load_state = AsyncMock()

    verify_results = [False, True]

    async def verify_side_effect(*_args, **_kwargs):
        return verify_results.pop(0)

    with patch.object(service, "verify_report_page", side_effect=verify_side_effect):
        await service.navigate_to_report(page, REPORT_1)

    page.goto.assert_awaited_once()
    assert "mis_reports/report1" in page.goto.await_args.args[0]


@pytest.mark.asyncio
async def test_navigate_skips_goto_when_already_on_report():
    service = NavigationService()
    page = MagicMock()
    page.url = (
        "https://railmadad.indianrailways.gov.in/rmmis/admin/home.jsp"
        "?page=/mis_reports/report1&archiveFlag=N"
    )
    page.goto = AsyncMock()

    with patch.object(service, "verify_report_page", AsyncMock(return_value=True)):
        await service.navigate_to_report(page, REPORT_1)

    page.goto.assert_not_called()


@pytest.mark.asyncio
async def test_navigate_goto_when_not_on_report():
    service = NavigationService()
    page = MagicMock()
    page.url = "https://railmadad.indianrailways.gov.in/rmmis/admin/home.jsp"
    page.goto = AsyncMock()
    page.wait_for_load_state = AsyncMock()

    verify_results = [False, True]

    async def verify_side_effect(*_args, **_kwargs):
        return verify_results.pop(0)

    with patch.object(service, "verify_report_page", side_effect=verify_side_effect):
        await service.navigate_to_report(page, REPORT_1)

    page.goto.assert_awaited_once()
    assert "mis_reports/report1" in page.goto.await_args.args[0]


@pytest.mark.asyncio
async def test_navigate_raises_when_verification_fails_after_goto():
    service = NavigationService()
    page = MagicMock()
    page.url = "https://railmadad.indianrailways.gov.in/rmmis/admin/home.jsp"
    page.goto = AsyncMock()
    page.wait_for_load_state = AsyncMock()

    with (
        patch.object(service, "verify_report_page", AsyncMock(return_value=False)),
        pytest.raises(NavigationError, match="verification failed"),
    ):
        await service.navigate_to_report(page, REPORT_1)


@pytest.mark.asyncio
async def test_capture_debug_screenshot(tmp_path):
    service = NavigationService()
    page = MagicMock()
    page.screenshot = AsyncMock()

    path = await service.capture_debug_screenshot(
        page,
        tmp_path,
        "report1.png",
    )

    assert path.endswith("report1.png")
    page.screenshot.assert_awaited_once()
