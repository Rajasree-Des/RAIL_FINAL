"""Tests for account-scoped user activity feed."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.automation.config import config
from app.automation.run_registry import create_cdp_run, finalize_cdp_run, register_artifact
from app.automation.schemas import MultiReportResult, ReportResult
from app.core.security.password import password_hasher
from app.domain.entities.user import User, UserRole
from app.features.activity.hub import activity_hub
from app.features.activity.service import ActivityService, scrub_message, scrub_metadata
from app.features.auth.dependencies import get_current_active_user, require_admin, validate_csrf_token
from app.infrastructure.database.models import UserModel
from app.infrastructure.database.session import get_db_session
from app.main import app


@pytest.fixture
async def user_a(test_session: AsyncSession) -> UserModel:
    user = UserModel(
        id="user-a",
        username="usera",
        email="a@example.com",
        password_hash=password_hasher.hash("TestPass123"),
        role="admin",
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    return user


@pytest.fixture
async def user_b(test_session: AsyncSession) -> UserModel:
    user = UserModel(
        id="user-b",
        username="userb",
        email="b@example.com",
        password_hash=password_hasher.hash("TestPass123"),
        role="admin",
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    return user


@pytest.fixture
def domain_user_a(user_a: UserModel) -> User:
    now = datetime.now(UTC)
    return User(
        id=user_a.id,
        username=user_a.username,
        email=user_a.email,
        password_hash=user_a.password_hash,
        role=UserRole.ADMIN,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
async def activity_client(domain_user_a: User, test_session: AsyncSession):
    async def override_user() -> User:
        return domain_user_a

    async def override_db():
        yield test_session

    app.dependency_overrides[get_current_active_user] = override_user
    app.dependency_overrides[require_admin] = override_user
    app.dependency_overrides[validate_csrf_token] = lambda: None
    app.dependency_overrides[get_db_session] = override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


def test_scrub_metadata_drops_secrets():
    cleaned = scrub_metadata(
        {
            "password": "x",
            "token": "y",
            "report": "division",
            "nested": {"authorization": "Bearer x", "ok": 1},
            "items": [{"password": "z", "name": "ok"}],
        }
    )
    assert "password" not in cleaned
    assert "token" not in cleaned
    assert cleaned["report"] == "division"
    assert "authorization" not in cleaned["nested"]
    assert cleaned["nested"]["ok"] == 1
    assert "password" not in cleaned["items"][0]
    assert cleaned["items"][0]["name"] == "ok"


def test_scrub_message_redacts_secret_assignments():
    msg = scrub_message("failed with password=SuperSecret123 token: abc.def")
    assert "SuperSecret123" not in msg
    assert "abc.def" not in msg
    assert "[REDACTED]" in msg


def test_created_at_serialized_with_utc_offset():
    """Naive (SQLite) and aware timestamps must both serialize as aware UTC."""
    from app.features.activity.service import _created_at_iso

    naive_utc = datetime(2026, 7, 15, 14, 3, 15)
    assert _created_at_iso(naive_utc) == "2026-07-15T14:03:15+00:00"

    aware = datetime(2026, 7, 15, 14, 3, 15, tzinfo=UTC)
    assert _created_at_iso(aware) == "2026-07-15T14:03:15+00:00"

    assert _created_at_iso(None) == ""


def test_date_filters_normalized_to_utc():
    """IST day boundaries (+05:30) must convert to UTC before querying."""
    from datetime import timedelta, timezone

    from app.features.activity.controller import _to_utc

    ist = timezone(timedelta(hours=5, minutes=30))
    # 15 Jul 00:00:00 IST == 14 Jul 18:30:00 UTC
    start = _to_utc(datetime(2026, 7, 15, 0, 0, 0, tzinfo=ist))
    assert start == datetime(2026, 7, 14, 18, 30, 0)
    assert start.tzinfo is None

    # Naive inputs pass through unchanged (already UTC)
    naive = datetime(2026, 7, 15, 12, 0, 0)
    assert _to_utc(naive) is naive
    assert _to_utc(None) is None


@pytest.mark.asyncio
async def test_activity_user_isolation(
    test_session: AsyncSession, user_a: UserModel, user_b: UserModel
):
    service = ActivityService(test_session)
    await service.record(
        user_id=user_a.id,
        action="LOGIN",
        message="A logged in",
        status="success",
    )
    await service.record(
        user_id=user_b.id,
        action="LOGIN",
        message="B logged in",
        status="success",
    )
    a_list = await service.list_activity(user_a.id, limit=20)
    b_list = await service.list_activity(user_b.id, limit=20)
    assert len(a_list.items) == 1
    assert a_list.items[0].message == "A logged in"
    assert len(b_list.items) == 1
    assert b_list.items[0].message == "B logged in"


@pytest.mark.asyncio
async def test_activity_dedupe(test_session: AsyncSession, user_a: UserModel):
    user_id = user_a.id
    service = ActivityService(test_session)
    first = await service.record(
        user_id=user_id,
        action="PDF_DOWNLOADED",
        message="Downloaded once",
        status="success",
        dedupe_key="pdf_downloaded:art-1",
    )
    second = await service.record(
        user_id=user_id,
        action="PDF_DOWNLOADED",
        message="Downloaded again",
        status="success",
        dedupe_key="pdf_downloaded:art-1",
    )
    assert first is not None
    assert second is None
    listed = await service.list_activity(user_id)
    assert listed.total == 1


@pytest.mark.asyncio
async def test_hub_publish_reaches_subscriber(user_a: UserModel):
    user_id = user_a.id
    queue = await activity_hub.subscribe(user_id)
    try:
        await activity_hub.publish(user_id, {"id": "evt-1", "message": "hello"})
        event = await queue.get()
        assert event["id"] == "evt-1"
        assert event["message"] == "hello"
    finally:
        await activity_hub.unsubscribe(user_id, queue)


@pytest.mark.asyncio
async def test_activity_api_recent_and_list(
    activity_client: AsyncClient, test_session: AsyncSession, user_a: UserModel
):
    user_id = user_a.id
    service = ActivityService(test_session)
    await service.record(
        user_id=user_id,
        action="SETTINGS_UPDATED",
        message="Updated settings",
        status="info",
        report_slug="report1",
    )
    recent = await activity_client.get("/api/v1/activity/recent?limit=5")
    assert recent.status_code == 200
    body = recent.json()
    assert len(body["items"]) >= 1
    assert body["items"][0]["user_id"] == user_id

    listed = await activity_client.get("/api/v1/activity?status=info&report_slug=report1")
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1


@pytest.mark.asyncio
async def test_download_creates_activity(
    tmp_path,
    monkeypatch,
    activity_client: AsyncClient,
    test_session: AsyncSession,
    user_a: UserModel,
):
    user_id = user_a.id
    pdf_dir = tmp_path / "pdf" / "division"
    pdf_dir.mkdir(parents=True)
    pdf_path = pdf_dir / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 sample")

    monkeypatch.setattr(config, "output_pdf_dir", str(tmp_path / "pdf"))
    monkeypatch.setattr(config, "output_excel_dir", str(tmp_path / "excel"))
    monkeypatch.setattr(config, "extracted_data_dir", str(tmp_path / "extracted"))
    monkeypatch.setattr(config, "pdf_archive_dir", str(tmp_path / "archive"))
    (tmp_path / "excel").mkdir(exist_ok=True)
    (tmp_path / "extracted").mkdir(exist_ok=True)
    (tmp_path / "archive").mkdir(exist_ok=True)

    calls: list[dict] = []

    async def fake_emit(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr("app.features.activity.emit.emit_activity", fake_emit)

    run = await create_cdp_run(test_session, user_id=user_id)
    art = await register_artifact(
        test_session,
        run_id=run.id,
        report_slug="division",
        report_name="division",
        file_type="pdf",
        file_path=pdf_path,
    )
    assert art is not None

    assert any(c.get("action") == "PDF_GENERATED" for c in calls)

    resp = await activity_client.get(f"/api/v1/automation/artifacts/{art.id}/download")
    assert resp.status_code == 200
    assert any(c.get("action") == "PDF_DOWNLOADED" for c in calls)

    preview = await activity_client.get(f"/api/v1/automation/artifacts/{art.id}/preview")
    assert preview.status_code == 200
    assert any(c.get("action") == "PDF_PREVIEWED" for c in calls)


@pytest.mark.asyncio
async def test_failed_automation_records_error(
    test_session: AsyncSession, user_a: UserModel, monkeypatch
):
    user_id = user_a.id
    calls: list[dict] = []

    async def fake_emit(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr("app.features.activity.emit.emit_activity", fake_emit)

    run = await create_cdp_run(test_session, user_id=user_id)
    result = MultiReportResult(
        success=False,
        connected=True,
        tab_found=True,
        error="MIS session lost",
        error_code="MIS_SESSION_LOST",
        run_id=run.id,
        reports=[
            ReportResult(
                slug="report1",
                dataset_key="report1",
                status="failed",
                error="auth lost",
            )
        ],
    )
    await finalize_cdp_run(test_session, run.id, result, user_id=user_id)
    assert any(
        c.get("action") == "AUTOMATION_FAILED" and c.get("status") == "error" for c in calls
    )


@pytest.mark.asyncio
async def test_service_publish_notifies_hub(test_session: AsyncSession, user_a: UserModel):
    user_id = user_a.id
    queue = await activity_hub.subscribe(user_id)
    try:
        service = ActivityService(test_session)
        entry = await service.record(
            user_id=user_id,
            action="LOGIN",
            message="Hub notify",
            status="success",
        )
        assert entry is not None
        event = await queue.get()
        assert event["id"] == entry.id
        assert event["message"] == "Hub notify"
    finally:
        await activity_hub.unsubscribe(user_id, queue)


@pytest.mark.asyncio
async def test_http_isolation_user_b_cannot_see_user_a(
    test_session: AsyncSession, user_a: UserModel, user_b: UserModel
):
    service = ActivityService(test_session)
    await service.record(
        user_id=user_a.id,
        action="LOGIN",
        message="A only",
        status="success",
    )
    now = datetime.now(UTC)
    domain_b = User(
        id=user_b.id,
        username=user_b.username,
        email=user_b.email,
        password_hash=user_b.password_hash,
        role=UserRole.ADMIN,
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    async def override_b() -> User:
        return domain_b

    async def override_db():
        yield test_session

    app.dependency_overrides[get_current_active_user] = override_b
    app.dependency_overrides[get_db_session] = override_db
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/activity/recent")
            assert resp.status_code == 200
            items = resp.json()["items"]
            assert all(i["user_id"] == user_b.id for i in items)
            assert not any(i["message"] == "A only" for i in items)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_publish_threadsafe_from_worker_thread(user_a: UserModel):
    import concurrent.futures

    user_id = user_a.id
    loop = asyncio.get_running_loop()
    activity_hub.bind_loop(loop)
    queue = await activity_hub.subscribe(user_id)
    try:

        def _worker() -> None:
            activity_hub.publish_threadsafe(
                user_id, {"id": "thread-evt", "message": "from-thread"}
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            await loop.run_in_executor(pool, _worker)

        event = await asyncio.wait_for(queue.get(), timeout=2.0)
        assert event["id"] == "thread-evt"
        assert event["message"] == "from-thread"
    finally:
        await activity_hub.unsubscribe(user_id, queue)


@pytest.mark.asyncio
async def test_events_after_replays_without_duplicate(
    test_session: AsyncSession, user_a: UserModel
):
    user_id = user_a.id
    service = ActivityService(test_session)
    first = await service.record(
        user_id=user_id,
        action="LOGIN",
        message="first",
        status="success",
    )
    second = await service.record(
        user_id=user_id,
        action="LOGOUT",
        message="second",
        status="info",
    )
    assert first is not None and second is not None
    missed = await service.events_after(user_id, first.id, limit=50)
    ids = [e.id for e in missed]
    assert second.id in ids
    assert first.id not in ids
    assert len(ids) == len(set(ids))


@pytest.mark.asyncio
async def test_stream_subscribe_publish_and_after_id_replay(
    test_session: AsyncSession, user_a: UserModel
):
    """Mirrors SSE path: replay after_id then live hub publish without duplicates."""
    user_id = user_a.id
    service = ActivityService(test_session)
    first = await service.record(
        user_id=user_id,
        action="LOGIN",
        message="cursor",
        status="success",
    )
    second = await service.record(
        user_id=user_id,
        action="SETTINGS_UPDATED",
        message="missed while offline",
        status="info",
    )
    assert first is not None and second is not None

    queue = await activity_hub.subscribe(user_id)
    seen: set[str] = set()
    delivered: list[str] = []
    try:
        missed = await service.events_after(user_id, first.id, limit=50)
        for entry in missed:
            if entry.id in seen:
                continue
            seen.add(entry.id)
            delivered.append(entry.id)

        live = await service.record(
            user_id=user_id,
            action="SETTINGS_UPDATED",
            message="stream live",
            status="info",
        )
        assert live is not None
        event = await asyncio.wait_for(queue.get(), timeout=2.0)
        event_id = str(event.get("id") or "")
        if event_id and event_id not in seen:
            seen.add(event_id)
            delivered.append(event_id)

        assert second.id in delivered
        assert first.id not in delivered
        assert live.id in delivered
        assert len(delivered) == len(set(delivered))
        assert event.get("message") == "stream live"
    finally:
        await activity_hub.unsubscribe(user_id, queue)
