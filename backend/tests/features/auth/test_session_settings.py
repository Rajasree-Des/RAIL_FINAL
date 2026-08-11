"""Logout-all and settings-driven session timeout."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.password import password_hasher
from app.features.settings.cache import CACHE_KEY_ALL, settings_cache
from app.infrastructure.database.models import RefreshTokenModel, UserModel


@pytest.fixture(autouse=True)
async def clear_settings_cache():
    await settings_cache.invalidate_all()
    yield
    await settings_cache.invalidate_all()


@pytest.fixture
async def session_user(test_session: AsyncSession) -> UserModel:
    user = UserModel(
        id="session-user-id",
        username="sessionuser",
        email="sessionuser@example.com",
        password_hash=password_hasher.hash("TestPass123"),
        role="officer",
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    return user


async def _login(client: AsyncClient) -> dict:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "sessionuser", "password": "TestPass123"},
    )
    assert response.status_code == 200
    return response.json()


def _cache_payload(session_timeout: str) -> dict:
    return {
        "version": "1.0",
        "total": 1,
        "categories": [
            {
                "slug": "account",
                "label": "Account",
                "description": None,
                "settings": [
                    {
                        "id": "x",
                        "category": "account",
                        "key": "session_timeout",
                        "label": "Session Timeout",
                        "description": None,
                        "value_type": "enum",
                        "value": session_timeout,
                        "default_value": "30m",
                        "validation": None,
                        "options": None,
                        "sort_order": 1,
                        "is_editable": True,
                        "is_modified": session_timeout != "30m",
                    }
                ],
            }
        ],
    }


@pytest.mark.asyncio
async def test_default_session_timeout_is_30_minutes(
    client: AsyncClient, session_user
):
    data = await _login(client)
    assert data["expires_in"] == 30 * 60


@pytest.mark.asyncio
async def test_session_timeout_setting_changes_token_expiry(
    client: AsyncClient, session_user
):
    await settings_cache.set(CACHE_KEY_ALL, _cache_payload("1h"))
    data = await _login(client)
    assert data["expires_in"] == 60 * 60


@pytest.mark.asyncio
async def test_session_timeout_never_maps_to_30_days(
    client: AsyncClient, session_user
):
    await settings_cache.set(CACHE_KEY_ALL, _cache_payload("never"))
    data = await _login(client)
    assert data["expires_in"] == 30 * 24 * 60 * 60


@pytest.mark.asyncio
async def test_logout_all_revokes_refresh_tokens(
    client: AsyncClient, session_user, test_session: AsyncSession
):
    await _login(client)

    # A second session for the same user (rotates the CSRF session cookie,
    # so the second login's token is the valid one)
    second = await _login(client)
    csrf = second.get("csrf_token")
    headers = {"X-CSRF-Token": csrf} if csrf else {}

    active_before = (
        (
            await test_session.execute(
                select(RefreshTokenModel).where(
                    RefreshTokenModel.user_id == session_user.id,
                    RefreshTokenModel.revoked_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(active_before) >= 2

    response = await client.post("/api/v1/auth/logout-all", headers=headers)
    assert response.status_code == 204

    active_after = (
        (
            await test_session.execute(
                select(RefreshTokenModel).where(
                    RefreshTokenModel.user_id == session_user.id,
                    RefreshTokenModel.revoked_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    assert active_after == []

    # The refresh token cookie can no longer be used
    refresh = await client.post("/api/v1/auth/refresh")
    assert refresh.status_code == 401
