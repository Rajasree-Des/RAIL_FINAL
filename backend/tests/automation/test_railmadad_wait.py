"""Unit tests for adaptive RailMadad wait helper."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.automation.railmadad_wait import (
    RailMadadWaitResult,
    wait_for_railmadad_result,
)


@pytest.mark.asyncio
async def test_ready_at_5s_succeeds_without_extended_phase():
    started = time.perf_counter()

    async def ready() -> bool:
        return time.perf_counter() - started >= 0.25

    result = await wait_for_railmadad_result(
        stage="result_table",
        report_slug="report6",
        ready_check=ready,
        normal_timeout=20.0,
        max_timeout=70.0,
        poll_interval=0.05,
    )
    assert result.success is True
    assert result.entered_extended is False
    assert 0.2 <= result.elapsed_seconds <= 1.0


@pytest.mark.asyncio
async def test_ready_at_25s_enters_extended_phase():
    started = time.perf_counter()

    async def ready() -> bool:
        return time.perf_counter() - started >= 0.55

    async def loading() -> bool:
        return time.perf_counter() - started < 0.45

    result = await wait_for_railmadad_result(
        stage="result_table",
        report_slug="comprehensive-10-13",
        ready_check=ready,
        is_loading=loading,
        normal_timeout=0.4,
        max_timeout=1.0,
        poll_interval=0.05,
    )
    assert result.success is True
    assert result.entered_extended is True
    assert result.extended_elapsed > 0


@pytest.mark.asyncio
async def test_ready_at_55s_within_cap():
    started = time.perf_counter()

    async def ready() -> bool:
        return time.perf_counter() - started >= 0.65

    async def loading() -> bool:
        return time.perf_counter() - started < 0.6

    result = await wait_for_railmadad_result(
        stage="result_table",
        report_slug="types",
        ready_check=ready,
        is_loading=loading,
        normal_timeout=0.4,
        max_timeout=1.0,
        poll_interval=0.05,
    )
    assert result.success is True
    assert result.elapsed_seconds <= 1.0


@pytest.mark.asyncio
async def test_ready_at_68s_within_cap():
    started = time.perf_counter()

    async def ready() -> bool:
        return time.perf_counter() - started >= 0.75

    async def loading() -> bool:
        return time.perf_counter() - started < 0.7

    result = await wait_for_railmadad_result(
        stage="result_table",
        report_slug="bottom-report",
        ready_check=ready,
        is_loading=loading,
        normal_timeout=0.4,
        max_timeout=1.0,
        poll_interval=0.05,
    )
    assert result.success is True


@pytest.mark.asyncio
async def test_never_ready_while_loading_times_out_at_max():
    async def ready() -> bool:
        return False

    async def loading() -> bool:
        return True

    result = await wait_for_railmadad_result(
        stage="result_table",
        report_slug="report18",
        ready_check=ready,
        is_loading=loading,
        normal_timeout=0.2,
        max_timeout=0.5,
        poll_interval=0.05,
    )
    assert result.success is False
    assert result.error_code == "report18.railmadad_slow_load_timeout"
    assert result.elapsed_seconds >= 0.45


@pytest.mark.asyncio
async def test_terminal_error_fails_fast():
    started = time.perf_counter()

    async def ready() -> bool:
        return False

    async def terminal() -> str | None:
        if time.perf_counter() - started >= 0.15:
            return "railmadad_session_expired"
        return None

    result = await wait_for_railmadad_result(
        stage="result_table",
        report_slug="report1",
        ready_check=ready,
        is_terminal_error=terminal,
        normal_timeout=20.0,
        max_timeout=70.0,
        poll_interval=0.05,
    )
    assert result.success is False
    assert result.error_code == "railmadad_session_expired"
    assert result.elapsed_seconds < 1.0


@pytest.mark.asyncio
async def test_normal_timeout_when_not_loading():
    async def ready() -> bool:
        return False

    async def loading() -> bool:
        return False

    result = await wait_for_railmadad_result(
        stage="result_table",
        report_slug="types",
        ready_check=ready,
        is_loading=loading,
        normal_timeout=0.2,
        max_timeout=0.7,
        poll_interval=0.05,
    )
    assert result.success is False
    assert result.error_code == "types.result_table_timeout"
    assert result.entered_extended is False


@pytest.mark.asyncio
async def test_records_slow_load_event_in_run_context():
    started = time.perf_counter()
    timing = MagicMock()

    async def ready() -> bool:
        return time.perf_counter() - started >= 0.15

    ctx = MagicMock()
    ctx.run_id = "test-run"
    ctx.timing = timing

    with patch("app.automation.railmadad_wait.get_run_context", return_value=ctx):
        result = await wait_for_railmadad_result(
            stage="result_table",
            report_slug="report6",
            ready_check=ready,
            normal_timeout=20.0,
            max_timeout=70.0,
            poll_interval=0.05,
        )

    assert isinstance(result, RailMadadWaitResult)
    assert result.success is True
    timing.record_slow_load_event.assert_called_once()


@pytest.mark.asyncio
async def test_report_failure_isolation_continues_next_report():
    """Orchestrator should append failed result and continue when one handler raises."""
    from app.automation.run import _execute_report_handler
    from app.automation.schemas import ReportResult

    handler = MagicMock()
    handler.bind_browser = MagicMock()
    from app.automation.report_errors import ReportGenerationError

    handler.execute = AsyncMock(
        side_effect=[
            ReportGenerationError("boom"),
            ReportResult(slug="report2", dataset_key="report2", status="success"),
        ]
    )

    report1 = MagicMock(slug="report1", url_fragment="report1")
    report2 = MagicMock(slug="report2", url_fragment="report2")

    ctx = MagicMock()
    ctx.checkpoint = AsyncMock()
    timing = MagicMock()
    timing.span.return_value.__enter__ = MagicMock(return_value=None)
    timing.span.return_value.__exit__ = MagicMock(return_value=False)

    manager = MagicMock()
    manager.browser = MagicMock()
    session = MagicMock()
    page = MagicMock()

    with patch("app.automation.run.get_handler", return_value=handler), patch(
        "app.automation.run.ensure_live_mis_page", new=AsyncMock(return_value=page)
    ):
        with pytest.raises(Exception):
            await _execute_report_handler(
                run_id="run-1",
                slug="report1",
                report=report1,
                manager=manager,
                session=session,
                page=page,
                ctx=ctx,
                timing=timing,
            )

        result, _page = await _execute_report_handler(
            run_id="run-1",
            slug="report2",
            report=report2,
            manager=manager,
            session=session,
            page=page,
            ctx=ctx,
            timing=timing,
        )

    assert result.status == "success"
    assert handler.execute.await_count == 2
