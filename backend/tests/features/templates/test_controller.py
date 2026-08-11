"""Integration tests for templates API."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.password import password_hasher
from app.infrastructure.database.models import UserModel


@pytest.fixture
async def admin_user(test_session: AsyncSession) -> UserModel:
    user = UserModel(
        id="templates-admin-id",
        username="templatesadmin",
        email="templatesadmin@example.com",
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
) -> tuple[AsyncClient, dict[str, str], UserModel]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "templatesadmin", "password": "TestPass123"},
    )
    assert response.status_code == 200
    csrf = response.json().get("csrf_token")
    headers = {"X-CSRF-Token": csrf} if csrf else {}
    return client, headers, admin_user


@pytest.mark.asyncio
async def test_create_template_requires_csrf(admin_client):
    client, _headers, _admin = admin_client
    response = await client.post(
        "/api/v1/admin/templates",
        json={"name": "Test Template"},
    )
    assert response.status_code == 400
    assert "CSRF" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_template_with_csrf(admin_client):
    client, headers, admin = admin_client
    response = await client.post(
        "/api/v1/admin/templates",
        json={"name": "Test Template"},
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Template"
    assert data["created_by"] == admin.id
