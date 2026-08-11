"""Performance-focused automation tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.automation.filters import FilterService
from app.automation.run_context import RunContext, reset_run_context, set_run_context
from app.automation.timing import RunTiming
from app.automation.wait_utils import poll_until


@pytest.mark.asyncio
async def test_apply_select_skips_unchanged_value():
    service = FilterService()
    locator = AsyncMock()
    locator.evaluate = AsyncMock(return_value="Zone Wise")
    applied, changed = await service._apply_select(locator, "Zone Wise")
    assert applied == "Zone Wise"
    assert changed is False
    locator.select_option.assert_not_called()


@pytest.mark.asyncio
async def test_poll_until_uses_short_interval_not_fixed_one_second():
    ticks: list[int] = []

    async def check() -> bool:
        ticks.append(1)
        return len(ticks) >= 2

    ok = await poll_until(check, interval_seconds=0.01, timeout_seconds=0.5)
    assert ok is True
    assert len(ticks) == 2


@pytest.mark.asyncio
async def test_timing_writes_labeled_performance_json(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.automation.timing.config.extracted_data_dir",
        str(tmp_path / "extracted"),
    )
    timing = RunTiming(run_id="label-run")
    timing.spans["handler_execute:report1"] = 5.0
    perf = timing.build_performance_report()
    path = timing.write_labeled_performance_json(perf, "after")
    assert path.name == "performance_after_label-run.json"
    assert path.exists()


@pytest.mark.asyncio
async def test_deferred_processing_schedules_without_blocking_browser():
    timing = RunTiming(run_id="defer-test")
    ctx = RunContext(run_id="defer-test", timing=timing, defer_processing=True)
    token = set_run_context(ctx)
    try:
        ran = {"ok": False}

        async def work():
            from app.automation.schemas import ReportResult

            ran["ok"] = True
            return ReportResult(slug="report1", status="success")

        result = await ctx.schedule_processing("report1", work)
        assert result is None
        await ctx.wait_all()
        assert ran["ok"] is True
        merged = ctx.get_results()
        assert merged and merged[0].status == "success"
    finally:
        reset_run_context(token)
