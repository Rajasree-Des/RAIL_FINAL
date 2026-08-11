"""Unit tests for filter application."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.automation.filters import FilterError, FilterService
from app.automation.report1_filters import (
    FilterFieldDefinition,
    resolve_filter_value,
)


def test_resolve_filter_value_today():
    value = resolve_filter_value("today", date_format="%d/%m/%Y")
    assert len(value) == 10
    assert value[2] == "/"


def test_resolve_filter_value_today_range():
    assert resolve_filter_value("today_range") == "Previous Day"
    assert resolve_filter_value("previous_day_range") == "Previous Day"


@pytest.mark.asyncio
async def test_apply_filters_select_field():
    service = FilterService()
    root = MagicMock()
    locator = MagicMock()
    locator.count = AsyncMock(return_value=1)
    locator.select_option = AsyncMock()
    locator.evaluate = AsyncMock(return_value="Today")
    root.locator.return_value.first = locator

    fields = [
        FilterFieldDefinition(
            name="dateRange",
            selector="#dateRange",
            field_type="select",
            value="today_range",
            label="Date Range",
        )
    ]

    applied = await service.apply_filters(root, fields)

    assert applied["dateRange"] == "Previous Day"
    locator.select_option.assert_awaited()


@pytest.mark.asyncio
async def test_apply_filters_previous_day_literal():
    service = FilterService()
    root = MagicMock()
    locator = MagicMock()
    locator.count = AsyncMock(return_value=1)
    locator.select_option = AsyncMock()
    locator.evaluate = AsyncMock(return_value="Today")
    root.locator.return_value.first = locator

    fields = [
        FilterFieldDefinition(
            name="dateRange",
            selector="#dateRange",
            field_type="select",
            value="Previous Day",
            label="Date Range",
        )
    ]

    applied = await service.apply_filters(root, fields)

    assert applied["dateRange"] == "Previous Day"
    locator.select_option.assert_awaited_with(label="Previous Day")


@pytest.mark.asyncio
async def test_apply_filters_sets_hidden_required_date_field():
    service = FilterService()
    root = MagicMock()
    locator = MagicMock()
    locator.count = AsyncMock(return_value=1)
    locator.is_visible = AsyncMock(return_value=False)
    locator.evaluate = AsyncMock()
    root.locator.return_value.first = locator

    fields = [
        FilterFieldDefinition(
            name="fromDate",
            selector="#fromDate",
            field_type="date",
            value="today_iso",
            label="From Date",
        )
    ]

    applied = await service.apply_filters(root, fields)

    assert applied["fromDate"]
    locator.evaluate.assert_awaited()


@pytest.mark.asyncio
async def test_get_report_root_falls_back_to_main_page():
    page = MagicMock()
    page.wait_for_selector = AsyncMock()

    iframe_locator = MagicMock()
    iframe_locator.count = AsyncMock(return_value=0)

    controls_locator = MagicMock()
    controls_locator.count = AsyncMock(return_value=2)

    def locator_side_effect(selector: str):
        if selector == "iframe":
            return iframe_locator
        if "select" in selector:
            return controls_locator
        return MagicMock()

    page.locator.side_effect = locator_side_effect

    frame_loc = MagicMock()
    frame_controls = MagicMock()
    frame_controls.count = AsyncMock(return_value=0)
    frame_loc.locator.return_value = frame_controls
    page.frame_locator.return_value.first = frame_loc

    root = await FilterService.get_report_root(page)

    assert root is page


@pytest.mark.asyncio
async def test_apply_filters_raises_when_required_missing():
    service = FilterService()
    frame = MagicMock()
    locator = MagicMock()
    locator.count = AsyncMock(return_value=0)
    frame.locator.return_value.first = locator

    fields = [
        FilterFieldDefinition(
            name="fromDate",
            selector="#missing",
            field_type="date",
            value="today",
            required=True,
        )
    ]

    with pytest.raises(FilterError, match="Required filter field not found"):
        await service.apply_filters(frame, fields)


@pytest.mark.asyncio
async def test_validate_mandatory_passes():
    service = FilterService()
    frame = MagicMock()
    locator = MagicMock()
    locator.count = AsyncMock(return_value=1)
    locator.input_value = AsyncMock(return_value="08/07/2026")
    frame.locator.return_value.first = locator

    fields = [
        FilterFieldDefinition(
            name="fromDate",
            selector="#fromDate",
            field_type="date",
            value="today",
            required=True,
        )
    ]
    await service.validate_mandatory(frame, fields, {"fromDate": "08/07/2026"})


@pytest.mark.asyncio
async def test_validate_mandatory_raises():
    service = FilterService()
    frame = MagicMock()
    locator = MagicMock()
    locator.count = AsyncMock(return_value=1)
    locator.input_value = AsyncMock(return_value="")
    frame.locator.return_value.first = locator

    fields = [
        FilterFieldDefinition(
            name="fromDate",
            selector="#fromDate",
            field_type="date",
            value="today",
            required=True,
        )
    ]

    with pytest.raises(FilterError, match="Mandatory filters missing"):
        await service.validate_mandatory(frame, fields, {"fromDate": ""})
