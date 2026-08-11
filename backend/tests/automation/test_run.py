"""Unit tests for automation run entrypoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.automation.browser import BrowserConnectionError
from app.automation.run import attach_to_railmadad, run
from app.automation.schemas import MultiReportResult, ReportResult
from app.automation.session import MisSessionError, MisSessionStatus, TabInfo


def _railmadad_tab() -> TabInfo:
    page = MagicMock()
    page.bring_to_front = AsyncMock()
    page.url = (
        "https://railmadad.indianrailways.gov.in/rmmis/admin/home.jsp"
        "?page=/mis_reports/report1&archiveFlag=N"
    )
    page.title = AsyncMock(return_value="RailMadad")
    page.is_closed = MagicMock(return_value=False)
    return TabInfo(
        context_index=0,
        tab_index=0,
        url=page.url,
        title="RailMadad",
        is_railmadad=True,
        page=page,
    )


@pytest.mark.asyncio
async def test_attach_returns_multi_report_result_on_success():
    mock_manager = MagicMock()
    mock_manager.connect = AsyncMock(return_value=MagicMock(contexts=[MagicMock()]))
    mock_manager.close = AsyncMock()
    mock_manager.browser = MagicMock()

    railmadad = _railmadad_tab()
    mock_session = MagicMock()
    mock_session.discover_tabs = AsyncMock(return_value=[railmadad])
    mock_session.ensure_authenticated_mis_page = AsyncMock(return_value=railmadad.page)
    mock_session.is_login_page = AsyncMock(return_value=False)

    mock_handler = MagicMock()
    mock_handler.bind_browser = MagicMock()

    async def _execute(_page, _session, report):
        from app.automation.report_keys import canonicalize_report_key

        key = canonicalize_report_key(report.slug)
        return ReportResult(slug=key, dataset_key=key, status="success")

    mock_handler.execute = AsyncMock(side_effect=_execute)

    with (
        patch("app.automation.run.BrowserManager", return_value=mock_manager),
        patch("app.automation.run.SessionManager", return_value=mock_session),
        patch("app.automation.run.get_handler", return_value=mock_handler),
        patch("app.automation.run.SessionLocal") as mock_db,
        patch("app.automation.run._register_missing_artifacts", AsyncMock()),
    ):
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_db.return_value = mock_cm
        with patch(
            "app.automation.run.create_cdp_run",
            AsyncMock(return_value=MagicMock(id="test-run-id")),
        ), patch(
            "app.automation.run.finalize_cdp_run",
            AsyncMock(),
        ):
            result = await attach_to_railmadad()

    assert isinstance(result, MultiReportResult)
    assert result.success is True
    assert result.connected is True
    assert result.tab_found is True
    assert len(result.reports) == 6
    assert result.run_id == "test-run-id"
    mock_manager.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_attach_returns_failure_when_mis_missing():
    mock_manager = MagicMock()
    mock_manager.connect = AsyncMock(return_value=MagicMock(contexts=[MagicMock()]))
    mock_manager.close = AsyncMock()
    mock_manager.browser = MagicMock()

    mock_session = MagicMock()
    mock_session.discover_tabs = AsyncMock(return_value=[])
    mock_session.ensure_authenticated_mis_page = AsyncMock(
        side_effect=MisSessionError(
            MisSessionStatus(
                valid=False,
                error_code="MIS_SESSION_LOST",
                error="No authenticated MIS admin page found in browser",
            )
        )
    )
    mock_session.first_available_page = MagicMock(return_value=None)

    with (
        patch("app.automation.run.BrowserManager", return_value=mock_manager),
        patch("app.automation.run.SessionManager", return_value=mock_session),
    ):
        result = await attach_to_railmadad()

    assert result.success is False
    assert result.session_valid is False
    mock_manager.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_attach_returns_failure_on_connect_error():
    mock_manager = MagicMock()
    mock_manager.connect = AsyncMock(
        side_effect=BrowserConnectionError("Connection refused"),
    )
    mock_manager.close = AsyncMock()
    mock_manager.browser = None

    with patch("app.automation.run.BrowserManager", return_value=mock_manager):
        result = await attach_to_railmadad()

    assert result.success is False
    assert result.connected is False
    assert result.tab_found is False
    assert result.error == "Connection refused"
    mock_manager.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_returns_true_when_attach_succeeds():
    with patch(
        "app.automation.run.attach_to_railmadad",
        AsyncMock(
            return_value=MultiReportResult(
                success=True,
                connected=True,
                tab_found=True,
            )
        ),
    ):
        assert await run() is True


@pytest.mark.asyncio
async def test_run_returns_false_when_attach_fails():
    with patch(
        "app.automation.run.attach_to_railmadad",
        AsyncMock(
            return_value=MultiReportResult(
                success=False,
                connected=False,
                tab_found=False,
                error="Connection refused",
            )
        ),
    ):
        assert await run() is False
