"""Tests for Home page date range feature: API validation and run creation."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.automation.date_range import ReportDateRange


class TestDateRangeValidation:
    """Tests for date_from/date_to validation in the /start endpoint."""

    def test_validate_date_range_both_none_is_valid(self):
        from app.api.automation import _validate_date_range

        _validate_date_range(None, None)

    def test_validate_date_range_both_provided_valid(self):
        from app.api.automation import _validate_date_range

        _validate_date_range("2026-07-27", "2026-07-28")

    def test_validate_date_range_same_date_valid(self):
        from app.api.automation import _validate_date_range

        _validate_date_range("2026-07-28", "2026-07-28")

    def test_validate_date_range_only_date_from_raises_422(self):
        from fastapi import HTTPException

        from app.api.automation import _validate_date_range

        with pytest.raises(HTTPException) as exc_info:
            _validate_date_range("2026-07-27", None)
        assert exc_info.value.status_code == 422
        assert "Both date_from and date_to are required" in exc_info.value.detail

    def test_validate_date_range_only_date_to_raises_422(self):
        from fastapi import HTTPException

        from app.api.automation import _validate_date_range

        with pytest.raises(HTTPException) as exc_info:
            _validate_date_range(None, "2026-07-28")
        assert exc_info.value.status_code == 422

    def test_validate_date_range_invalid_format_raises_422(self):
        from fastapi import HTTPException

        from app.api.automation import _validate_date_range

        with pytest.raises(HTTPException) as exc_info:
            _validate_date_range("27-07-2026", "28-07-2026")
        assert exc_info.value.status_code == 422
        assert "YYYY-MM-DD" in exc_info.value.detail

    def test_validate_date_range_invalid_date_raises_422(self):
        from fastapi import HTTPException

        from app.api.automation import _validate_date_range

        with pytest.raises(HTTPException) as exc_info:
            _validate_date_range("2026-02-30", "2026-02-31")
        assert exc_info.value.status_code == 422

    def test_validate_date_range_from_after_to_raises_422(self):
        from fastapi import HTTPException

        from app.api.automation import _validate_date_range

        with pytest.raises(HTTPException) as exc_info:
            _validate_date_range("2026-07-28", "2026-07-27")
        assert exc_info.value.status_code == 422
        assert "date_from must not be after date_to" in exc_info.value.detail


class TestReportDateRangeDefaults:
    """Tests for default date range in Asia/Kolkata timezone."""

    def test_default_global_range_yesterday_to_today(self):
        moment = datetime(2026, 7, 28, 12, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
        dr = ReportDateRange.default_global_range(moment=moment)
        assert dr.date_from == date(2026, 7, 27)
        assert dr.date_to == date(2026, 7, 28)

    def test_default_global_range_at_midnight_boundary(self):
        moment = datetime(2026, 7, 28, 0, 30, tzinfo=ZoneInfo("Asia/Kolkata"))
        dr = ReportDateRange.default_global_range(moment=moment)
        assert dr.date_from == date(2026, 7, 27)
        assert dr.date_to == date(2026, 7, 28)

    def test_from_iso_creates_correct_range(self):
        dr = ReportDateRange.from_iso("2026-07-20", "2026-07-25")
        assert dr.date_from == date(2026, 7, 20)
        assert dr.date_to == date(2026, 7, 25)

    def test_from_iso_same_date(self):
        dr = ReportDateRange.from_iso("2026-07-25", "2026-07-25")
        assert dr.date_from == date(2026, 7, 25)
        assert dr.date_to == date(2026, 7, 25)


class TestCreateCdpRunWithDates:
    """Tests for create_cdp_run with date_from/date_to parameters."""

    @pytest.mark.asyncio
    async def test_create_cdp_run_stores_dates(self):
        from unittest.mock import MagicMock, AsyncMock, patch

        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        with patch(
            "app.automation.run_registry.ensure_cdp_profile",
            new_callable=AsyncMock,
        ) as mock_ensure:
            mock_profile = MagicMock()
            mock_profile.id = "profile-1"
            mock_ensure.return_value = mock_profile

            from app.automation.run_registry import create_cdp_run

            run = await create_cdp_run(
                mock_session,
                user_id="user-1",
                date_from="2026-07-20",
                date_to="2026-07-25",
            )

            assert run.date_from == date(2026, 7, 20)
            assert run.date_to == date(2026, 7, 25)

    @pytest.mark.asyncio
    async def test_create_cdp_run_no_dates_leaves_null(self):
        from unittest.mock import MagicMock, AsyncMock, patch

        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        with patch(
            "app.automation.run_registry.ensure_cdp_profile",
            new_callable=AsyncMock,
        ) as mock_ensure:
            mock_profile = MagicMock()
            mock_profile.id = "profile-1"
            mock_ensure.return_value = mock_profile

            from app.automation.run_registry import create_cdp_run

            run = await create_cdp_run(
                mock_session,
                user_id="user-1",
            )

            assert run.date_from is None
            assert run.date_to is None


class TestRunContextDateRange:
    """Tests for RunContext.date_range propagation."""

    def test_run_context_stores_date_range(self):
        from app.automation.run_context import RunContext
        from app.automation.timing import RunTiming

        dr = ReportDateRange.from_iso("2026-07-20", "2026-07-25")
        ctx = RunContext(
            run_id="run-1",
            timing=RunTiming(run_id="run-1"),
            date_range=dr,
            phase1_from_date=dr.iso_from(),
        )

        assert ctx.date_range is not None
        assert ctx.date_range.date_from == date(2026, 7, 20)
        assert ctx.date_range.date_to == date(2026, 7, 25)

    def test_get_context_date_range_returns_ctx_date_range(self):
        from app.automation.date_range import get_context_date_range
        from app.automation.run_context import RunContext, set_run_context, reset_run_context
        from app.automation.timing import RunTiming

        dr = ReportDateRange.from_iso("2026-07-15", "2026-07-20")
        ctx = RunContext(
            run_id="run-test",
            timing=RunTiming(run_id="run-test"),
            date_range=dr,
            phase1_from_date=dr.iso_from(),
        )
        token = set_run_context(ctx)
        try:
            result = get_context_date_range()
            assert result.date_from == date(2026, 7, 15)
            assert result.date_to == date(2026, 7, 20)
        finally:
            reset_run_context(token)

    def test_get_context_date_range_falls_back_to_default_when_no_context(self):
        from app.automation.date_range import get_context_date_range
        from app.automation.run_context import set_run_context, reset_run_context

        token = set_run_context(None)
        try:
            result = get_context_date_range()
            assert result.date_from is not None
            assert result.date_to is not None
        finally:
            reset_run_context(token)


class TestDateRangeTitleAndFilename:
    """Tests for title_suffix and filename_suffix formatting."""

    def test_title_suffix_single_date(self):
        dr = ReportDateRange.from_iso("2026-07-25", "2026-07-25")
        assert dr.title_suffix() == "on date 25-07-2026"

    def test_title_suffix_date_range(self):
        dr = ReportDateRange.from_iso("2026-07-20", "2026-07-25")
        assert dr.title_suffix() == "from 20-07-2026 to 25-07-2026"

    def test_filename_suffix_single_date(self):
        dr = ReportDateRange.from_iso("2026-07-25", "2026-07-25")
        assert dr.filename_suffix() == "25-07-2026"

    def test_filename_suffix_date_range(self):
        dr = ReportDateRange.from_iso("2026-07-20", "2026-07-25")
        assert dr.filename_suffix() == "20-07-2026_to_25-07-2026"
