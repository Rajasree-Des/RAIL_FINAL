"""API-level tests for Daily Summary persistence and auth isolation."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import NotFoundError
from app.features.daily_summary.service import DailySummaryService
from app.features.daily_summary.sources import RunSources
from app.infrastructure.database.models import AutomationRunModel, GeneratedSummaryModel


@pytest.mark.asyncio
async def test_generate_rejects_other_users_run():
    session = AsyncMock()
    run = AutomationRunModel(
        id="run-1",
        profile_id="p",
        status="completed",
        created_by="owner",
        result_json=json.dumps({"reports": []}),
    )
    session.get = AsyncMock(return_value=run)
    service = DailySummaryService(session)

    with pytest.raises(NotFoundError):
        await service.generate("run-1", "other-user")


@pytest.mark.asyncio
async def test_get_for_run_raises_summary_not_generated():
    session = AsyncMock()
    run = AutomationRunModel(
        id="run-1",
        profile_id="p",
        status="completed",
        created_by="owner",
        result_json="{}",
    )
    session.get = AsyncMock(return_value=run)
    service = DailySummaryService(session)

    from app.core.exceptions import SummaryNotGeneratedError

    with patch.object(service.repository, "get_by_run_and_user", new_callable=AsyncMock) as get_row:
        get_row.return_value = None
        with pytest.raises(SummaryNotGeneratedError):
            await service.get_for_run("run-1", "owner")


@pytest.mark.asyncio
async def test_generate_persists_previous_day_date():
    session = AsyncMock()
    run = AutomationRunModel(
        id="run-1",
        profile_id="p",
        status="completed",
        created_by="owner",
        result_json=json.dumps({"reports": []}),
    )
    session.get = AsyncMock(return_value=run)

    fake_row = GeneratedSummaryModel(
        id="sum-1",
        summary_type="daily_briefing",
        content="partial text",
        status="failed",
        run_id="run-1",
        report_date="14.07.2026",
        created_by="owner",
        metadata_json=json.dumps(
            {
                "source_reports": [],
                "source_row_counts": {},
                "missing_reports": ["train-no", "types", "scr-train", "scr-station"],
            }
        ),
    )

    service = DailySummaryService(session)
    with (
        patch(
            "app.features.daily_summary.service.previous_day_report_date",
            return_value="14.07.2026",
        ),
        patch("app.features.daily_summary.service.emit_activity", new_callable=AsyncMock),
        patch(
            "app.features.daily_summary.service.resolve_run_sources",
        ) as resolve,
        patch.object(service.repository, "upsert", new_callable=AsyncMock) as upsert,
    ):
        resolve.return_value = RunSources(
            run_id="run-1",
            user_id="owner",
            run_status="completed",
            reports={},
            missing_reports=["train-no", "types", "scr-train", "scr-station"],
            all_terminal=True,
        )
        upsert.return_value = fake_row
        result = await service.generate("run-1", "owner")
        assert result.report_date == "14.07.2026"
        assert result.status == "failed"
        assert upsert.await_args.kwargs["report_date"] == "14.07.2026"
