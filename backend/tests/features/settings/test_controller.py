"""Integration tests for settings API."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.password import password_hasher
from app.features.settings.cache import settings_cache
from app.features.settings.seeds.default_definitions import DEFAULT_SETTING_DEFINITIONS
from app.infrastructure.database.models import AppSettingDefinitionModel, UserModel


@pytest.fixture(autouse=True)
async def clear_settings_cache():
    await settings_cache.invalidate_all()
    yield
    await settings_cache.invalidate_all()


@pytest.fixture
async def admin_user(test_session: AsyncSession) -> UserModel:
    user = UserModel(
        id="admin-settings-id",
        username="settingsadmin",
        email="settingsadmin@example.com",
        password_hash=password_hasher.hash("TestPass123"),
        role="admin",
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    return user


@pytest.fixture
async def admin_client(client: AsyncClient, admin_user: UserModel) -> tuple[AsyncClient, dict]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "settingsadmin", "password": "TestPass123"},
    )
    assert response.status_code == 200
    csrf = response.json().get("csrf_token")
    headers = {"X-CSRF-Token": csrf} if csrf else {}
    return client, headers


@pytest.fixture
async def seeded_settings(test_session: AsyncSession) -> None:
    for definition in DEFAULT_SETTING_DEFINITIONS:
        test_session.add(AppSettingDefinitionModel(**definition))
    await test_session.commit()


@pytest.mark.asyncio
async def test_get_settings_requires_auth(client):
    response = await client.get("/api/v1/settings")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_settings_as_admin(admin_client, seeded_settings):
    client, _ = admin_client
    response = await client.get("/api/v1/settings")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == len(DEFAULT_SETTING_DEFINITIONS)
    assert {c["slug"] for c in data["categories"]} == {
        "general",
        "notifications",
        "account",
    }


@pytest.mark.asyncio
async def test_update_setting(admin_client, seeded_settings):
    client, headers = admin_client
    response = await client.put(
        "/api/v1/settings",
        json={
            "settings": [
                {"category": "general", "key": "default_page_size", "value": 100},
            ],
        },
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["updated"] == 1

    get_response = await client.get("/api/v1/settings?category=general")
    general_settings = get_response.json()["categories"][0]["settings"]
    size_setting = next(s for s in general_settings if s["key"] == "default_page_size")
    assert size_setting["value"] == 100
    assert size_setting["is_modified"] is True


@pytest.mark.asyncio
async def test_export_import_settings(admin_client, seeded_settings):
    client, headers = admin_client

    export_response = await client.get("/api/v1/settings/export")
    assert export_response.status_code == 200
    payload = export_response.json()
    assert "settings" in payload
    assert "general.organization_name" in payload["settings"]

    import_response = await client.post(
        "/api/v1/settings/import",
        json={
            "settings": {"general.organization_name": "Custom Railway"},
            "merge": True,
        },
        headers=headers,
    )
    assert import_response.status_code == 200
    assert import_response.json()["imported"] >= 1


@pytest.mark.asyncio
async def test_display_settings_requires_auth(client, seeded_settings):
    response = await client.get("/api/v1/settings/display")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_display_settings_for_viewer(authenticated_client, seeded_settings):
    """Any active user (even viewer) can read resolved display settings."""
    response = await authenticated_client.get("/api/v1/settings/display")
    assert response.status_code == 200
    data = response.json()
    assert data["organization_name"] == "South Central Railway"
    assert data["timezone"] == "Asia/Kolkata"
    assert data["date_format"] == "DD/MM/YYYY"
    assert data["time_format"] == "12h"
    assert data["default_page_size"] == 50
    assert data["enable_notifications"] is True
    assert "desktop_notifications" not in data


@pytest.mark.asyncio
async def test_notification_definitions_count(seeded_settings, test_session: AsyncSession):
    from sqlalchemy import select

    definitions = (
        await test_session.execute(
            select(AppSettingDefinitionModel).where(
                AppSettingDefinitionModel.category == "notifications"
            )
        )
    ).scalars().all()
    assert len(definitions) == 4
    assert {d.key for d in definitions} == {
        "enable_notifications",
        "notify_on_completion",
        "notify_on_failure",
        "notification_sound",
    }


@pytest.mark.asyncio
async def test_display_settings_reflect_overrides(admin_client, seeded_settings):
    client, headers = admin_client
    update = await client.put(
        "/api/v1/settings",
        json={
            "settings": [
                {"category": "general", "key": "organization_name", "value": "Test Rail Org"},
                {"category": "general", "key": "time_format", "value": "24h"},
            ],
        },
        headers=headers,
    )
    assert update.status_code == 200

    response = await client.get("/api/v1/settings/display")
    assert response.status_code == 200
    data = response.json()
    assert data["organization_name"] == "Test Rail Org"
    assert data["time_format"] == "24h"
