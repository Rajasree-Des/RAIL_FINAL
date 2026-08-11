"""Tests for cooperative CDP run cancellation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.automation.cancellation import clear_cancel, is_cancelled, request_cancel
from app.automation.run import attach_to_railmadad
from app.automation.schemas import MultiReportResult, ReportResult
from app.automation.session import TabInfo


def test_request_cancel_sets_flag():
    clear_cancel("run-a")
    assert is_cancelled("run-a") is False
    request_cancel("run-a")
    assert is_cancelled("run-a") is True
    clear_cancel("run-a")
    assert is_cancelled("run-a") is False


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
async def test_attach_skips_remaining_reports_when_cancelled():
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
    call_count = {"n": 0}

    async def _execute(_page, _session, report):
        from app.automation.report_keys import canonicalize_report_key

        call_count["n"] += 1
        if call_count["n"] == 1:
            request_cancel("cancel-run")
        key = canonicalize_report_key(report.slug)
        return ReportResult(slug=key, dataset_key=key, status="success")

    mock_handler.execute = AsyncMock(side_effect=_execute)

    with (
        patch("app.automation.run.BrowserManager", return_value=mock_manager),
        patch("app.automation.run.SessionManager", return_value=mock_session),
        patch("app.automation.run.get_handler", return_value=mock_handler),
        patch("app.automation.run.SessionLocal") as mock_db,
        patch("app.automation.run._register_missing_artifacts", AsyncMock()),
        patch(
            "app.automation.run.create_cdp_run",
            AsyncMock(return_value=MagicMock(id="cancel-run")),
        ),
        patch("app.automation.run.finalize_cdp_run", AsyncMock()) as mock_finalize,
    ):
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_db.return_value = mock_cm
        result = await attach_to_railmadad(run_id="cancel-run")

    assert isinstance(result, MultiReportResult)
    assert result.stopped_early is True
    assert result.stop_reason == "USER_CANCELLED"
    assert call_count["n"] == 1
    skipped = [r for r in result.reports if r.status == "skipped"]
    succeeded = [r for r in result.reports if r.status == "success"]
    assert len(succeeded) == 1
    assert len(skipped) == 5
    mock_finalize.assert_awaited()
    clear_cancel("cancel-run")
