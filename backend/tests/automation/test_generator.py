"""Unit tests for report generation service."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.automation.generator import ReportGenerationError, ReportGeneratorService


@pytest.mark.asyncio
async def test_generate_report_clicks_visible_button():
    service = ReportGeneratorService()
    frame = MagicMock()
    page = MagicMock()
    page.wait_for_load_state = AsyncMock()

    button = MagicMock()
    button.is_visible = AsyncMock(return_value=True)
    button.click = AsyncMock()

    submit_locator = MagicMock()
    submit_locator.count = AsyncMock(return_value=1)
    submit_locator.nth.return_value = button

    table = MagicMock()
    table.count = AsyncMock(return_value=1)
    table.is_visible = AsyncMock(return_value=True)
    table.wait_for = AsyncMock()
    table.first = table

    def locator_side_effect(selector):
        if any(token in selector for token in ("loading", "loader", "spinner", "Loader", "Loading")):
            empty = MagicMock()
            empty.count = AsyncMock(return_value=0)
            return empty
        if "table" in selector or "grid" in selector:
            return table
        return submit_locator

    frame.locator.side_effect = locator_side_effect

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(service, "_is_export_button", AsyncMock(return_value=False))
        await service.generate_report(frame, page)

    button.click.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_report_raises_when_no_button():
    service = ReportGeneratorService()
    frame = MagicMock()
    page = MagicMock()

    empty = MagicMock()
    empty.count = AsyncMock(return_value=0)
    empty.nth.return_value = empty
    frame.locator.return_value = empty

    with pytest.raises(ReportGenerationError, match="button not found"):
        await service.generate_report(frame, page)


@pytest.mark.asyncio
async def test_find_generate_button_prefers_report_submit_over_navigation_search():
    service = ReportGeneratorService()
    root = MagicMock()

    submit_button = MagicMock()
    submit_button.is_visible = AsyncMock(return_value=True)
    submit_button.inner_text = AsyncMock(return_value="")
    submit_button.get_attribute = AsyncMock(
        side_effect=lambda name: {"id": "submitbtn", "type": "submit"}.get(name)
    )

    nav_button = MagicMock()
    nav_button.is_visible = AsyncMock(return_value=True)
    nav_button.inner_text = AsyncMock(return_value="Search Complaint")
    nav_button.get_attribute = AsyncMock(return_value="")

    empty_locator = MagicMock()
    empty_locator.count = AsyncMock(return_value=0)

    submit_locator = MagicMock()
    submit_locator.count = AsyncMock(return_value=1)
    submit_locator.nth.return_value = submit_button

    nav_locator = MagicMock()
    nav_locator.count = AsyncMock(return_value=1)
    nav_locator.nth.return_value = nav_button

    def locator_side_effect(selector):
        if selector == "#submitbtn":
            return submit_locator
        if selector == "button:has-text('Search')":
            return nav_locator
        return empty_locator

    root.locator.side_effect = locator_side_effect

    assert await service._find_generate_button(root) is submit_button


@pytest.mark.asyncio
async def test_count_rows():
    service = ReportGeneratorService()
    root = MagicMock()

    table = MagicMock()
    table.count = AsyncMock(return_value=1)

    rows = MagicMock()
    rows.count = AsyncMock(return_value=5)
    table.locator.return_value = rows

    table_wrapper = MagicMock()
    table_wrapper.first = table

    root.locator.return_value = table_wrapper

    assert await service.count_rows(root) == 5
