"""Automation API tests."""

import json

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.encryption import encrypt_secret
from app.core.security.password import password_hasher
from app.infrastructure.database.models import AutomationProfileModel, UserModel


@pytest.fixture
async def admin_user(test_session: AsyncSession) -> UserModel:
    user = UserModel(
        id="auto-admin-id",
        username="autoadmin",
        email="auto@example.com",
        password_hash=password_hasher.hash("TestPass123"),
        role="admin",
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    return user


@pytest.fixture
async def admin_client(
    client: AsyncClient, admin_user: UserModel
) -> tuple[AsyncClient, dict[str, str]]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "autoadmin", "password": "TestPass123"},
    )
    assert response.status_code == 200
    csrf = response.json().get("csrf_token")
    headers = {"X-CSRF-Token": csrf} if csrf else {}
    return client, headers


@pytest.fixture
async def automation_profile(test_session: AsyncSession) -> AutomationProfileModel:
    profile = AutomationProfileModel(
        name="Test Profile",
        slug="test-profile",
        portal_url="https://example.com",
        username_encrypted=encrypt_secret("user"),
        password_encrypted=encrypt_secret("pass"),
        report_sequence_json=json.dumps([{"name": "Test", "report_path": "/r"}]),
        is_enabled=True,
    )
    test_session.add(profile)
    await test_session.commit()
    await test_session.refresh(profile)
    return profile


@pytest.mark.asyncio
async def test_automation_status_requires_admin(client):
    response = await client.get("/api/v1/automation/status")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_status_as_admin(admin_client, automation_profile):
    client, _ = admin_client
    response = await client.get("/api/v1/automation/status")
    assert response.status_code == 200
    data = response.json()
    assert "success_rate" in data
    assert data["total_runs"] == 0


@pytest.mark.asyncio
async def test_list_profiles(admin_client, automation_profile):
    client, _ = admin_client
    response = await client.get("/api/v1/automation/profiles")
    assert response.status_code == 200
    assert response.json()["total"] >= 1


@pytest.mark.asyncio
async def test_callback_updates_run(admin_client, automation_profile, test_session):
    from app.infrastructure.database.models import AutomationRunModel

    client, headers = admin_client
    run = AutomationRunModel(profile_id=automation_profile.id, status="running")
    test_session.add(run)
    await test_session.commit()
    await test_session.refresh(run)

    service_headers = {
        "Authorization": "Bearer dev-automation-service-token-change-in-production",
    }
    response = await client.post(
        "/api/v1/automation/callback",
        json={
            "run_id": run.id,
            "status": "completed",
            "success_count": 2,
            "failure_count": 0,
            "log_message": "Done",
        },
        headers=service_headers,
    )
    assert response.status_code == 200

    status = await client.get("/api/v1/automation/status")
    assert status.json()["last_run"]["status"] == "completed"
