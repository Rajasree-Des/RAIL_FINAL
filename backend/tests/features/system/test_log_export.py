"""Tests for administrative log PDF export."""

from __future__ import annotations

import json
import re
import zlib
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

import app.features.system.service as system_service
from app.core.security.password import password_hasher
from app.features.system.log_export import collect_admin_events
from app.infrastructure.database.models import (
    AutomationLogModel,
    AutomationProfileModel,
    AutomationRunModel,
    UserActivityModel,
    UserModel,
)


def _pdf_text(content: bytes) -> str:
    """Best-effort text extraction for ReportLab PDF assertions."""
    decoded = content.decode("latin-1", errors="ignore")
    if "Administrative" in decoded or "RailMadad" in decoded:
        return decoded
    parts: list[str] = [decoded]
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", content, re.DOTALL):
        data = match.group(1)
        try:
            parts.append(zlib.decompress(data).decode("latin-1", errors="ignore"))
        except zlib.error:
            parts.append(data.decode("latin-1", errors="ignore"))
    return "".join(parts)


@pytest.fixture(autouse=True)
def cdp_down(monkeypatch):
    class _FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            raise ConnectionError("CDP not running")

    monkeypatch.setattr(system_service.httpx, "AsyncClient", _FailingClient)


@pytest.fixture
async def admin_user(test_session: AsyncSession) -> UserModel:
    user = UserModel(
        id="admin-export-id",
        username="exportadmin",
        email="exportadmin@example.com",
        password_hash=password_hasher.hash("TestPass123"),
        role="admin",
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    return user


@pytest.fixture
async def admin_client(client: AsyncClient, admin_user: UserModel) -> AsyncClient:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "exportadmin", "password": "TestPass123"},
    )
    assert response.status_code == 200
    return client


@pytest.fixture
async def seeded_logs(
    test_session: AsyncSession,
    admin_user: UserModel,
) -> tuple[str, str]:
    older = datetime.now(UTC) - timedelta(hours=2)
    newer = datetime.now(UTC) - timedelta(minutes=5)

    test_session.add(
        UserActivityModel(
            id="activity-older-001",
            user_id=admin_user.id,
            action="LOGIN",
            message="Older activity login event",
            status="info",
            created_at=older,
        )
    )
    test_session.add(
        UserActivityModel(
            id="activity-newer-002",
            user_id=admin_user.id,
            action="CACHE_CLEARED",
            message="Newer cache cleared event",
            status="success",
            report_slug=None,
            metadata_json=json.dumps(
                {
                    "password": "secret-should-not-export",
                    "stage": "maintenance",
                }
            ),
            created_at=newer,
        )
    )

    profile = AutomationProfileModel(
        id="profile-export-1",
        name="Export Test",
        slug="report1",
        portal_url="https://example.test",
        username_encrypted="enc",
        password_encrypted="enc",
    )
    test_session.add(profile)
    await test_session.flush()

    run = AutomationRunModel(
        id="run-export-failed-1",
        profile_id=profile.id,
        status="failed",
        error_message="Portal timeout during extraction",
        failure_count=1,
        completed_at=newer - timedelta(minutes=1),
        created_at=newer - timedelta(minutes=30),
    )
    test_session.add(run)
    await test_session.flush()

    test_session.add(
        AutomationLogModel(
            id="log-export-001",
            run_id=run.id,
            level="error",
            message="Automation step failed safely",
            created_at=newer - timedelta(minutes=2),
        )
    )
    await test_session.commit()
    return "Newer cache cleared event", "Older activity login event"


@pytest.mark.asyncio
async def test_export_logs_requires_auth(client):
    response = await client.get("/api/v1/system/export-logs")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_export_logs_forbidden_for_viewer(authenticated_client):
    response = await authenticated_client.get("/api/v1/system/export-logs")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_export_logs_returns_pdf(admin_client, seeded_logs, test_session):
    response = await admin_client.get("/api/v1/system/export-logs")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert "RailMadad_Administrative_Logs_" in response.headers.get(
        "content-disposition", ""
    )

    body = response.content
    assert body.startswith(b"%PDF")
    assert len(body) > 2000
    text = _pdf_text(body)
    assert "Administrative Events" in text
    assert "secret-should-not-export" not in text

    events = await collect_admin_events(test_session)
    messages = [e.message for e in events]
    newer_msg, older_msg = seeded_logs
    assert newer_msg in messages
    assert older_msg in messages
    assert messages.index(newer_msg) < messages.index(older_msg)


@pytest.mark.asyncio
async def test_export_logs_missing_fields_show_na(
    admin_client, test_session, admin_user,
):
    test_session.add(
        UserActivityModel(
            id="activity-minimal-003",
            user_id=admin_user.id,
            action="SYSTEM_CHECK",
            message="Minimal event without optional fields",
            status="info",
            created_at=datetime.now(UTC),
        )
    )
    await test_session.commit()

    events = await collect_admin_events(test_session)
    assert any(e.message == "Minimal event without optional fields" for e in events)
    assert any(e.task_category == "N/A" or e.task_category for e in events)

    response = await admin_client.get("/api/v1/system/export-logs")
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")


def test_missing_fields_render_na():
    from app.features.system.log_export import _event_id, _na

    assert _na(None) == "N/A"
    assert _na("") == "N/A"
    assert _event_id(None) == "N/A"


@pytest.mark.asyncio
async def test_collect_admin_events_order(test_session, admin_user, seeded_logs):
    events = await collect_admin_events(test_session)
    messages = [e.message for e in events]
    newer_msg, older_msg = seeded_logs
    assert messages.index(newer_msg) < messages.index(older_msg)
