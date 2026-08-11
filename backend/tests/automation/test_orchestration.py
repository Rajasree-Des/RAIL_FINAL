"""Tests for canonical report keys and multi-report orchestration."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.automation.handlers.registry import HANDLER_REGISTRY, get_handler
from app.automation.processing.registry import PROCESSORS
from app.automation.report_keys import (
    ALIASES,
    canonicalize_report_key,
    pdf_download_url,
)
from app.automation.reports import DEFAULT_CATALOG, catalog
from app.automation.run import attach_to_railmadad
from app.automation.schemas import ReportResult
from app.automation.session import MisSessionError, MisSessionStatus, TabInfo


def test_canonical_key_mapping():
    assert canonicalize_report_key("report2") == "division"
    assert canonicalize_report_key("report3") == "train-no"
    assert canonicalize_report_key("report4") == "types"
    assert canonicalize_report_key("report5") == "scr-train"
    assert canonicalize_report_key("report6_station") == "scr-station"
    assert canonicalize_report_key("division") == "division"


def test_catalog_uses_canonical_slugs():
    slugs = [r.slug for r in catalog.reports]
    assert slugs == [
        "report1",
        "division",
        "train-no",
        "types",
        "scr-train",
        "scr-station",
    ]
    assert DEFAULT_CATALOG[1].slug == "division"


def test_handlers_and_processors_registered_under_canonical_keys():
    for key in ["report1", "division", "train-no", "types", "scr-train", "scr-station"]:
        assert get_handler(key) is not None
        assert PROCESSORS.get(key) is not None
    # Aliases resolve to the same handler class
    assert get_handler("report2").__class__ is get_handler("division").__class__
    assert PROCESSORS.get("report3") is PROCESSORS.get("train-no")


def test_aliases_do_not_duplicate_canonical_registry_keys():
    for alias in ALIASES:
        assert alias not in HANDLER_REGISTRY or ALIASES[alias] == alias


def test_pdf_download_url():
    assert pdf_download_url("division") == "/api/v1/automation/reports/division/pdf"
    assert pdf_download_url("report2") == "/api/v1/automation/reports/division/pdf"


def _railmadad_tab(url: str | None = None) -> TabInfo:
    page = MagicMock()
    page.bring_to_front = AsyncMock()
    page.url = url or (
        "https://railmadad.indianrailways.gov.in/rmmis/admin/home.jsp"
        "?page=/mis_reports/report1"
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


def _success_result(slug: str) -> ReportResult:
    return ReportResult(
        slug=slug,
        dataset_key=slug,
        status="success",
        source_paths=[f"storage/extracted/{slug}/data.csv"],
        source_csv_path=f"storage/extracted/{slug}/data.csv",
        source_row_count=10,
        ingestion_success=True,
        excel_path=f"storage/output/excel/{slug}/out.xlsx",
        pdf_path=f"storage/output/pdf/{slug}/out.pdf",
        pdf_download_url=f"/api/v1/automation/reports/{slug}/pdf",
        processing_attempted=True,
        processing_success=True,
    )


def _mock_browser_manager() -> MagicMock:
    mock_manager = MagicMock()
    browser = MagicMock(contexts=[MagicMock()])
    mock_manager.connect = AsyncMock(return_value=browser)
    mock_manager.close = AsyncMock()
    mock_manager.browser = browser
    mock_manager.is_browser_connected = MagicMock(return_value=True)
    return mock_manager


def _mock_session_manager() -> tuple[MagicMock, TabInfo]:
    railmadad = _railmadad_tab()
    mock_session = MagicMock()
    mock_session.discover_tabs = AsyncMock(return_value=[railmadad])
    mock_session.ensure_authenticated_mis_page = AsyncMock(return_value=railmadad.page)
    mock_session.is_login_page = AsyncMock(return_value=False)
    mock_session.verify_mis_session = AsyncMock(return_value=MisSessionStatus(valid=True))
    mock_session.activate_tab = AsyncMock()
    return mock_session, railmadad


@pytest.mark.asyncio
async def test_execution_order_matches_canonical_catalog():
    execution_order: list[str] = []

    async def track_execute(page, session, report):
        execution_order.append(report.slug)
        return _success_result(report.slug)

    mock_manager = _mock_browser_manager()
    mock_session, _railmadad = _mock_session_manager()

    mock_handler = MagicMock()
    mock_handler.bind_browser = MagicMock()
    mock_handler.execute = AsyncMock(side_effect=track_execute)

    with (
        patch("app.automation.run.BrowserManager", return_value=mock_manager),
        patch("app.automation.run.SessionManager", return_value=mock_session),
        patch("app.automation.run.get_handler", return_value=mock_handler),
    ):
        result = await attach_to_railmadad()

    assert result.success is True
    assert execution_order == [r.slug for r in catalog.reports]


@pytest.mark.asyncio
async def test_report_failure_allows_next_report():
    async def flaky_execute(page, session, report):
        if report.slug == "division":
            return ReportResult(slug="division", dataset_key="division", status="failed", error="x")
        return _success_result(report.slug)

    mock_manager = _mock_browser_manager()
    mock_session, _railmadad = _mock_session_manager()

    mock_handler = MagicMock()
    mock_handler.bind_browser = MagicMock()
    mock_handler.execute = AsyncMock(side_effect=flaky_execute)

    with (
        patch("app.automation.run.BrowserManager", return_value=mock_manager),
        patch("app.automation.run.SessionManager", return_value=mock_session),
        patch("app.automation.run.get_handler", return_value=mock_handler),
    ):
        result = await attach_to_railmadad()

    assert result.stopped_early is False
    assert len(result.reports) == 6
    assert result.reports[1].status == "failed"
    assert result.reports[2].status == "success"


@pytest.mark.asyncio
async def test_auth_loss_stops_remaining_reports():
    async def auth_fail_on_third(page, session, report):
        if report.slug == "train-no":
            raise MisSessionError(
                MisSessionStatus(valid=False, error_code="MIS_SESSION_LOST", error="lost")
            )
        return _success_result(report.slug)

    mock_manager = _mock_browser_manager()
    mock_session, _railmadad = _mock_session_manager()

    mock_handler = MagicMock()
    mock_handler.bind_browser = MagicMock()
    mock_handler.execute = AsyncMock(side_effect=auth_fail_on_third)

    with (
        patch("app.automation.run.BrowserManager", return_value=mock_manager),
        patch("app.automation.run.SessionManager", return_value=mock_session),
        patch("app.automation.run.get_handler", return_value=mock_handler),
    ):
        result = await attach_to_railmadad()

    assert result.stopped_early is True
    assert result.stop_reason == "MIS_SESSION_LOST"
    assert len(result.reports) == 3


@pytest.mark.asyncio
async def test_public_tab_plus_mis_tab_reacquires_mis():
    from app.automation.session import SessionManager

    public = _railmadad_tab("https://railmadad.indianrailways.gov.in/madad/final/home.jsp")
    mis = _railmadad_tab(
        "https://railmadad.indianrailways.gov.in/rmmis/admin/home.jsp?page=/mis_reports/report1"
    )

    session = SessionManager(railmadad_url="https://railmadad.indianrailways.gov.in")
    browser = MagicMock()

    async def fake_discover(browser_arg):
        return [public, mis]

    with (
        patch.object(session, "discover_tabs", side_effect=fake_discover),
        patch.object(
            session,
            "verify_mis_session",
            AsyncMock(
                side_effect=[
                    MisSessionStatus(valid=False, error_code="MIS_SESSION_LOST", error="public"),
                    MisSessionStatus(valid=True),
                    MisSessionStatus(valid=True),
                ]
            ),
        ),
        patch.object(session, "is_login_page", AsyncMock(return_value=False)),
        patch.object(session, "activate_tab", AsyncMock()),
    ):
        page = await session.ensure_authenticated_mis_page(browser, public.page)

    assert page is mis.page


@pytest.mark.asyncio
async def test_report5_failure_allows_report6():
    async def fail_on_report5(page, session, report):
        if report.slug == "scr-train":
            return ReportResult(
                slug=report.slug,
                dataset_key=report.slug,
                status="failed",
                error="REPORT5_PDF_VALIDATION_FAILED: layout",
            )
        return _success_result(report.slug)

    mock_manager = _mock_browser_manager()
    mock_session, _railmadad = _mock_session_manager()

    mock_handler = MagicMock()
    mock_handler.bind_browser = MagicMock()
    mock_handler.execute = AsyncMock(side_effect=fail_on_report5)

    with (
        patch("app.automation.run.BrowserManager", return_value=mock_manager),
        patch("app.automation.run.SessionManager", return_value=mock_session),
        patch("app.automation.run.get_handler", return_value=mock_handler),
    ):
        result = await attach_to_railmadad()

    assert result.stopped_early is False
    assert len(result.reports) == 6
    r5 = next(r for r in result.reports if r.slug == "scr-train")
    r6 = next(r for r in result.reports if r.slug == "scr-station")
    assert r5.status == "failed"
    assert r6.status == "success"


def test_output_paths_separated_by_canonical_key():
    for slug in ["division", "train-no", "types", "scr-train", "scr-station"]:
        result = _success_result(slug)
        assert slug in (result.excel_path or "")
        assert slug in (result.pdf_path or "")
        assert result.pdf_download_url == f"/api/v1/automation/reports/{slug}/pdf"
