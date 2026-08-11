import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.password import password_hasher
from app.infrastructure.database.models import UserModel


@pytest.fixture
async def test_user(test_session: AsyncSession):
    user = UserModel(
        id="test-user-id",
        username="testuser",
        email="test@example.com",
        password_hash=password_hasher.hash("TestPass123"),
        role="officer",
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    return user


async def test_login_success(client: AsyncClient, test_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "TestPass123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "access_token" in response.cookies


async def test_login_invalid_password(client: AsyncClient, test_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "WrongPassword123"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "AUTHENTICATION_ERROR"


async def test_login_user_not_found(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "nonexistent", "password": "TestPass123"},
    )
    assert response.status_code == 401


async def test_register_success(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "newuser",
            "email": "new@example.com",
            "password": "NewPass123",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "new@example.com"
    assert data["role"] == "viewer"


async def test_register_duplicate_username(client: AsyncClient, test_user):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "email": "another@example.com",
            "password": "NewPass123",
        },
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


async def test_register_weak_password(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "newuser",
            "email": "new@example.com",
            "password": "weakpass",
        },
    )
    assert response.status_code == 422


async def test_get_current_user_authenticated(client: AsyncClient, test_user):
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "TestPass123"},
    )
    token = login_response.json()["access_token"]

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["username"] == "testuser"


async def test_get_current_user_unauthenticated(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_login_trims_username_whitespace(client: AsyncClient, test_user):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "  testuser  ", "password": "TestPass123"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_registered_user_can_login_immediately(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "freshuser",
            "email": "freshuser@example.com",
            "password": "FreshPass123",
        },
    )
    assert response.status_code == 201

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": "freshuser", "password": "FreshPass123"},
    )
    assert login_response.status_code == 200


async def test_refresh_after_login(client: AsyncClient, test_user):
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "TestPass123"},
    )
    assert login_response.status_code == 200

    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        cookies=login_response.cookies,
    )
    assert refresh_response.status_code == 200
    assert "access_token" in refresh_response.json()


async def test_issue_csrf_requires_authentication(client: AsyncClient):
    response = await client.post("/api/v1/auth/csrf")
    assert response.status_code == 401


async def test_issue_csrf_returns_token(client: AsyncClient, test_user):
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "TestPass123"},
    )
    assert login_response.status_code == 200

    response = await client.post(
        "/api/v1/auth/csrf",
        cookies=login_response.cookies,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["csrf_token"]
    assert "csrf_session" in response.cookies
