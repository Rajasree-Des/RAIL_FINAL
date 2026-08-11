"""Tests for /dashboard/analytics aggregation from report output CSVs."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

import app.features.dashboard.analytics as analytics_mod
from app.core.security.password import password_hasher
from app.domain.entities.user import User, UserRole
from app.features.auth.dependencies import get_current_active_user
from app.features.dashboard.analytics import DashboardAnalyticsService, clear_analytics_cache
from app.infrastructure.database.models import (
    AutomationArtifactModel,
    AutomationProfileModel,
    AutomationRunModel,
    UserModel,
)
from app.infrastructure.database.session import get_db_session
from app.main import app


@pytest.fixture(autouse=True)
def _fresh_cache(monkeypatch):
    clear_analytics_cache()
    # Tests write CSVs to tmp dirs outside the storage roots
    monkeypatch.setattr(analytics_mod, "is_under_storage", lambda _p: True)
    yield
    clear_analytics_cache()


@pytest.fixture
async def profile(test_session: AsyncSession) -> AutomationProfileModel:
    row = AutomationProfileModel(
        id="profile-an",
        name="CDP",
        slug="cdp-analytics",
        portal_url="https://example.test",
        username_encrypted="x",
        password_encrypted="y",
    )
    test_session.add(row)
    await test_session.commit()
    return row


@pytest.fixture
async def an_user(test_session: AsyncSession) -> UserModel:
    user = UserModel(
        id="an-user",
        username="anuser",
        email="an@example.com",
        password_hash=password_hasher.hash("TestPass123"),
        role="admin",
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    return user


def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(headers)
        writer.writerows(rows)
    return str(path)


COMP_HEADERS = [
    "S.No.", "Organisation", "Opening Balance", "Received", "% Share", "Closed",
    "Closing Balance", "% Disposal", "Avg. Disposal Time", "Avg. Rating",
    "Avg. Pendency Time", "Forwarded", "Avg. FRT",
]
FB_HEADERS = [
    "S.No.", "Organisation", "Feedback Received", "% Feedback",
    "Excellent", "Satisfactory", "Unsatisfactory", "% Unsatisfactory",
]
TRAIN_HEADERS = [
    "S.No.", "Train Name", "Owning Zone", "Owning Division", "Train No.",
    "Received", "% Share", "Closed", "% Closed", "Pending", "Average Rating",
]
SCR_HEADERS = ["Ref. No.", "Mode", "Rating", "Status", "Sub Type",
               "Train/Station", "Type", "trainNameForReport/Station Name"]


def _build_fixture_run(tmp_path: Path, profile_id: str) -> AutomationRunModel:
    zone_comp = _write_csv(
        tmp_path / "report1.csv", COMP_HEADERS,
        [
            ["1", "Northern Railway", "5", "100", "10", "90", "15", "90.00", "0:38", "Satisfactory", "0:18", "120", "0:11"],
            ["2", "Southern Railway", "2", "50", "5", "40", "12", "80.00", "0:40", "Excellent", "0:20", "60", "0:12"],
            ["", "Total", "7", "150", "", "130", "27", "86.67", "", "", "", "180", ""],
        ],
    )
    zone_fb = _write_csv(
        tmp_path / "report1_fb.csv", FB_HEADERS,
        [
            ["1", "Northern Railway", "30", "9.5", "10", "12", "8", "26.7"],
            ["2", "Southern Railway", "20", "6.3", "5", "6", "9", "45.0"],
        ],
    )
    div_comp = _write_csv(
        tmp_path / "division.csv",
        [h if h != "Organisation" else "Division" for h in COMP_HEADERS],
        [
            ["1", "DELHI DIVISION (Northern Railway)", "1", "40", "4", "38", "3", "95.00", "0:28", "Satisfactory", "0:14", "52", "0:17"],
            ["2", "MUMBAI DIVISION (Central Railway)", "1", "60", "6", "54", "7", "90.00", "0:30", "Satisfactory", "0:15", "70", "0:18"],
        ],
    )
    div_fb = _write_csv(
        tmp_path / "division_fb.csv", FB_HEADERS,
        [["1", "DELHI DIVISION (DLI)", "13", "5.3", "5", "4", "4", "30.8"]],
    )
    trains = _write_csv(
        tmp_path / "trains.csv", TRAIN_HEADERS,
        [
            ["1", "EXP A", "Z", "D", "12345", "9", "1", "9", "100.00", "0", "Satisfactory"],
            ["2", "EXP B", "Z", "D", "67890", "15", "2", "12", "80.00", "3", "Satisfactory"],
        ],
    )
    type_a = _write_csv(
        tmp_path / "types_security.csv", TRAIN_HEADERS,
        [["1", "EXP A", "Z", "D", "12345", "30", "1", "30", "100.00", "0", "Nil"]],
    )
    type_b = _write_csv(
        tmp_path / "types_bedroll.csv", TRAIN_HEADERS,
        [["1", "EXP B", "Z", "D", "67890", "10", "1", "10", "100.00", "0", "Nil"]],
    )
    types_index = _write_csv(
        tmp_path / "types_index.csv",
        ["type_name", "csv_path", "row_count", "status", "error"],
        [
            ["Security", type_a, "1", "success", ""],
            ["Bedroll", type_b, "1", "success", ""],
            ["Water Availability", "missing.csv", "0", "failed", "boom"],
        ],
    )
    scr_train = _write_csv(
        tmp_path / "scr_train.csv", SCR_HEADERS,
        [
            ["1", "T", "Unsatisfactory", "Closed", "AC not working", "12721", "Electrical Equipment", "DAKSHIN EXP"],
            ["2", "T", "Unsatisfactory", "Closed", "Cockroach", "12721", "Coach - Cleanliness", "DAKSHIN EXP"],
            ["3", "T", "Unsatisfactory", "Pending", "Dirty coach", "17229", "Coach - Cleanliness", "SABARI EXP"],
        ],
    )
    scr_station = _write_csv(
        tmp_path / "scr_station.csv", SCR_HEADERS,
        [["1", "S", "Unsatisfactory", "Closed", "Misc", "BMT", "Miscellaneous", "BEGAMPET"]],
    )

    now = datetime.now(UTC)
    reports = [
        {
            "slug": "report1", "status": "success",
            "source_csv_path": zone_comp, "source_paths": [zone_comp, zone_fb],
            "completed_at": (now - timedelta(minutes=9)).isoformat(),
            "duration_seconds": 100.0,
        },
        {
            "slug": "division", "status": "success",
            "source_csv_path": div_comp, "source_paths": [div_comp, div_fb],
            "completed_at": (now - timedelta(minutes=7)).isoformat(),
            "duration_seconds": 80.0,
        },
        {
            "slug": "train-no", "status": "success",
            "source_csv_path": trains, "source_paths": [trains],
            "completed_at": (now - timedelta(minutes=6)).isoformat(),
            "duration_seconds": 15.0,
        },
        {
            "slug": "types", "status": "success",
            "source_csv_path": types_index, "source_paths": [type_a, type_b],
            "completed_at": (now - timedelta(minutes=4)).isoformat(),
            "duration_seconds": 60.0,
        },
        {
            "slug": "scr-train", "status": "success",
            "source_csv_path": scr_train, "source_paths": [scr_train],
            "completed_at": (now - timedelta(minutes=2)).isoformat(),
            "duration_seconds": 20.0,
        },
        {
            "slug": "scr-station", "status": "failed", "error": "extract failed",
            "source_csv_path": scr_station, "source_paths": [scr_station],
            "completed_at": None, "duration_seconds": None,
        },
    ]
    return AutomationRunModel(
        profile_id=profile_id,
        status="completed",
        trigger_type="cdp_in_process",
        success_count=5,
        failure_count=1,
        started_at=now - timedelta(minutes=10),
        completed_at=now - timedelta(minutes=1),
        result_json=json.dumps({"success": True, "reports": reports}),
        created_at=now - timedelta(minutes=10),
    )


@pytest.mark.asyncio
async def test_analytics_empty_db(test_session: AsyncSession):
    res = await DashboardAnalyticsService(test_session).analytics()
    assert res.has_data is False
    assert res.totals is None
    assert res.zones == []
    assert res.report_cards == []


@pytest.mark.asyncio
async def test_analytics_aggregates_from_report_csvs(
    test_session: AsyncSession, profile: AutomationProfileModel, tmp_path: Path
):
    run = _build_fixture_run(tmp_path, profile.id)
    test_session.add(run)
    await test_session.commit()
    test_session.add(
        AutomationArtifactModel(
            run_id=run.id,
            artifact_type="pdf",
            file_path="storage/output/pdf/report1/x.pdf",
            file_size_bytes=4225,
            report_slug="report1",
            status="ready",
        )
    )
    await test_session.commit()

    res = await DashboardAnalyticsService(test_session).analytics()
    assert res.has_data is True
    assert res.run_id == run.id

    # KPI totals: Total row excluded, sums from zone comprehensive + feedback CSVs
    assert res.totals is not None
    assert res.totals.complaints_received == 150
    assert res.totals.complaints_resolved == 130
    assert res.totals.feedback_received == 50
    assert res.totals.resolution_rate == pytest.approx(86.67, abs=0.01)

    # Zones ranked by complaints, feedback merged by organisation
    assert [z.zone for z in res.zones] == ["Northern Railway", "Southern Railway"]
    assert res.zones[0].rank == 1
    assert res.zones[0].feedback == 30
    assert res.zones[0].resolution_pct == pytest.approx(90.0)

    # Divisions ranked by complaints; feedback matched on base name
    assert res.divisions[0].division == "MUMBAI DIVISION (Central Railway)"
    delhi = next(d for d in res.divisions if d.division.startswith("DELHI"))
    assert delhi.feedback == 13

    # Trains ranked by complaints desc
    assert [t.train_no for t in res.trains] == ["67890", "12345"]
    assert res.trains[0].complaints == 15
    assert res.trains[0].resolution_pct == pytest.approx(80.0)

    # Complaint types: failed type excluded; percentages over the grand total
    assert [(t.type_name, t.complaints) for t in res.complaint_types] == [
        ("Security", 30),
        ("Bedroll", 10),
    ]
    assert res.complaint_types[0].percentage == pytest.approx(75.0)
    assert res.top_causes[0].name == "Security"

    # SCR train grouping: complaints counted, types deduped, resolution from Status
    t12721 = next(t for t in res.scr_trains if t.name == "12721")
    assert t12721.complaints == 2
    assert t12721.complaint_types == ["Coach - Cleanliness", "Electrical Equipment"]
    assert t12721.resolution_pct == pytest.approx(100.0)
    t17229 = next(t for t in res.scr_trains if t.name == "17229")
    assert t17229.resolution_pct == pytest.approx(0.0)
    assert res.scr_stations[0].name == "BMT"

    # Feedback distribution sums the feedback CSV columns
    assert res.feedback_distribution is not None
    assert res.feedback_distribution.excellent == 15
    assert res.feedback_distribution.unsatisfactory == 17

    # Complaints by report present for every populated report
    by_name = {c.name: c.count for c in res.complaints_by_report}
    assert by_name["Zone Wise Complaints"] == 150
    assert by_name["Top 20 Trains"] == 24
    assert by_name["SCR Train Report"] == 3

    # Report cards: statuses from result_json, artifact files with sizes
    cards = {c.slug: c for c in res.report_cards}
    assert cards["report1"].status == "success"
    assert cards["report1"].files[0].file_size_bytes == 4225
    assert cards["report1"].duration_seconds == 100.0
    assert cards["scr-station"].status == "failed"
    assert cards["scr-station"].generated_at is None


@pytest.mark.asyncio
async def test_analytics_cached_per_run(
    test_session: AsyncSession, profile: AutomationProfileModel, tmp_path: Path
):
    run = _build_fixture_run(tmp_path, profile.id)
    test_session.add(run)
    await test_session.commit()

    service = DashboardAnalyticsService(test_session)
    first = await service.analytics()
    second = await service.analytics()
    assert second is first  # cache hit, no recompute


@pytest.mark.asyncio
async def test_analytics_api_requires_auth(
    test_session: AsyncSession, an_user: UserModel
):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as anon:
        resp = await anon.get("/api/v1/dashboard/analytics")
        assert resp.status_code == 401

    now = datetime.now(UTC)
    domain = User(
        id=an_user.id,
        username=an_user.username,
        email=an_user.email,
        password_hash=an_user.password_hash,
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
            resp = await client.get("/api/v1/dashboard/analytics")
            assert resp.status_code == 200
            body = resp.json()
            assert body["has_data"] is False
            assert body["zones"] == []
    finally:
        app.dependency_overrides.clear()
