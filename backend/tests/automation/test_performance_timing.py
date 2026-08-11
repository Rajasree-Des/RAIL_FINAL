"""Performance instrumentation and condition-wait helpers."""

from __future__ import annotations

import pytest

from app.automation.run_context import RunContext, reset_run_context, set_run_context
from app.automation.timing import RunTiming
from app.automation.wait_utils import poll_until, tracked_sleep


@pytest.mark.asyncio
async def test_run_timing_writes_performance_json(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.automation.timing.config.extracted_data_dir",
        str(tmp_path / "extracted"),
    )
    timing = RunTiming(run_id="perf-test-run")
    timing.spans["nav_filter_submit:report1"] = 12.5
    timing.spans["processing:report1"] = 0.4
    timing.record_fixed_sleep(0.25, reason="cascading_filter_settle")
    perf = timing.build_performance_report()
    path = timing.write_performance_json(perf)
    assert path.name == "performance_perf-test-run.json"
    assert perf["run_id"] == "perf-test-run"
    assert perf["fixed_sleep_seconds"] == 0.25
    assert perf["top_bottlenecks"][0][0] == "nav_filter_submit:report1"


@pytest.mark.asyncio
async def test_tracked_sleep_records_on_run_context():
    timing = RunTiming(run_id="sleep-test")
    ctx = RunContext(run_id="sleep-test", timing=timing)
    token = set_run_context(ctx)
    try:
        await tracked_sleep(0.01, reason="unit_test")
    finally:
        reset_run_context(token)
    assert timing.fixed_sleep_seconds >= 0.01
    assert timing.fixed_sleep_events[-1]["reason"] == "unit_test"


@pytest.mark.asyncio
async def test_poll_until_returns_early_when_condition_met():
    counter = {"n": 0}

    async def check() -> bool:
        counter["n"] += 1
        return counter["n"] >= 2

    ok = await poll_until(check, interval_seconds=0.01, timeout_seconds=1.0)
    assert ok is True
    assert counter["n"] == 2
