"""Tests for default admin user seeding."""

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security.password import password_hasher
from app.domain.entities.user import UserRole
from app.features.auth.repository import UserRepository
from app.infrastructure.database.models import UserModel
from app.infrastructure.seed.seed_users import seed_admin_user


@pytest.fixture
def admin_seed_env(monkeypatch):
    monkeypatch.setattr(settings, "default_admin_username", "seedadmin")
    monkeypatch.setattr(settings, "default_admin_password", "SeedPass123!")


@pytest.fixture
def clear_admin_seed_env(monkeypatch):
    monkeypatch.setattr(settings, "default_admin_username", None)
    monkeypatch.setattr(settings, "default_admin_password", None)


@pytest.mark.asyncio
async def test_skips_when_env_missing(test_session: AsyncSession, clear_admin_seed_env):
    await seed_admin_user(test_session)

    result = await test_session.execute(select(func.count()).select_from(UserModel))
    assert result.scalar_one() == 0


@pytest.mark.asyncio
async def test_creates_admin_when_env_set(test_session: AsyncSession, admin_seed_env):
    await seed_admin_user(test_session)

    user_repo = UserRepository(test_session)
    user = await user_repo.get_by_username("seedadmin")
    assert user is not None
    assert user.role == UserRole.ADMIN
    assert user.email == "seedadmin@railway.local"
    assert password_hasher.verify("SeedPass123!", user.password_hash)


@pytest.mark.asyncio
async def test_idempotent_no_duplicate(test_session: AsyncSession, admin_seed_env):
    await seed_admin_user(test_session)
    await seed_admin_user(test_session)

    result = await test_session.execute(
        select(func.count()).select_from(UserModel).where(UserModel.username == "seedadmin")
    )
    assert result.scalar_one() == 1


@pytest.mark.asyncio
async def test_does_not_overwrite_existing(test_session: AsyncSession, admin_seed_env):
    user_repo = UserRepository(test_session)
    await user_repo.create(
        user_id=str(uuid.uuid4()),
        username="seedadmin",
        email="seedadmin@railway.local",
        password_hash=password_hasher.hash("OriginalPass123!"),
        role=UserRole.ADMIN,
    )

    await seed_admin_user(test_session)

    user = await user_repo.get_by_username("seedadmin")
    assert user is not None
    assert password_hasher.verify("OriginalPass123!", user.password_hash)
    assert not password_hasher.verify("SeedPass123!", user.password_hash)
