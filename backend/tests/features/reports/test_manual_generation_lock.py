"""Tests for manual generation lock conflicts."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.automation.automation_lock import reset_automation_lock_for_tests, try_acquire_automation_lock
from app.domain.entities.user import User, UserRole
from app.features.auth.dependencies import require_officer_or_admin, validate_csrf_token
from app.main import app


@pytest.fixture(autouse=True)
def _clear_lock():
    reset_automation_lock_for_tests()
    yield
    reset_automation_lock_for_tests()


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
async def test_generate_returns_409_when_automation_lock_held(api_client: AsyncClient):
    assert try_acquire_automation_lock("active-run", "division") is True

    response = await api_client.post(
        "/api/v1/reports/report1/generate",
        json={
            "date_from": "2026-07-25",
            "date_to": "2026-07-26",
            "selected_column_ids": ["report1.source_a.organisation"],
            "column_order": ["report1.source_a.organisation"],
            "configuration_source": "manual_snapshot",
            "requested_formats": ["xlsx", "pdf"],
            "force_fresh_extraction": True,
        },
    )

    assert response.status_code == 409
    payload = response.json()
    assert payload["detail"]["code"] == "AUTOMATION_ALREADY_RUNNING"
    assert payload["detail"]["active_run_id"] == "active-run"


@pytest.mark.asyncio
async def test_get_handler_returns_fresh_instances():
    from app.automation.handlers.registry import get_handler

    first = get_handler("report1")
    second = get_handler("report1")
    assert first is not second
    assert first.__class__ is second.__class__
