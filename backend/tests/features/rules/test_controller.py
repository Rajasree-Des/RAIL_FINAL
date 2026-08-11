"""Integration tests for rules API."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.password import password_hasher
from app.infrastructure.database.models import ConfigurableRuleModel, UserModel


@pytest.fixture
async def admin_user(test_session: AsyncSession) -> UserModel:
    user = UserModel(
        id="rules-admin-id",
        username="rulesadmin",
        email="rulesadmin@example.com",
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
        json={"username": "rulesadmin", "password": "TestPass123"},
    )
    assert response.status_code == 200
    csrf = response.json().get("csrf_token")
    headers = {"X-CSRF-Token": csrf} if csrf else {}
    return client, headers, admin_user


@pytest.mark.asyncio
async def test_create_rule_requires_csrf(admin_client):
    client, _headers, _admin = admin_client
    response = await client.post(
        "/api/v1/rules/",
        json={
            "name": "Highlight row",
            "category": "highlight",
            "rule_type": "cell_style",
            "config": {},
        },
    )
    assert response.status_code == 400
    assert "CSRF" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_rule_sets_user_id(admin_client, test_session):
    client, headers, admin = admin_client
    response = await client.post(
        "/api/v1/rules/",
        json={
            "name": "Hide column",
            "category": "column",
            "rule_type": "hide",
            "config": {"columns": ["col_a"]},
        },
        headers=headers,
    )
    assert response.status_code == 200
    rule_id = response.json()["id"]

    result = await test_session.execute(
        select(ConfigurableRuleModel).where(ConfigurableRuleModel.id == rule_id)
    )
    rule = result.scalar_one()
    assert rule.created_by == admin.id
    assert rule.updated_by == admin.id
