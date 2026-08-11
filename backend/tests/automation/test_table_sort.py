"""Unit tests for Received / Feedback Received column sorting."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.automation.table_sort import (
    FEEDBACK_RECEIVED_COLUMN,
    RECEIVED_COLUMN,
    ReceivedColumnService,
    ReceivedSortError,
)


@pytest.mark.asyncio
async def test_sort_received_descending_verifies_on_header_class():
    service = ReceivedColumnService()
    header = MagicMock()
    header.click = AsyncMock()
    header.wait_for = AsyncMock()
    header.get_attribute = AsyncMock(side_effect=["sorting_desc", None])

    service._find_column_header = AsyncMock(return_value=header)
    service._wait_for_table_stable = AsyncMock()
    service._rows_indicate_descending = AsyncMock(return_value=False)

    root = MagicMock()
    page = MagicMock()

    await service.sort_received_descending(root, page)

    assert header.click.await_count == 2
    service._find_column_header.assert_awaited_with(root, page, RECEIVED_COLUMN)
    service._wait_for_table_stable.assert_awaited()


@pytest.mark.asyncio
async def test_sort_feedback_received_descending_uses_feedback_column():
    service = ReceivedColumnService()
    header = MagicMock()
    header.click = AsyncMock()
    header.wait_for = AsyncMock()
    header.get_attribute = AsyncMock(side_effect=["sorting_desc", None])

    service._find_column_header = AsyncMock(return_value=header)
    service._wait_for_table_stable = AsyncMock()
    service._rows_indicate_descending = AsyncMock(return_value=False)

    root = MagicMock()
    page = MagicMock()

    await service.sort_feedback_received_descending(root, page)

    assert header.click.await_count == 2
    service._find_column_header.assert_awaited_with(
        root, page, FEEDBACK_RECEIVED_COLUMN
    )


@pytest.mark.asyncio
async def test_sort_received_descending_retries_once_then_raises():
    service = ReceivedColumnService()
    header = MagicMock()
    header.click = AsyncMock()
    header.wait_for = AsyncMock()
    header.get_attribute = AsyncMock(return_value="sorting")

    service._find_column_header = AsyncMock(return_value=header)
    service._wait_for_table_stable = AsyncMock()
    service._verify_descending_sort = AsyncMock(return_value=False)

    root = MagicMock()
    page = MagicMock()

    with pytest.raises(ReceivedSortError, match="verification failed"):
        await service.sort_received_descending(root, page)

    assert header.click.await_count == 6  # 2 attempts × (2 clicks + 1 recovery)
    assert service._verify_descending_sort.await_count == 4


@pytest.mark.asyncio
async def test_sort_received_descending_raises_when_header_missing():
    service = ReceivedColumnService()
    service._find_column_header = AsyncMock(return_value=None)

    with pytest.raises(ReceivedSortError, match="header not found"):
        await service.sort_received_descending(MagicMock(), MagicMock())
