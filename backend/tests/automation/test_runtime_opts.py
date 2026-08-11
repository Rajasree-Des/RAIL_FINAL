"""Unit tests for Tab reuse and run-context process deferral."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.automation.handlers.report4_handler import Report4Handler
from app.automation.handlers.report6_handler import Report6Handler
from app.automation.reports import REPORT_4_TYPES, REPORT_6_SCR_STATION
from app.automation.run_context import (
    PROCESS_CONCURRENCY,
    RunContext,
    reset_run_context,
    set_run_context,
)
from app.automation.schemas import ReportResult
from app.automation.timing import RunTiming


@pytest.mark.asyncio
async def test_report4_navigates_once_then_full_filters_each_type(tmp_path):
    """Report 4 navigates once up front; each Type uses full-filter submit."""
    handler = Report4Handler()
    handler.navigation = MagicMock()
    handler.navigation.navigate_to_report = AsyncMock()
    handler.ensure_mis_page = AsyncMock(side_effect=lambda page, session, ctx="": page)
    handler._submit_type_once = AsyncMock(return_value=MagicMock())
    handler._wait_for_received_header = AsyncMock()
    handler._sort_received = AsyncMock()

    async def extract_side_effect(report_root, report, type_config, extracted_dir):
        path = Path(extracted_dir) / f"report4_{type_config.name.lower()}_raw.csv"
        path.write_text("a,b\n1,2\n", encoding="utf-8")
        return path, 1

    handler._extract_type = AsyncMock(side_effect=extract_side_effect)
    handler.finalize_after_extract = AsyncMock(
        return_value=ReportResult(
            slug="types",
            dataset_key="types",
            status="success",
            ingestion_success=True,
            processing_success=True,
        )
    )

    page = MagicMock()
    page.wait_for_selector = AsyncMock()
    session = MagicMock()

    from app.automation.report4_filters import TypeConfig

    configs = [
        TypeConfig("Security", "Security- Train", "t1"),
        TypeConfig("Bedroll", "Bed Roll- Train", "t2"),
    ]
    with (
        patch(
            "app.automation.handlers.report4_handler.get_type_configs",
            return_value=configs,
        ),
        patch(
            "app.automation.handlers.report4_handler.get_run_context",
            return_value=None,
        ),
        patch(
            "app.automation.handlers.report4_handler.resolve_report_dir",
            return_value=tmp_path / "types",
        ),
        patch("app.automation.handlers.report4_handler.config") as cfg,
    ):
        cfg.extracted_data_dir = str(tmp_path / "extracted")
        await handler.execute(page, session, REPORT_4_TYPES)

    assert handler.navigation.navigate_to_report.await_count == 1
    assert handler._submit_type_once.await_count == 2


@pytest.mark.asyncio
async def test_report4_retries_once_then_continues(tmp_path):
    """First attempt display failure should retry once, not abort the report."""
    from app.automation.generator import ReportGenerationError
    from app.automation.report4_filters import TypeConfig

    handler = Report4Handler()
    handler.navigation = MagicMock()
    handler.navigation.navigate_to_report = AsyncMock()
    handler.ensure_mis_page = AsyncMock(side_effect=lambda page, session, ctx="": page)
    handler._wait_for_received_header = AsyncMock()
    handler._sort_received = AsyncMock()
    handler._save_type_failure_artifacts = AsyncMock()
    handler.finalize_after_extract = AsyncMock(
        return_value=ReportResult(
            slug="types",
            dataset_key="types",
            status="success",
            ingestion_success=True,
            processing_success=True,
        )
    )

    async def extract_side_effect(report_root, report, type_config, extracted_dir):
        path = Path(extracted_dir) / f"report4_{type_config.name.lower()}_raw.csv"
        path.write_text("a,b\n1,2\n", encoding="utf-8")
        return path, 5

    handler._extract_type = AsyncMock(side_effect=extract_side_effect)

    async def submit_side_effect(page, session, report, type_config, *, attempt):
        if type_config.name == "Bedroll" and attempt == 1:
            raise ReportGenerationError("Report types did not display after generate")
        return MagicMock()

    handler._submit_type_once = AsyncMock(side_effect=submit_side_effect)

    page = MagicMock()
    page.wait_for_selector = AsyncMock()
    session = MagicMock()

    configs = [
        TypeConfig("Security", "Security- Train", "t1"),
        TypeConfig("Bedroll", "Bed Roll- Train", "t2"),
    ]
    with (
        patch(
            "app.automation.handlers.report4_handler.get_type_configs",
            return_value=configs,
        ),
        patch("app.automation.handlers.report4_handler.asyncio.sleep", new=AsyncMock()),
        patch(
            "app.automation.handlers.report4_handler.get_run_context",
            return_value=None,
        ),
        patch(
            "app.automation.handlers.report4_handler.resolve_report_dir",
            return_value=tmp_path / "types",
        ),
        patch("app.automation.handlers.report4_handler.config") as cfg,
    ):
        cfg.extracted_data_dir = str(tmp_path / "extracted")
        cfg.screenshots_dir = str(tmp_path / "shots")
        result = await handler.execute(page, session, REPORT_4_TYPES)

    assert result.status == "success"
    # Security(1) + Bedroll fail(1) + Bedroll retry(1) = 3
    assert handler._submit_type_once.await_count == 3


@pytest.mark.asyncio
async def test_report4_skips_failed_type_and_still_finalizes(tmp_path):
    """Exhausted retries for one type should skip it and still ingest remaining types."""
    from app.automation.generator import ReportGenerationError
    from app.automation.report4_filters import TypeConfig

    handler = Report4Handler()
    handler.navigation = MagicMock()
    handler.navigation.navigate_to_report = AsyncMock()
    handler.ensure_mis_page = AsyncMock(side_effect=lambda page, session, ctx="": page)
    handler._wait_for_received_header = AsyncMock()
    handler._sort_received = AsyncMock()
    handler._save_type_failure_artifacts = AsyncMock()
    handler.finalize_after_extract = AsyncMock(
        return_value=ReportResult(
            slug="types",
            dataset_key="types",
            status="success",
            ingestion_success=True,
            processing_success=True,
        )
    )

    async def extract_side_effect(report_root, report, type_config, extracted_dir):
        path = Path(extracted_dir) / f"report4_{type_config.name.lower()}_raw.csv"
        path.write_text("a,b\n1,2\n", encoding="utf-8")
        return path, 7

    handler._extract_type = AsyncMock(side_effect=extract_side_effect)

    async def submit_side_effect(page, session, report, type_config, *, attempt):
        if type_config.name == "Bedroll":
            raise ReportGenerationError("Report types did not display after generate")
        return MagicMock()

    handler._submit_type_once = AsyncMock(side_effect=submit_side_effect)

    page = MagicMock()
    page.wait_for_selector = AsyncMock()
    session = MagicMock()

    configs = [
        TypeConfig("Security", "Security- Train", "t1"),
        TypeConfig("Bedroll", "Bed Roll- Train", "t2"),
        TypeConfig("Water Availability", "Water Availability- Train", "t3"),
    ]
    with (
        patch(
            "app.automation.handlers.report4_handler.get_type_configs",
            return_value=configs,
        ),
        patch("app.automation.handlers.report4_handler.asyncio.sleep", new=AsyncMock()),
        patch(
            "app.automation.handlers.report4_handler.get_run_context",
            return_value=None,
        ),
        patch(
            "app.automation.handlers.report4_handler.resolve_report_dir",
            return_value=tmp_path / "types",
        ),
        patch("app.automation.handlers.report4_handler.config") as cfg,
    ):
        cfg.extracted_data_dir = str(tmp_path / "extracted")
        cfg.screenshots_dir = str(tmp_path / "shots")
        result = await handler.execute(page, session, REPORT_4_TYPES)

    assert result.status == "partial_success"
    # Security + Water Availability extracted; Bedroll skipped after retries
    assert handler._extract_type.await_count == 2
    handler.finalize_after_extract.assert_awaited_once()


@pytest.mark.asyncio
async def test_report6_reuses_tab6_mode_only():
    handler = Report6Handler()
    handler.navigation = MagicMock()
    handler.navigation.navigate_to_report = AsyncMock()
    handler.ensure_mis_page = AsyncMock(side_effect=lambda page, session, ctx="": page)
    handler.apply_filters_and_submit = AsyncMock(
        return_value=(MagicMock(), {}, 1)
    )
    handler.click_received_twice = AsyncMock()
    handler._extract_scr_complaints = AsyncMock(
        return_value=(1, [{"Ref. No.": "1", "Mode": "S"}], None)
    )
    handler._save_complaints_csv = MagicMock(return_value=MagicMock())
    handler.archive_pdf = AsyncMock(return_value=(True, None, None))
    handler.finalize_after_extract = AsyncMock(
        return_value=MagicMock(status="success", slug="scr-station")
    )

    page = MagicMock()
    page.url = "https://example/rmmis/admin/home.jsp?page=/mis_reports/report6"
    session = MagicMock()

    await handler.execute(page, session, REPORT_6_SCR_STATION)

    handler.navigation.navigate_to_report.assert_not_awaited()
    filters = handler.apply_filters_and_submit.await_args.kwargs.get("filters")
    if filters is None:
        filters = handler.apply_filters_and_submit.await_args.args[2]
    assert len(filters) == 1
    assert filters[0].name == "mode"
    assert filters[0].value == "Station"


@pytest.mark.asyncio
async def test_process_pool_max_two():
    timing = RunTiming(run_id="test-run")
    ctx = RunContext(run_id="test-run", timing=timing, defer_processing=True)
    token = set_run_context(ctx)
    active = 0
    max_active = 0
    lock = asyncio.Lock()

    async def work(i: int):
        nonlocal active, max_active

        async def _inner():
            nonlocal active, max_active
            async with lock:
                active += 1
                max_active = max(max_active, active)
            await asyncio.sleep(0.05)
            async with lock:
                active -= 1
            return ReportResult(slug=f"r{i}", status="success", dataset_key=f"r{i}")

        return await ctx.schedule_processing(f"r{i}", _inner)

    try:
        await asyncio.gather(*[work(i) for i in range(5)])
        await ctx.wait_all()
    finally:
        reset_run_context(token)

    assert max_active <= PROCESS_CONCURRENCY


def test_same_run_ingest_guard_tracks_paths():
    timing = RunTiming(run_id="ingest-guard")
    ctx = RunContext(run_id="ingest-guard", timing=timing)
    assert ctx.already_ingested("division", "/tmp/a.csv") is False
    ctx.mark_ingested("division", "/tmp/a.csv")
    assert ctx.already_ingested("division", "/tmp/a.csv") is True
    assert ctx.already_ingested("division", "/tmp/b.csv") is False
    # Feedback and comprehensive use different dataset keys — both allowed
    ctx.mark_ingested("report1_feedback", "/tmp/a.csv")
    assert ctx.already_ingested("report1_feedback", "/tmp/a.csv") is True
