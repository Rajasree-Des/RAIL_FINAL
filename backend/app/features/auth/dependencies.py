from fastapi import Cookie, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, AuthorizationError, ValidationError
from app.core.request_utils import get_client_ip
from app.core.security.csrf import csrf_protection
from app.core.security.jwt import jwt_handler
from app.domain.entities.user import User, UserRole
from app.features.auth.repository import RefreshTokenRepository, UserRepository
from app.features.auth.service import AuthService
from app.infrastructure.database.session import get_db_session


def get_refresh_token_cookie(request: Request) -> str | None:
    """Extract refresh token from cookies - proper dependency for FastAPI injection."""
    return request.cookies.get("refresh_token")


def get_csrf_session_cookie(request: Request) -> str | None:
    """Extract CSRF session ID from cookies."""
    return request.cookies.get("csrf_session")


def validate_csrf_token(
    request: Request,
    x_csrf_token: str | None = Header(None),
    csrf_session: str | None = Depends(get_csrf_session_cookie),
) -> None:
    """Validate CSRF token for state-changing requests.

    Exemptions:
    - GET, HEAD, OPTIONS requests (safe methods)
    - /auth/login, /auth/register, /auth/refresh (stateless or pre-auth)
    """
    safe_methods = {"GET", "HEAD", "OPTIONS"}
    if request.method in safe_methods:
        return

    exempt_paths = {
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/refresh",
        "/api/v1/auth/csrf",
        "/api/v1/automation/callback",
    }
    if request.url.path in exempt_paths:
        return

    if not x_csrf_token:
        raise ValidationError("CSRF token required")

    if not csrf_session:
        raise ValidationError("CSRF session not found")

    csrf_protection.validate_or_raise(x_csrf_token, csrf_session)


def get_user_repository(
    session: AsyncSession = Depends(get_db_session),
) -> UserRepository:
    return UserRepository(session)


def get_token_repository(
    session: AsyncSession = Depends(get_db_session),
) -> RefreshTokenRepository:
    return RefreshTokenRepository(session)


def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repository),
    token_repo: RefreshTokenRepository = Depends(get_token_repository),
) -> AuthService:
    return AuthService(user_repo, token_repo)


def get_user_agent(user_agent: str | None = Header(None)) -> str | None:
    return user_agent


async def get_current_user(
    request: Request,
    authorization: str | None = Header(None),
    access_token: str | None = Cookie(None),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    token = None

    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    elif access_token:
        token = access_token

    if not token:
        raise AuthenticationError("Authentication required")

    try:
        user_id = jwt_handler.get_subject(token, token_type="access")
    except Exception as e:
        raise AuthenticationError(str(e)) from e

    return await auth_service.get_current_user(user_id)


async def get_current_active_user(
    user: User = Depends(get_current_user),
) -> User:
    if not user.is_active:
        raise AuthorizationError("Account is disabled")
    return user


def require_role(*roles: UserRole):
    async def role_checker(user: User = Depends(get_current_active_user)) -> User:
        if user.role not in roles:
            raise AuthorizationError(f"Required role: {', '.join(r.value for r in roles)}")
        return user
    return role_checker


async def require_admin(user: User = Depends(get_current_active_user)) -> User:
    if not user.can_access_admin():
        raise AuthorizationError("Admin access required")
    return user


async def require_officer_or_admin(user: User = Depends(get_current_active_user)) -> User:
    if not user.can_generate_reports():
        raise AuthorizationError("Officer or admin access required")
    return user
