"""Unit tests for Phase 2 portal From Date handling (Reports 3/4)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.automation.date_range import resolve_portal_from_date
from app.automation.handlers.base import BaseReportHandler
from app.automation.handlers.report4_handler import Report4Handler
from app.automation.portal_from_date import (
    FROM_DATE_SELECTORS,
    PortalFromDateError,
    apply_previous_from_date,
)
from app.automation.report3_filters import REPORT_3_FILTERS
from app.automation.report4_filters import get_report4_base_filters
from app.automation.reports import REPORT_3_TRAIN_NO, REPORT_4_TYPES
from app.automation.run_context import RunContext, reset_run_context, set_run_context
from app.automation.timing import RunTiming


def test_resolve_portal_from_date_asia_kolkata_boundary():
    moment = datetime(2026, 7, 25, 19, 0, tzinfo=ZoneInfo("UTC"))
    assert resolve_portal_from_date(moment=moment) == "2026-07-25"


def test_resolve_portal_from_date_format_yyyy_mm_dd():
    value = resolve_portal_from_date(
        moment=datetime(2026, 7, 26, 12, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    )
    assert len(value) == 10
    assert value[4] == "-" and value[7] == "-"
    assert value == "2026-07-25"


def test_freeze_report_from_date_once_per_report():
    ctx = RunContext(run_id="run-3", timing=RunTiming(run_id="run-3"))
    token = set_run_context(ctx)
    try:
        with patch(
            "app.automation.date_range.resolve_portal_from_date",
            return_value="2026-07-25",
        ):
            first = ctx.freeze_report_from_date("train-no")
            second = ctx.freeze_report_from_date("train-no")
        assert first == second == "2026-07-25"
        assert ctx.report_from_dates["train-no"] == "2026-07-25"
    finally:
        reset_run_context(token)


def test_report3_filters_exclude_date_range():
    assert not any(f.name == "dateRange" for f in REPORT_3_FILTERS)


def test_report4_base_filters_exclude_date_range():
    assert not any(f.name == "dateRange" for f in get_report4_base_filters())


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
async def test_phase2_from_date_uses_frozen_report_date():
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
        run_id="run-3",
        timing=RunTiming(run_id="run-3"),
        report_from_dates={"train-no": "2026-07-25"},
    )
    token = set_run_context(ctx)
    try:
        await apply_previous_from_date(
            page, "run-3", "train-no", "train_no_wise", filter_service=service
        )
    finally:
        reset_run_context(token)

    from_locator.focus.assert_awaited()
    from_locator.fill.assert_awaited()
    assert from_locator.evaluate.await_count >= 1


@pytest.mark.asyncio
async def test_phase2_native_setter_retry():
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
        run_id="run-3",
        timing=RunTiming(run_id="run-3"),
        report_from_dates={"train-no": "2026-07-25"},
    )
    token = set_run_context(ctx)
    try:
        await apply_previous_from_date(
            page, "run-3", "train-no", "train_no_wise", filter_service=service
        )
    finally:
        reset_run_context(token)

    assert from_locator.evaluate.await_count >= 2


@pytest.mark.asyncio
async def test_phase2_blocks_when_to_date_changes():
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
        run_id="run-4",
        timing=RunTiming(run_id="run-4"),
        report_from_dates={"types": "2026-07-25"},
        date_range=ReportDateRange.from_iso("2026-07-25", "2026-07-26"),
    )
    token = set_run_context(ctx)
    try:
        with pytest.raises(PortalFromDateError) as exc_info:
            await apply_previous_from_date(
                page, "run-4", "types", "Security", filter_service=service
            )
        assert exc_info.value.code == "PORTAL_DATE_RANGE_MISMATCH"
    finally:
        reset_run_context(token)


@pytest.mark.asyncio
async def test_report3_apply_filters_and_submit_calls_phase2_helper():
    class _Handler(BaseReportHandler):
        async def execute(self, page, session, report):
            raise NotImplementedError

    handler = _Handler()
    page = MagicMock()
    report_root = MagicMock()
    handler.filter_service.get_report_root = AsyncMock(return_value=report_root)
    handler.filter_service.apply_filters = AsyncMock(return_value={"view": "Train No Wise"})
    handler.filter_service.validate_mandatory = AsyncMock()
    handler.generator.generate_report = AsyncMock()
    handler.generator.count_rows = AsyncMock(return_value=5)
    handler.generator.verify_report_displayed = AsyncMock(return_value=True)
    handler.navigation.verify_report_page = AsyncMock(return_value=True)

    with patch(
        "app.automation.handlers.base.apply_previous_from_date",
        new_callable=AsyncMock,
    ) as mock_apply, patch(
        "app.automation.handlers.base.log_phase2_submit_clicked",
    ) as mock_log:
        ctx = RunContext(
            run_id="run-r3",
            timing=RunTiming(run_id="run-r3"),
            report_from_dates={"train-no": "2026-07-25"},
        )
        token = set_run_context(ctx)
        try:
            await handler.apply_filters_and_submit(
                page,
                REPORT_3_TRAIN_NO,
                filters=REPORT_3_FILTERS,
                source_name="train_no_wise",
            )
        finally:
            reset_run_context(token)

        mock_apply.assert_awaited_once()
        assert mock_apply.await_args.args[3] == "train_no_wise"
        mock_log.assert_called_once()
        handler.generator.generate_report.assert_awaited_once()


@pytest.mark.asyncio
async def test_report4_submit_type_once_calls_phase2_helper():
    handler = Report4Handler()
    page = MagicMock()
    report_root = MagicMock()
    handler.ensure_mis_page = AsyncMock(return_value=page)
    handler.filter_service.get_report_root = AsyncMock(return_value=report_root)
    handler.filter_service.apply_filters = AsyncMock(return_value={"type": "Security- Train"})
    handler.filter_service.validate_mandatory = AsyncMock()
    handler._assert_core_filters = MagicMock()
    handler._table_fingerprint = AsyncMock(return_value="OLD")
    handler._wait_for_table_refresh = AsyncMock(return_value=True)
    handler._verify_type_selected = AsyncMock(return_value=True)
    handler.generator.generate_report = AsyncMock()
    handler.generator.verify_report_displayed = AsyncMock(return_value=True)

    type_config = MagicMock()
    type_config.name = "Security"
    type_config.portal_value = "Security- Train"

    with patch(
        "app.automation.handlers.report4_handler.apply_previous_from_date",
        new_callable=AsyncMock,
    ) as mock_apply, patch(
        "app.automation.handlers.report4_handler.log_phase2_submit_clicked",
    ) as mock_log:
        ctx = RunContext(
            run_id="run-r4",
            timing=RunTiming(run_id="run-r4"),
            report_from_dates={"types": "2026-07-25"},
        )
        token = set_run_context(ctx)
        try:
            await handler._submit_type_once(
                page, MagicMock(), REPORT_4_TYPES, type_config, attempt=1
            )
        finally:
            reset_run_context(token)

        mock_apply.assert_awaited_once()
        assert mock_apply.await_args.args[3] == "Security"
        mock_log.assert_called_once()
        handler.generator.generate_report.assert_awaited_once()


@pytest.mark.asyncio
async def test_extract_with_retry_train_no_calls_phase2_helper():
    from app.automation.workflow import extract_with_retry

    page = MagicMock()
    extractor = MagicMock()
    extractor.extract_and_save = AsyncMock(
        side_effect=[
            MagicMock(success=False, validation_result=None),
            MagicMock(success=True, row_count=10),
        ]
    )
    report_root = MagicMock()
    navigation = MagicMock()
    navigation.navigate_to_report = AsyncMock()
    filter_service = MagicMock()
    filter_service.get_report_root = AsyncMock(return_value=report_root)
    filter_service.apply_filters = AsyncMock(return_value={"view": "Train No Wise"})
    filter_service.validate_mandatory = AsyncMock()
    discovery = MagicMock()
    discovery.discover_fields = AsyncMock(return_value=[])
    generator = MagicMock()
    generator.generate_report = AsyncMock()
    generator.verify_report_displayed = AsyncMock(return_value=True)
    session = MagicMock()
    session.verify_mis_session = AsyncMock(return_value=MagicMock())

    with patch(
        "app.automation.workflow.verify_mis_session_or_raise",
        new_callable=AsyncMock,
    ), patch(
        "app.automation.workflow.build_filters_from_discovery",
        return_value=[],
    ), patch(
        "app.automation.workflow.apply_previous_from_date",
        new_callable=AsyncMock,
    ) as mock_apply, patch(
        "app.automation.workflow.log_phase2_submit_clicked",
    ) as mock_log, patch(
        "app.automation.workflow.ReceivedColumnService"
    ) as mock_sort_cls:
        mock_sort_cls.return_value.sort_received_descending = AsyncMock()
        ctx = RunContext(
            run_id="run-r3",
            timing=RunTiming(run_id="run-r3"),
            report_from_dates={"train-no": "2026-07-25"},
        )
        token = set_run_context(ctx)
        try:
            await extract_with_retry(
                page,
                extractor,
                report_root,
                REPORT_3_TRAIN_NO,
                navigation,
                filter_service,
                discovery,
                generator,
                session,
                max_retries=1,
            )
        finally:
            reset_run_context(token)

        mock_apply.assert_awaited_once()
        assert mock_apply.await_args.args[3] == "train_no_wise_retry"
        mock_log.assert_called_once()
