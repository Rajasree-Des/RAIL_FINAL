"""Fresh manual CDP generation for SCR Train and SCR Station."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.automation.schemas import MultiReportResult, ReportResult
from app.domain.entities.user import User, UserRole
from app.features.auth.dependencies import require_officer_or_admin, validate_csrf_token
from app.features.reports.scr_fresh import verify_current_run_source
from app.features.reports.service import build_config_snapshot
from app.features.reports.schemas import ManualGenerateRequest
from app.main import app
from datetime import UTC, datetime

ACCEPTANCE_R5 = [
    "scr-train.complaint_ref_no",
    "scr-train.created_on",
    "scr-train.user_id",
    "scr-train.comp_type_name",
    "scr-train.complaint_desc",
]

ACCEPTANCE_R6 = [
    "scr-station.complaint_ref_no",
    "scr-station.train_station",
    "scr-station.comp_type_name",
    "scr-station.remarks",
    "scr-station.user_id",
]


@pytest.fixture
def officer_user() -> User:
    now = datetime.now(UTC)
    return User(
        id="test-officer",
        username="officer",
        email="officer@test.local",
        password_hash="hash",
        role=UserRole.OFFICER,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
async def api_client(officer_user: User):
    async def override_user() -> User:
        return officer_user

    def override_csrf() -> None:
        return None

    app.dependency_overrides[require_officer_or_admin] = override_user
    app.dependency_overrides[validate_csrf_token] = override_csrf

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("slug", "columns"),
    [
        ("scr-train", ACCEPTANCE_R5),
        ("scr-station", ACCEPTANCE_R6),
    ],
)
async def test_scr_manual_generate_uses_fresh_cdp_not_process_only(
    api_client: AsyncClient,
    slug: str,
    columns: list[str],
):
    with patch("app.features.reports.service.AutomationService") as mock_cls:
        mock_service = AsyncMock()
        mock_service.start_manual_async.return_value = (f"run-{slug}", "running")
        mock_cls.return_value = mock_service

        response = await api_client.post(
            f"/api/v1/reports/{slug}/generate",
            json={
                "date_from": "2026-07-25",
                "date_to": "2026-07-26",
                "selected_column_ids": columns,
                "column_order": columns,
                "export_format": "xlsx",
                "requested_formats": ["xlsx", "pdf"],
                "configuration_source": "manual_snapshot",
                "force_fresh_extraction": True,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == f"run-{slug}"
    assert payload["status"] == "Extracting"
    mock_service.start_manual_async.assert_awaited_once()
    call_kwargs = mock_service.start_manual_async.await_args.kwargs
    assert call_kwargs["report_slugs"] == [slug]
    manual_config = call_kwargs["manual_config"]
    assert manual_config["force_fresh_extraction"] is True
    assert manual_config["generation_mode"] == "fresh_extraction"
    assert manual_config["selected_column_ids"] == columns


@pytest.mark.asyncio
async def test_scr_manual_generate_runs_single_report_only(api_client: AsyncClient):
    with patch("app.features.reports.service.AutomationService") as mock_cls:
        mock_service = AsyncMock()
        mock_service.start_manual_async.return_value = ("run-r5", "running")
        mock_cls.return_value = mock_service

        await api_client.post(
            "/api/v1/reports/scr-train/generate",
            json={
                "date_from": "2026-07-25",
                "date_to": "2026-07-26",
                "selected_column_ids": ACCEPTANCE_R5,
                "column_order": ACCEPTANCE_R5,
                "force_fresh_extraction": True,
            },
        )

    assert mock_service.start_manual_async.await_args.kwargs["report_slugs"] == ["scr-train"]


def test_build_config_snapshot_includes_force_fresh_extraction():
    body = ManualGenerateRequest(
        date_from="2026-07-25",
        date_to="2026-07-26",
        selected_column_ids=ACCEPTANCE_R5,
        column_order=ACCEPTANCE_R5,
        force_fresh_extraction=True,
    )
    snapshot = build_config_snapshot(body, report_slug="scr-train")
    assert snapshot["force_fresh_extraction"] is True


def test_verify_current_run_source_rejects_path_without_run_id(tmp_path: Path):
    csv_path = tmp_path / "scr-train_complaints_raw.csv"
    csv_path.write_text("header\n", encoding="utf-8")
    run_id = str(uuid4())
    with pytest.raises(ValueError, match="STALE_SOURCE_REJECTED"):
        verify_current_run_source(
            csv_path,
            run_id=run_id,
            report_slug="scr-train",
        )


def test_verify_current_run_source_accepts_run_scoped_path(tmp_path: Path):
    run_id = str(uuid4())
    run_dir = tmp_path / "scr-train" / run_id
    run_dir.mkdir(parents=True)
    csv_path = run_dir / "scr-train_complaints_raw.csv"
    csv_path.write_text("header\n", encoding="utf-8")
    verify_current_run_source(
        csv_path,
        run_id=run_id,
        report_slug="scr-train",
    )


@pytest.mark.asyncio
async def test_finalize_mixed_results_sets_completed_not_stopped(test_session):
    from app.automation.run_registry import finalize_cdp_run
    from app.infrastructure.database.models import AutomationRunModel

    run_id = str(uuid4())
    run = AutomationRunModel(
        id=run_id,
        profile_id="test-profile",
        status="running",
        trigger_type="cdp_in_process",
    )
    test_session.add(run)
    await test_session.commit()

    result = MultiReportResult(
        success=False,
        connected=True,
        tab_found=True,
        reports=[
            ReportResult(slug="scr-train", status="failed", error="failed"),
            ReportResult(slug="scr-station", status="success"),
        ],
        run_id=run_id,
        reports_successful=1,
        reports_failed=1,
        stopped_early=False,
    )
    finalized = await finalize_cdp_run(test_session, run_id, result)
    assert finalized is not None
    assert finalized.status == "completed"
    assert finalized.success_count == 1
    assert finalized.failure_count == 1
