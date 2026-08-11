from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import AuthenticationError, ValidationError
from app.core.security.password import password_hasher
from app.domain.entities.user import User, UserRole
from app.features.auth.service import AuthService


def create_mock_user(
    user_id: str = "test-id",
    username: str = "testuser",
    email: str = "test@example.com",
    password: str = "TestPass123",
    role: UserRole = UserRole.OFFICER,
    is_active: bool = True,
) -> User:
    return User(
        id=user_id,
        username=username,
        email=email,
        password_hash=password_hasher.hash(password),
        role=role,
        is_active=is_active,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_user_repo():
    return AsyncMock()


@pytest.fixture
def mock_token_repo():
    return AsyncMock()


@pytest.fixture
def auth_service(mock_user_repo, mock_token_repo):
    return AuthService(mock_user_repo, mock_token_repo)


async def test_login_success(auth_service, mock_user_repo, mock_token_repo):
    mock_user = create_mock_user()
    mock_user_repo.get_by_username.return_value = mock_user
    mock_user_repo.update_last_login.return_value = None
    mock_token_repo.create.return_value = None

    token_response, refresh_token, user = await auth_service.login(
        username="testuser",
        password="TestPass123",
    )

    assert token_response.access_token is not None
    assert refresh_token is not None
    assert user.username == "testuser"
    mock_user_repo.get_by_username.assert_called_once_with("testuser")


async def test_login_invalid_password(auth_service, mock_user_repo):
    mock_user = create_mock_user()
    mock_user_repo.get_by_username.return_value = mock_user

    with pytest.raises(AuthenticationError):
        await auth_service.login(
            username="testuser",
            password="WrongPassword",
        )


async def test_login_user_not_found(auth_service, mock_user_repo):
    mock_user_repo.get_by_username.return_value = None

    with pytest.raises(AuthenticationError):
        await auth_service.login(
            username="nonexistent",
            password="TestPass123",
        )


async def test_login_trims_username_before_lookup(
    auth_service, mock_user_repo, mock_token_repo
):
    mock_user = create_mock_user()
    mock_user_repo.get_by_username.return_value = mock_user
    mock_user_repo.update_last_login.return_value = None
    mock_token_repo.create.return_value = None

    await auth_service.login(
        username="  testuser  ",
        password="TestPass123",
    )

    mock_user_repo.get_by_username.assert_called_once_with("testuser")


async def test_login_inactive_user(auth_service, mock_user_repo):
    mock_user = create_mock_user(is_active=False)
    mock_user_repo.get_by_username.return_value = mock_user

    with pytest.raises(AuthenticationError) as exc_info:
        await auth_service.login(
            username="testuser",
            password="TestPass123",
        )

    assert "disabled" in str(exc_info.value.message)


async def test_register_success(auth_service, mock_user_repo):
    mock_user_repo.get_by_username.return_value = None
    mock_user_repo.get_by_email.return_value = None
    mock_user_repo.create.return_value = create_mock_user(role=UserRole.VIEWER)

    result = await auth_service.register(
        username="newuser",
        email="new@example.com",
        password="NewPass123",
    )

    assert result.role == "viewer"
    mock_user_repo.create.assert_called_once()


async def test_register_duplicate_username(auth_service, mock_user_repo):
    mock_user_repo.get_by_username.return_value = create_mock_user()

    with pytest.raises(ValidationError) as exc_info:
        await auth_service.register(
            username="testuser",
            email="new@example.com",
            password="NewPass123",
        )

    assert exc_info.value.field == "username"


async def test_change_password_success(auth_service, mock_user_repo, mock_token_repo):
    mock_user = create_mock_user()
    mock_user_repo.get_by_id.return_value = mock_user
    mock_user_repo.update_password.return_value = None
    mock_token_repo.revoke_all_for_user.return_value = None

    await auth_service.change_password(
        user_id="test-id",
        current_password="TestPass123",
        new_password="NewPass456",
    )

    mock_user_repo.update_password.assert_called_once()
    mock_token_repo.revoke_all_for_user.assert_called_once_with("test-id")


async def test_change_password_wrong_current(auth_service, mock_user_repo):
    mock_user = create_mock_user()
    mock_user_repo.get_by_id.return_value = mock_user

    with pytest.raises(AuthenticationError):
        await auth_service.change_password(
            user_id="test-id",
            current_password="WrongPassword",
            new_password="NewPass456",
        )
