import os
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security.password import password_hasher
from app.infrastructure.database.models import Base, UserModel
from app.infrastructure.database.session import get_db_session
from app.main import app

os.environ["JWT_SECRET_KEY"] = "test-secret-key-at-least-32-characters-long"
os.environ["CSRF_SECRET_KEY"] = "test-csrf-secret-key"

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session


@pytest.fixture
async def client(test_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db_session():
        yield test_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(test_session: AsyncSession) -> UserModel:
    """Create a test user for authentication tests."""
    user = UserModel(
        id="test-user-id",
        username="testuser",
        email="test@example.com",
        password_hash=password_hasher.hash("TestPass123"),
        role="viewer",
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    return user


@pytest.fixture
async def authenticated_client(
    client: AsyncClient, test_user: UserModel
) -> AsyncGenerator[AsyncClient, None]:
    """Create an authenticated client with access token cookie."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "TestPass123"},
    )
    assert response.status_code == 200
    yield client
