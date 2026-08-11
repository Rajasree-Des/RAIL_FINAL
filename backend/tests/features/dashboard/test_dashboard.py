"""Tests for the /dashboard/summary API and derivation logic."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.automation.reports import catalog
from app.core.security.password import password_hasher
from app.domain.entities.user import User, UserRole
from app.features.auth.dependencies import (
    get_current_active_user,
    require_admin,
    validate_csrf_token,
)
from app.features.dashboard.service import DashboardService, canonical_run_status
from app.features.dashboard.analytics import (
    DISPLAY_NAMES,
    DashboardAnalyticsService,
    clear_analytics_cache,
)
from app.infrastructure.database.models import (
    AutomationArtifactModel,
    AutomationProfileModel,
    AutomationRunModel,
    UserModel,
)
from app.infrastructure.database.session import get_db_session
from app.main import app


@pytest.fixture
async def dash_user(test_session: AsyncSession) -> UserModel:
    user = UserModel(
        id="dash-user",
        username="dashuser",
        email="dash@example.com",
        password_hash=password_hasher.hash("TestPass123"),
        role="admin",
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    return user


@pytest.fixture
async def profile(test_session: AsyncSession) -> AutomationProfileModel:
    row = AutomationProfileModel(
        id="profile-1",
        name="CDP",
        slug="cdp-test",
        portal_url="https://example.test",
        username_encrypted="x",
        password_encrypted="y",
    )
    test_session.add(row)
    await test_session.commit()
    return row


def _run(
    profile_id: str,
    *,
    status: str,
    success: int = 0,
    failure: int = 0,
    started_offset_min: float = 10,
    duration_s: float | None = 120,
    reports: list[dict] | None = None,
    created_offset_min: float | None = None,
) -> AutomationRunModel:
    now = datetime.now(UTC)
    started = now - timedelta(minutes=started_offset_min)
    completed = (
        started + timedelta(seconds=duration_s) if duration_s is not None else None
    )
    result_json = (
        json.dumps({"success": failure == 0, "connected": True, "reports": reports})
        if reports is not None
        else None
    )
    return AutomationRunModel(
        profile_id=profile_id,
        status=status,
        trigger_type="cdp_in_process",
        success_count=success,
        failure_count=failure,
        started_at=started,
        completed_at=completed if status in {"completed", "failed", "stopped"} else None,
        result_json=result_json,
        created_at=now - timedelta(minutes=created_offset_min if created_offset_min is not None else started_offset_min),
    )


@pytest.mark.asyncio
async def test_summary_empty_db_is_ready(test_session: AsyncSession, dash_user: UserModel):
    summary = await DashboardService(test_session).summary(dash_user.id)
    assert summary.current_status == "ready"
    assert summary.active_run_id is None
    assert summary.last_generated_at is None
    assert summary.estimated_duration_seconds is None
    # Configured fallback estimate (defaults to 15 minutes)
    assert summary.default_expected_duration_seconds == 15 * 60
    assert summary.total_enabled_reports == len(catalog.reports)
    assert all(r.status == "pending" for r in summary.reports)
    assert [r.slug for r in summary.reports] == [d.slug for d in catalog.reports]


@pytest.mark.asyncio
async def test_summary_derives_from_completed_run(
    test_session: AsyncSession, dash_user: UserModel, profile: AutomationProfileModel
):
    n = len(catalog.reports)
    reports = [
        {"slug": d.slug, "status": "success", "duration_seconds": 30.0}
        for d in catalog.reports
    ]
    run = _run(
        profile.id,
        status="completed",
        success=n,
        failure=0,
        duration_s=150,
        reports=reports,
    )
    test_session.add(run)
    await test_session.commit()

    art = AutomationArtifactModel(
        run_id=run.id,
        artifact_type="pdf",
        file_path="storage/output/pdf/report1/x.pdf",
        report_slug="report1",
        status="ready",
    )
    test_session.add(art)
    await test_session.commit()

    summary = await DashboardService(test_session).summary(dash_user.id)
    assert summary.current_status == "success"
    assert summary.last_run_status == "success"
    assert summary.last_generated_at is not None
    assert summary.successful_report_count == n
    assert summary.failed_report_count == 0
    assert summary.generated_report_count == 1
    assert summary.estimated_duration_seconds == pytest.approx(150, abs=1)
    by_slug = {r.slug: r for r in summary.reports}
    assert all(by_slug[d.slug].status == "success" for d in catalog.reports)
    # successful reports must not retain error text
    assert all(by_slug[d.slug].error is None for d in catalog.reports)


@pytest.mark.asyncio
async def test_summary_partial_success_mapping(
    test_session: AsyncSession, dash_user: UserModel, profile: AutomationProfileModel
):
    reports = [
        {"slug": "report1", "status": "success"},
        {"slug": "division", "status": "failed", "error": "sort failed"},
    ]
    run = _run(profile.id, status="completed", success=1, failure=1, reports=reports)
    test_session.add(run)
    await test_session.commit()

    summary = await DashboardService(test_session).summary(dash_user.id)
    assert summary.current_status == "partial_success"
    by_slug = {r.slug: r for r in summary.reports}
    assert by_slug["report1"].status == "success"
    assert by_slug["report1"].error is None
    assert by_slug["division"].status == "failed"
    assert by_slug["division"].error == "sort failed"
    # reports absent from the run stay pending
    assert by_slug["train-no"].status == "pending"


@pytest.mark.asyncio
async def test_summary_active_run_running(
    test_session: AsyncSession, dash_user: UserModel, profile: AutomationProfileModel
):
    old = _run(
        profile.id,
        status="completed",
        success=6,
        duration_s=100,
        started_offset_min=60,
    )
    active = _run(
        profile.id,
        status="running",
        duration_s=None,
        started_offset_min=1,
        reports=[{"slug": "report1", "status": "success"}],
    )
    test_session.add_all([old, active])
    await test_session.commit()

    summary = await DashboardService(test_session).summary(dash_user.id)
    assert summary.current_status == "running"
    assert summary.active_run_id == active.id
    # last generated still comes from the old completed run
    assert summary.last_generated_at is not None
    # per-slug status comes from the active run's progress, keyed by slug
    by_slug = {r.slug: r for r in summary.reports}
    assert by_slug["report1"].status == "success"
    assert by_slug["division"].status == "pending"


@pytest.mark.asyncio
async def test_stale_running_run_does_not_override_latest_terminal(
    test_session: AsyncSession, dash_user: UserModel, profile: AutomationProfileModel
):
    """An old unfinalized 'running' row must not overwrite the newest outcome."""
    stale = _run(
        profile.id,
        status="running",
        duration_s=None,
        started_offset_min=600,
        created_offset_min=600,
    )
    newest = _run(
        profile.id,
        status="completed",
        success=6,
        duration_s=120,
        started_offset_min=5,
        created_offset_min=5,
    )
    test_session.add_all([stale, newest])
    await test_session.commit()

    summary = await DashboardService(test_session).summary(dash_user.id)
    assert summary.current_status == "success"
    assert summary.active_run_id is None


@pytest.mark.asyncio
async def test_summary_estimated_duration_rolling_average(
    test_session: AsyncSession, dash_user: UserModel, profile: AutomationProfileModel
):
    r1 = _run(profile.id, status="completed", success=6, duration_s=100, started_offset_min=120)
    r2 = _run(profile.id, status="completed", success=6, duration_s=200, started_offset_min=60)
    # failed runs are excluded from the average
    r3 = _run(profile.id, status="failed", failure=6, duration_s=999, started_offset_min=30)
    test_session.add_all([r1, r2, r3])
    await test_session.commit()

    summary = await DashboardService(test_session).summary(dash_user.id)
    assert summary.estimated_duration_seconds == pytest.approx(150, abs=1)


def test_canonical_run_status_mapping():
    def make(status: str, success: int = 0, failure: int = 0) -> AutomationRunModel:
        return AutomationRunModel(
            profile_id="p", status=status, success_count=success, failure_count=failure
        )

    assert canonical_run_status(make("running")) == "running"
    assert canonical_run_status(make("pending")) == "running"
    assert canonical_run_status(make("paused")) == "paused"
    assert canonical_run_status(make("pause_requested")) == "paused"
    assert canonical_run_status(make("stopped")) == "stopped"
    assert canonical_run_status(make("failed", failure=3)) == "failed"
    assert canonical_run_status(make("completed", success=6)) == "success"
    assert canonical_run_status(make("completed", success=4, failure=2)) == "partial_success"
    assert canonical_run_status(make("completed", success=0, failure=6)) == "failed"


@pytest.mark.asyncio
async def test_dashboard_api_requires_auth_and_returns_summary(
    test_session: AsyncSession, dash_user: UserModel
):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as anon:
        resp = await anon.get("/api/v1/dashboard/summary")
        assert resp.status_code == 401

    now = datetime.now(UTC)
    domain = User(
        id=dash_user.id,
        username=dash_user.username,
        email=dash_user.email,
        password_hash=dash_user.password_hash,
        role=UserRole.ADMIN,
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    async def override_user() -> User:
        return domain

    async def override_db():
        yield test_session

    app.dependency_overrides[get_current_active_user] = override_user
    app.dependency_overrides[get_db_session] = override_db
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/dashboard/summary")
            assert resp.status_code == 200
            body = resp.json()
            assert body["current_status"] == "ready"
            assert body["total_enabled_reports"] == len(catalog.reports)
            assert isinstance(body["recent_activity"], list)
            assert [r["slug"] for r in body["reports"]] == [
                d.slug for d in catalog.reports
            ]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_config_updated_emitted_on_template_create(
    test_session: AsyncSession, dash_user: UserModel, monkeypatch
):
    calls: list[dict] = []

    async def fake_emit(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(
        "app.features.templates.controller.emit_activity", fake_emit
    )

    now = datetime.now(UTC)
    domain = User(
        id=dash_user.id,
        username=dash_user.username,
        email=dash_user.email,
        password_hash=dash_user.password_hash,
        role=UserRole.ADMIN,
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    async def override_user() -> User:
        return domain

    async def override_db():
        yield test_session

    app.dependency_overrides[require_admin] = override_user
    app.dependency_overrides[validate_csrf_token] = lambda: None
    app.dependency_overrides[get_db_session] = override_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/admin/templates",
                json={"name": "Dashboard Test Config", "slug": "dash-test"},
            )
            assert resp.status_code == 201, resp.text
    finally:
        app.dependency_overrides.clear()

    assert any(
        c.get("action") == "CONFIG_UPDATED"
        and c.get("user_id") == dash_user.id
        and c.get("status") == "success"
        for c in calls
    )


@pytest.mark.asyncio
async def test_analytics_report_cards_include_comprehensive_1013(
    test_session: AsyncSession, profile: AutomationProfileModel
):
    clear_analytics_cache()
    reports = [
        {"slug": d.slug, "status": "success", "duration_seconds": 20.0}
        for d in catalog.reports
    ]
    comprehensive = next(
        rep for rep in reports if rep["slug"] == "comprehensive-10-13"
    )
    comprehensive.update(
        {
            "completed_at": "2026-07-29T06:07:56.084514+00:00",
            "duration_seconds": 26.852,
            "row_count": 12,
            "processed_row_count": 12,
        }
    )
    run = _run(
        profile.id,
        status="completed",
        success=len(catalog.reports),
        failure=0,
        duration_s=180,
        reports=reports,
    )
    test_session.add(run)
    await test_session.flush()

    test_session.add_all(
        [
            AutomationArtifactModel(
                run_id=run.id,
                artifact_type="pdf",
                file_path="storage/output/pdf/comprehensive-10-13/sample.pdf",
                report_slug="comprehensive-10-13",
                status="ready",
                file_size_bytes=31725,
            ),
            AutomationArtifactModel(
                run_id=run.id,
                artifact_type="excel",
                file_path="storage/output/excel/comprehensive-10-13/sample.xlsx",
                report_slug="comprehensive-10-13",
                status="ready",
                file_size_bytes=18432,
            ),
        ]
    )
    await test_session.commit()

    analytics = await DashboardAnalyticsService(test_session).analytics()
    assert len(analytics.report_cards) == len(DISPLAY_NAMES)
    comp_card = next(c for c in analytics.report_cards if c.slug == "comprehensive-10-13")
    assert comp_card.name == "Report 10-13 (Comprehensive Reports)"
    assert comp_card.status == "success"
    assert comp_card.sections_total == 4
    assert comp_card.row_count == 12
    assert comp_card.duration_seconds == pytest.approx(26.852)

    files = {f.file_type: f for f in comp_card.files}
    assert files["pdf"].file_size_bytes == 31725
    assert files["excel"].file_size_bytes == 18432
    assert files["pdf"].download_url.startswith("/api/v1/automation/artifacts/")
    assert files["pdf"].preview_url.startswith("/api/v1/automation/artifacts/")
    assert files["excel"].download_url.startswith("/api/v1/automation/artifacts/")
    assert analytics.report_cards[-1].slug == "report18"
