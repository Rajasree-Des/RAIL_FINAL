"""Unit tests for Phase 3 portal From Date handling (Reports 5/6)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.automation.date_range import resolve_portal_from_date
from app.automation.handlers.base import BaseReportHandler
from app.automation.handlers.report6_handler import Report6Handler
from app.automation.portal_from_date import (
    FROM_DATE_SELECTORS,
    PortalFromDateError,
    apply_previous_from_date,
)
from app.automation.report5_filters import REPORT_5_FILTERS
from app.automation.report6_scr_filters import REPORT_6_SCR_FILTERS
from app.automation.reports import REPORT_5_SCR_TRAIN
from app.automation.run_context import RunContext, reset_run_context, set_run_context
from app.automation.timing import RunTiming


def test_freeze_report_from_date_scr_train():
    ctx = RunContext(run_id="run-5", timing=RunTiming(run_id="run-5"))
    token = set_run_context(ctx)
    try:
        with patch(
            "app.automation.date_range.resolve_portal_from_date",
            return_value="2026-07-25",
        ):
            first = ctx.freeze_report_from_date("scr-train")
            second = ctx.freeze_report_from_date("scr-train")
        assert first == second == "2026-07-25"
        assert ctx.report_from_dates["scr-train"] == "2026-07-25"
    finally:
        reset_run_context(token)


def test_report5_filters_exclude_date_range():
    assert not any(f.name == "dateRange" for f in REPORT_5_FILTERS)


def test_report6_scr_filters_exclude_date_range():
    assert not any(f.name == "dateRange" for f in REPORT_6_SCR_FILTERS)


def test_resolve_portal_from_date_phase3_format():
    value = resolve_portal_from_date(
        moment=datetime(2026, 7, 26, 12, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    )
    assert value == "2026-07-25"
    assert len(value) == 10 and value[4] == "-" and value[7] == "-"


def test_from_date_selectors_label_before_id_fallback():
    assert FROM_DATE_SELECTORS[0] == "div.fromDate input"
    assert FROM_DATE_SELECTORS[-1] == "#fromInput"
    assert "input[type=date]" not in FROM_DATE_SELECTORS


def _make_locator(*, input_values: list[str], count: int = 1):
    locator = MagicMock()
    locator.count = AsyncMock(return_value=count)
    values_iter = iter(input_values)

    async def _input_value():
        try:
            return next(values_iter)
        except StopIteration:
            return input_values[-1] if input_values else ""

    async def _evaluate(script, *args):
        if "el.value" in script and "trim" in script:
            try:
                return next(values_iter)
            except StopIteration:
                return input_values[-1] if input_values else ""
        return None

    locator.input_value = AsyncMock(side_effect=_input_value)
    locator.fill = AsyncMock()
    locator.click = AsyncMock()
    locator.focus = AsyncMock()
    locator.evaluate = AsyncMock(side_effect=_evaluate)
    return locator


@pytest.mark.asyncio
async def test_phase3_from_date_uses_frozen_report_date():
    page = MagicMock()
    root = MagicMock()
    from_locator = _make_locator(input_values=["", "2026-07-25", "2026-07-25", "2026-07-26"])
    to_locator = _make_locator(input_values=["2026-07-26", "2026-07-26"])

    def locator_side_effect(selector: str):
        child = MagicMock()
        if "fromDate" in selector or "From Date" in selector or selector == "#fromInput":
            child.first = from_locator
        else:
            child.first = to_locator
        return child

    root.locator = MagicMock(side_effect=locator_side_effect)
    service = MagicMock()
    service.get_report_root = AsyncMock(return_value=root)

    ctx = RunContext(
        run_id="run-5",
        timing=RunTiming(run_id="run-5"),
        report_from_dates={"scr-train": "2026-07-25"},
    )
    token = set_run_context(ctx)
    try:
        await apply_previous_from_date(
            page, "run-5", "scr-train", "scr_train_feedback", filter_service=service
        )
    finally:
        reset_run_context(token)

    from_locator.focus.assert_awaited()
    from_locator.fill.assert_awaited()
    assert from_locator.evaluate.await_count >= 1


@pytest.mark.asyncio
async def test_phase3_native_setter_retry():
    page = MagicMock()
    root = MagicMock()
    from_locator = _make_locator(
        input_values=["", "wrong", "2026-07-25", "2026-07-25", "2026-07-26"]
    )
    to_locator = _make_locator(input_values=["2026-07-26", "2026-07-26"])

    def locator_side_effect(selector: str):
        child = MagicMock()
        if "toDate" in selector or "To Date" in selector or selector == "#toInput":
            child.first = to_locator
        else:
            child.first = from_locator
        return child

    root.locator = MagicMock(side_effect=locator_side_effect)
    service = MagicMock()
    service.get_report_root = AsyncMock(return_value=root)

    ctx = RunContext(
        run_id="run-5",
        timing=RunTiming(run_id="run-5"),
        report_from_dates={"scr-train": "2026-07-25"},
    )
    token = set_run_context(ctx)
    try:
        await apply_previous_from_date(
            page, "run-5", "scr-train", "scr_train_feedback", filter_service=service
        )
    finally:
        reset_run_context(token)

    assert from_locator.evaluate.await_count >= 2


@pytest.mark.asyncio
async def test_phase3_blocks_when_to_date_changes():
    page = MagicMock()
    root = MagicMock()
    from_locator = _make_locator(input_values=["", "2026-07-25", "2026-07-25"])
    to_locator = _make_locator(input_values=["", "2026-07-25", "2026-07-25"])

    def locator_side_effect(selector: str):
        child = MagicMock()
        if "toDate" in selector or "To Date" in selector or selector == "#toInput":
            child.first = to_locator
        else:
            child.first = from_locator
        return child

    root.locator = MagicMock(side_effect=locator_side_effect)
    service = MagicMock()
    service.get_report_root = AsyncMock(return_value=root)

    from app.automation.date_range import ReportDateRange

    ctx = RunContext(
        run_id="run-6",
        timing=RunTiming(run_id="run-6"),
        report_from_dates={"scr-station": "2026-07-25"},
        date_range=ReportDateRange.from_iso("2026-07-25", "2026-07-26"),
    )
    token = set_run_context(ctx)
    try:
        with pytest.raises(PortalFromDateError) as exc_info:
            await apply_previous_from_date(
                page, "run-6", "scr-station", "scr_station_feedback", filter_service=service
            )
        assert exc_info.value.code == "PORTAL_DATE_RANGE_MISMATCH"
    finally:
        reset_run_context(token)


@pytest.mark.asyncio
async def test_report5_apply_filters_and_submit_calls_phase3_helper():
    class _Handler(BaseReportHandler):
        async def execute(self, page, session, report):
            raise NotImplementedError

    handler = _Handler()
    page = MagicMock()
    report_root = MagicMock()
    handler.filter_service.get_report_root = AsyncMock(return_value=report_root)
    handler.filter_service.apply_filters = AsyncMock(return_value={"mode": "Train"})
    handler.filter_service.validate_mandatory = AsyncMock()
    handler.generator.generate_report = AsyncMock()
    handler.generator.count_rows = AsyncMock(return_value=5)
    handler.generator.verify_report_displayed = AsyncMock(return_value=True)
    handler.navigation.verify_report_page = AsyncMock(return_value=True)

    with patch(
        "app.automation.handlers.base.apply_previous_from_date",
        new_callable=AsyncMock,
    ) as mock_apply, patch(
        "app.automation.handlers.base.log_phase3_submit_clicked",
    ) as mock_log:
        ctx = RunContext(
            run_id="run-r5",
            timing=RunTiming(run_id="run-r5"),
            report_from_dates={"scr-train": "2026-07-25"},
        )
        token = set_run_context(ctx)
        try:
            await handler.apply_filters_and_submit(
                page,
                REPORT_5_SCR_TRAIN,
                filters=REPORT_5_FILTERS,
                source_name="scr_train_feedback",
            )
        finally:
            reset_run_context(token)

        mock_apply.assert_awaited_once()
        assert mock_apply.await_args.args[3] == "scr_train_feedback"
        mock_log.assert_called_once()
        handler.generator.generate_report.assert_awaited_once()


@pytest.mark.asyncio
async def test_report6_apply_station_filters_calls_phase3_helper():
    handler = Report6Handler()
    page = MagicMock()
    session = MagicMock()
    report_root = MagicMock()
    handler.ensure_mis_page = AsyncMock(return_value=page)
    handler.navigation.navigate_to_report = AsyncMock()
    handler.apply_filters_and_submit = AsyncMock(return_value=(report_root, {}, 5))

    with patch.object(handler, "apply_filters_and_submit", new_callable=AsyncMock) as mock_submit:
        mock_submit.return_value = (report_root, {}, 5)
        ctx = RunContext(
            run_id="run-r6",
            timing=RunTiming(run_id="run-r6"),
            report_from_dates={"scr-station": "2026-07-25"},
        )
        token = set_run_context(ctx)
        try:
            from app.automation.reports import REPORT_6_SCR_STATION

            await handler._apply_station_filters(page, session, REPORT_6_SCR_STATION)
        finally:
            reset_run_context(token)

        mock_submit.assert_awaited_once()
        assert mock_submit.await_args.kwargs["source_name"] == "scr_station_feedback"
