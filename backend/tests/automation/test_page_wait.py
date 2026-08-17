"""Tests for state-based page wait helpers."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.automation.page_wait import wait_for_cascade_settle, wait_for_state


@pytest.mark.asyncio
async def test_wait_for_state_succeeds_when_check_passes():
    calls = {"n": 0}

    async def check() -> bool:
        calls["n"] += 1
        return calls["n"] >= 2

    ok = await wait_for_state(
        check,
        timeout_seconds=1.0,
        interval_seconds=0.05,
        reason="test_wait",
        report_slug="report1",
        action="test",
    )
    assert ok is True
    assert calls["n"] >= 2


@pytest.mark.asyncio
async def test_wait_for_cascade_settle_delegates_to_portal_settle():
    root = MagicMock()
    page = MagicMock()
    with pytest.MonkeyPatch.context() as mp:
        mock_settle = AsyncMock(return_value=True)
        mp.setattr("app.automation.page_wait.wait_for_portal_settle", mock_settle)
        ok = await wait_for_cascade_settle(
            root,
            page,
            field_name="zone",
            report_slug="report1",
        )
    assert ok is True
    mock_settle.assert_awaited_once()
