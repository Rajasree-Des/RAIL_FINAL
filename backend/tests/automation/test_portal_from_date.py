"""Unit tests for Phase 1 portal From Date handling."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.automation.date_range import (
    ReportDateRange,
    resolve_phase1_from_date,
    resolve_phase1_to_date,
)
from app.automation.portal_from_date import (
    FROM_DATE_SELECTORS,
    PortalFromDateError,
    apply_previous_from_date,
    apply_portal_date_range,
    get_phase1_from_date,
)
from app.automation.run_context import RunContext, set_run_context, reset_run_context
from app.automation.timing import RunTiming


def _run_context(*, from_date: str = "2026-07-25", to_date: str = "2026-07-26") -> RunContext:
    date_range = ReportDateRange.from_iso(from_date, to_date)
    return RunContext(
        run_id="run-1",
        timing=RunTiming(run_id="run-1"),
        phase1_from_date=from_date,
        date_range=date_range,
    )


def test_resolve_phase1_from_date_asia_kolkata_boundary():
    # 2026-07-26 00:30 IST is still July 26 → yesterday is 2026-07-25
    moment = datetime(2026, 7, 25, 19, 0, tzinfo=ZoneInfo("UTC"))
    assert resolve_phase1_from_date(moment=moment) == "2026-07-25"


def test_resolve_phase1_from_date_format_yyyy_mm_dd():
    value = resolve_phase1_from_date(
        moment=datetime(2026, 7, 26, 12, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    )
    assert len(value) == 10
    assert value[4] == "-" and value[7] == "-"
    assert value == "2026-07-25"


def test_get_phase1_from_date_reads_run_context():
    ctx = _run_context(from_date="2026-07-20")
    token = set_run_context(ctx)
    try:
        assert get_phase1_from_date() == "2026-07-20"
    finally:
        reset_run_context(token)


def _make_locator(*, input_values: list[str], count: int = 1):
    """Mock locator whose input_value/evaluate returns sequential values."""
    locator = MagicMock()
    locator.count = AsyncMock(return_value=count)
    values_iter = iter(input_values)

    async def _input_value():
        return next(values_iter)

    async def _evaluate(script, *args):
        if "el.value" in script and "trim" in script:
            return next(values_iter)
        return None

    locator.input_value = AsyncMock(side_effect=_input_value)
    locator.fill = AsyncMock()
    locator.focus = AsyncMock()
    locator.click = AsyncMock()
    locator.evaluate = AsyncMock(side_effect=_evaluate)
    return locator


@pytest.mark.asyncio
async def test_from_date_located_by_label_form_group_selector():
    page = MagicMock()
    root = MagicMock()
    from_locator = _make_locator(input_values=["", "2026-07-25", "2026-07-25"])
    to_locator = _make_locator(input_values=["", "2026-07-26", "2026-07-26"])

    def locator_side_effect(selector: str):
        child = MagicMock()
        child.first = from_locator if "fromDate" in selector or "From Date" in selector else to_locator
        return child

    root.locator = MagicMock(side_effect=locator_side_effect)

    service = MagicMock()
    service.get_report_root = AsyncMock(return_value=root)

    ctx = _run_context()
    token = set_run_context(ctx)
    try:
        await apply_previous_from_date(
            page, "run-1", "report1", "comprehensive", filter_service=service
        )
    finally:
        reset_run_context(token)

    # First selector in chain must be tried
    assert root.locator.call_args_list[0].args[0] == FROM_DATE_SELECTORS[0]
    from_locator.fill.assert_awaited()
    from_locator.evaluate.assert_awaited()


@pytest.mark.asyncio
async def test_normal_fill_verifies_and_emits_events():
    page = MagicMock()
    root = MagicMock()
    from_locator = _make_locator(input_values=["", "2026-07-25", "2026-07-25"])
    to_locator = _make_locator(input_values=["", "2026-07-26", "2026-07-26"])

    def locator_side_effect(selector: str):
        child = MagicMock()
        if "To Date" in selector or "toDate" in selector:
            child.first = to_locator
        else:
            child.first = from_locator
        return child

    root.locator = MagicMock(side_effect=locator_side_effect)
    service = MagicMock()
    service.get_report_root = AsyncMock(return_value=root)

    ctx = _run_context()
    token = set_run_context(ctx)
    try:
        await apply_previous_from_date(
            page, "run-1", "report1", "comprehensive", filter_service=service
        )
    finally:
        reset_run_context(token)

    evaluate_calls = [str(c.args[0]) for c in from_locator.evaluate.await_args_list]
    assert any("dispatchEvent" in c and "blur" in c for c in evaluate_calls)


@pytest.mark.asyncio
async def test_native_setter_retry_on_first_mismatch():
    page = MagicMock()
    root = MagicMock()
    # existing read, after-fill mismatch, after native retry, final verify
    from_locator = _make_locator(
        input_values=["", "wrong", "2026-07-25", "2026-07-25"]
    )
    to_locator = _make_locator(input_values=["", "2026-07-26", "2026-07-26"])

    def locator_side_effect(selector: str):
        child = MagicMock()
        if "To Date" in selector or "toDate" in selector:
            child.first = to_locator
        else:
            child.first = from_locator
        return child

    root.locator = MagicMock(side_effect=locator_side_effect)
    service = MagicMock()
    service.get_report_root = AsyncMock(return_value=root)

    ctx = _run_context()
    token = set_run_context(ctx)
    try:
        await apply_previous_from_date(
            page, "run-1", "report1", "comprehensive", filter_service=service
        )
    finally:
        reset_run_context(token)

    evaluate_calls = [str(c.args[0]) for c in from_locator.evaluate.await_args_list]
    assert any("HTMLInputElement.prototype" in c for c in evaluate_calls)


@pytest.mark.asyncio
async def test_submit_blocked_when_verification_fails():
    page = MagicMock()
    page.content = AsyncMock(return_value="<html></html>")
    page.screenshot = AsyncMock()
    root = MagicMock()
    from_locator = _make_locator(input_values=["", "2026-07-26", "2026-07-26"])
    to_locator = _make_locator(input_values=["", "2026-07-26", "2026-07-26"])

    def locator_side_effect(selector: str):
        child = MagicMock()
        if "To Date" in selector or "toDate" in selector:
            child.first = to_locator
        else:
            child.first = from_locator
        return child

    root.locator = MagicMock(side_effect=locator_side_effect)
    service = MagicMock()
    service.get_report_root = AsyncMock(return_value=root)

    ctx = _run_context()
    token = set_run_context(ctx)
    try:
        with pytest.raises(PortalFromDateError) as exc_info:
            await apply_previous_from_date(
                page, "run-1", "report1", "comprehensive", filter_service=service
            )
        assert exc_info.value.code == "PORTAL_DATE_RANGE_MISMATCH"
    finally:
        reset_run_context(token)


async def test_to_date_field_not_found():
    page = MagicMock()
    page.content = AsyncMock(return_value="<html></html>")
    page.screenshot = AsyncMock()
    root = MagicMock()
    from_locator = _make_locator(input_values=[""])
    empty = MagicMock()
    empty.first = MagicMock()
    empty.first.count = AsyncMock(return_value=0)

    def locator_side_effect(selector: str):
        child = MagicMock()
        if any(token in selector for token in ("To Date", "toDate", "toInput")):
            child.first = empty.first
        else:
            child.first = from_locator
        return child

    root.locator = MagicMock(side_effect=locator_side_effect)
    service = MagicMock()
    service.get_report_root = AsyncMock(return_value=root)

    ctx = _run_context()
    token = set_run_context(ctx)
    try:
        with pytest.raises(PortalFromDateError) as exc_info:
            await apply_portal_date_range(
                page, "run-1", "report1", "comprehensive", filter_service=service
            )
        assert exc_info.value.code == "PORTAL_TO_DATE_FIELD_NOT_FOUND"
    finally:
        reset_run_context(token)


@pytest.mark.asyncio
async def test_both_dates_filled_on_empty_portal_fields():
    page = MagicMock()
    root = MagicMock()
    from_locator = _make_locator(input_values=["", "2026-07-25", "2026-07-25"])
    to_locator = _make_locator(input_values=["", "2026-07-26", "2026-07-26"])

    def locator_side_effect(selector: str):
        child = MagicMock()
        if "To Date" in selector or "toDate" in selector:
            child.first = to_locator
        else:
            child.first = from_locator
        return child

    root.locator = MagicMock(side_effect=locator_side_effect)
    service = MagicMock()
    service.get_report_root = AsyncMock(return_value=root)

    ctx = _run_context()
    token = set_run_context(ctx)
    try:
        await apply_portal_date_range(
            page, "run-1", "report1", "comprehensive", filter_service=service
        )
    finally:
        reset_run_context(token)

    assert from_locator.fill.await_count >= 1
    assert to_locator.fill.await_count >= 1


def test_resolve_phase1_to_date_format_yyyy_mm_dd():
    value = resolve_phase1_to_date(
        moment=datetime(2026, 7, 26, 12, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    )
    assert value == "2026-07-26"


@pytest.mark.asyncio
async def test_phase1_bootstraps_empty_to_date_to_today():
    page = MagicMock()
    root = MagicMock()
    from_locator = _make_locator(input_values=["", "2026-07-25", "2026-07-25", "2026-07-26"])
    to_locator = _make_locator(input_values=["", "2026-07-26", "2026-07-26"])

    def locator_side_effect(selector: str):
        child = MagicMock()
        if "To Date" in selector or "toDate" in selector:
            child.first = to_locator
        else:
            child.first = from_locator
        return child

    root.locator = MagicMock(side_effect=locator_side_effect)
    service = MagicMock()
    service.get_report_root = AsyncMock(return_value=root)

    ctx = _run_context()
    token = set_run_context(ctx)
    try:
        await apply_previous_from_date(
            page, "run-1", "report1", "comprehensive", filter_service=service
        )
    finally:
        reset_run_context(token)

    assert to_locator.fill.await_count >= 1


@pytest.mark.asyncio
async def test_phase1_waits_for_portal_to_date_initialization():
    page = MagicMock()
    root = MagicMock()
    from_locator = _make_locator(input_values=["", "2026-07-25", "2026-07-25", "2026-07-26"])
    to_locator = _make_locator(input_values=["", "2026-07-26", "2026-07-26"])

    def locator_side_effect(selector: str):
        child = MagicMock()
        if "To Date" in selector or "toDate" in selector:
            child.first = to_locator
        else:
            child.first = from_locator
        return child

    root.locator = MagicMock(side_effect=locator_side_effect)
    service = MagicMock()
    service.get_report_root = AsyncMock(return_value=root)

    ctx = _run_context()
    token = set_run_context(ctx)
    try:
        await apply_previous_from_date(
            page, "run-1", "report1", "comprehensive", filter_service=service
        )
    finally:
        reset_run_context(token)

    assert from_locator.fill.await_count >= 1
    assert to_locator.fill.await_count >= 1


@pytest.mark.asyncio
async def test_to_date_mismatch_raises_range_error():
    page = MagicMock()
    root = MagicMock()
    from_locator = _make_locator(input_values=["", "2026-07-25", "2026-07-25"])
    to_locator = _make_locator(input_values=["", "2026-07-25", "2026-07-25"])

    def locator_side_effect(selector: str):
        child = MagicMock()
        if "To Date" in selector or "toDate" in selector:
            child.first = to_locator
        else:
            child.first = from_locator
        return child

    root.locator = MagicMock(side_effect=locator_side_effect)
    service = MagicMock()
    service.get_report_root = AsyncMock(return_value=root)

    ctx = _run_context()
    token = set_run_context(ctx)
    try:
        with pytest.raises(PortalFromDateError) as exc_info:
            await apply_previous_from_date(
                page, "run-1", "report1", "comprehensive", filter_service=service
            )
        assert exc_info.value.code == "PORTAL_DATE_RANGE_MISMATCH"
    finally:
        reset_run_context(token)


@pytest.mark.asyncio
async def test_field_not_found_error():
    page = MagicMock()
    page.content = AsyncMock(return_value="<html></html>")
    page.screenshot = AsyncMock()
    root = MagicMock()
    missing = MagicMock()
    missing.count = AsyncMock(return_value=0)
    child = MagicMock()
    child.first = missing
    root.locator = MagicMock(return_value=child)
    service = MagicMock()
    service.get_report_root = AsyncMock(return_value=root)

    ctx = _run_context()
    token = set_run_context(ctx)
    try:
        with pytest.raises(PortalFromDateError) as exc_info:
            await apply_previous_from_date(
                page, "run-1", "report1", "comprehensive", filter_service=service
            )
        assert exc_info.value.code == "PORTAL_FROM_DATE_FIELD_NOT_FOUND"
    finally:
        reset_run_context(token)


@pytest.mark.asyncio
async def test_report1_apply_filters_and_submit_calls_helper():
    from app.automation.handlers.base import BaseReportHandler
    from app.automation.reports import REPORT_1

    class _Handler(BaseReportHandler):
        async def execute(self, page, session, report):
            raise NotImplementedError

    handler = _Handler()
    page = MagicMock()
    report_root = MagicMock()
    handler.filter_service.get_report_root = AsyncMock(return_value=report_root)
    handler.discovery_service.discover_fields = AsyncMock(return_value=[])
    handler.filter_service.apply_filters = AsyncMock(return_value={"dateRange": "Previous Day"})
    handler.filter_service.validate_mandatory = AsyncMock()
    handler.generator.generate_report = AsyncMock()
    handler.generator.count_rows = AsyncMock(return_value=5)
    handler.generator.verify_report_displayed = AsyncMock(return_value=True)
    handler.navigation.verify_report_page = AsyncMock(return_value=True)

    with patch(
        "app.automation.handlers.base.build_filters_from_discovery",
        return_value=[],
    ), patch(
        "app.automation.handlers.base.apply_previous_from_date",
        new_callable=AsyncMock,
    ) as mock_apply, patch(
        "app.automation.handlers.base.log_phase1_submit_clicked",
    ) as mock_log:
        ctx = RunContext(
            run_id="run-r1",
            timing=RunTiming(run_id="run-r1"),
            phase1_from_date="2026-07-25",
        )
        token = set_run_context(ctx)
        try:
            await handler.apply_filters_and_submit(page, REPORT_1)
        finally:
            reset_run_context(token)

        mock_apply.assert_awaited_once()
        mock_log.assert_called_once()
        handler.generator.generate_report.assert_awaited_once()


@pytest.mark.asyncio
async def test_report1_feedback_extract_calls_helper():
    from app.automation.workflow import attempt_feedback_extract

    page = MagicMock()
    extractor = MagicMock()
    navigation = MagicMock()
    navigation.navigate_to_report = AsyncMock()
    filter_service = MagicMock()
    filter_service.get_report_root = AsyncMock(return_value=MagicMock())
    filter_service.apply_filters = AsyncMock(return_value={"dateRange": "Previous Day"})
    filter_service.validate_mandatory = AsyncMock()
    discovery = MagicMock()
    discovery.discover_fields = AsyncMock(return_value=[])
    generator = MagicMock()
    generator.generate_report = AsyncMock()
    generator.verify_report_displayed = AsyncMock(return_value=False)

    with patch(
        "app.automation.workflow.build_filters_from_discovery",
        return_value=[],
    ), patch(
        "app.automation.workflow.apply_previous_from_date",
        new_callable=AsyncMock,
    ) as mock_apply, patch(
        "app.automation.workflow.log_phase1_submit_clicked",
    ) as mock_log:
        ctx = RunContext(
            run_id="run-r1",
            timing=RunTiming(run_id="run-r1"),
            phase1_from_date="2026-07-25",
        )
        token = set_run_context(ctx)
        try:
            await attempt_feedback_extract(
                page, extractor, navigation, filter_service, discovery, generator
            )
        finally:
            reset_run_context(token)

        mock_apply.assert_awaited_once()
        mock_log.assert_called_once()
        generator.generate_report.assert_awaited_once()


@pytest.mark.asyncio
async def test_report2_feedback_division_extract_calls_helper():
    from app.automation.report2_feedback import attempt_feedback_division_extract

    page = MagicMock()
    extractor = MagicMock()
    navigation = MagicMock()
    navigation.navigate_to_report = AsyncMock()
    filter_service = MagicMock()
    filter_service.get_report_root = AsyncMock(return_value=MagicMock())
    filter_service.apply_filters = AsyncMock(return_value={"View": "Division Wise"})
    filter_service.validate_mandatory = AsyncMock()
    discovery = MagicMock()
    generator = MagicMock()
    generator.generate_report = AsyncMock()
    generator.verify_report_displayed = AsyncMock(return_value=False)

    with patch(
        "app.automation.report2_feedback.apply_previous_from_date",
        new_callable=AsyncMock,
    ) as mock_apply, patch(
        "app.automation.report2_feedback.log_phase1_submit_clicked",
    ) as mock_log:
        ctx = RunContext(
            run_id="run-r2",
            timing=RunTiming(run_id="run-r2"),
            phase1_from_date="2026-07-25",
        )
        token = set_run_context(ctx)
        try:
            await attempt_feedback_division_extract(
                page, extractor, navigation, filter_service, discovery, generator
            )
        finally:
            reset_run_context(token)

        mock_apply.assert_awaited_once()
        assert mock_apply.await_args.args[3] == "feedback"
        mock_log.assert_called_once()
        generator.generate_report.assert_awaited_once()
