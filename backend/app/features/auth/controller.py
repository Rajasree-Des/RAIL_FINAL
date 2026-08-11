import logging

from fastapi import APIRouter, Depends, Response

from app.core.config import settings
from app.core.security.csrf import csrf_protection
from app.core.security.rate_limit import rate_limit_login, rate_limit_password, rate_limit_register
from app.domain.entities.user import User
from app.features.auth.dependencies import (
    get_auth_service,
    get_client_ip,
    get_current_active_user,
    get_refresh_token_cookie,
    get_user_agent,
    validate_csrf_token,
)
from app.features.auth.schemas import (
    CsrfTokenResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    PasswordChangeRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.features.auth.service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


def _set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    csrf_session: str | None = None,
    remember_me: bool = False,
    access_max_age: int | None = None,
) -> None:
    refresh_expire_days = (
        settings.jwt_refresh_token_expire_days_remember
        if remember_me
        else settings.jwt_refresh_token_expire_days
    )

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=settings.cookie_httponly,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=access_max_age or settings.jwt_access_token_expire_minutes * 60,
        domain=settings.cookie_domain,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=settings.cookie_httponly,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=refresh_expire_days * 24 * 60 * 60,
        path="/api/v1/auth",
        domain=settings.cookie_domain,
    )
    if csrf_session:
        response.set_cookie(
            key="csrf_session",
            value=csrf_session,
            httponly=True,
            secure=settings.cookie_secure,
            samesite=settings.cookie_samesite,
            max_age=refresh_expire_days * 24 * 60 * 60,
            domain=settings.cookie_domain,
        )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(key="access_token", domain=settings.cookie_domain)
    response.delete_cookie(key="refresh_token", path="/api/v1/auth", domain=settings.cookie_domain)
    response.delete_cookie(key="csrf_session", domain=settings.cookie_domain)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    response: Response,
    service: AuthService = Depends(get_auth_service),
    ip_address: str | None = Depends(get_client_ip),
    user_agent: str | None = Depends(get_user_agent),
    _rate_limit: None = Depends(rate_limit_login),
) -> TokenResponse:
    token_response, refresh_token, _ = await service.login(
        username=body.username,
        password=body.password,
        ip_address=ip_address,
        user_agent=user_agent,
        remember_me=body.remember_me,
    )

    csrf_session, csrf_token = csrf_protection.generate_session_and_token()
    _set_auth_cookies(
        response,
        token_response.access_token,
        refresh_token,
        csrf_session,
        body.remember_me,
        access_max_age=token_response.expires_in,
    )

    token_response.csrf_token = csrf_token
    return token_response


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    body: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
    ip_address: str | None = Depends(get_client_ip),
    _rate_limit: None = Depends(rate_limit_register),
) -> UserResponse:
    return await service.register(
        username=body.username,
        email=body.email,
        password=body.password,
        ip_address=ip_address,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    response: Response,
    service: AuthService = Depends(get_auth_service),
    ip_address: str | None = Depends(get_client_ip),
    refresh_token: str | None = Depends(get_refresh_token_cookie),
) -> TokenResponse:
    if not refresh_token:
        from app.core.exceptions import AuthenticationError
        raise AuthenticationError("Refresh token required")

    token_response, new_refresh = await service.refresh_tokens(
        refresh_token=refresh_token,
        ip_address=ip_address,
    )

    csrf_session, csrf_token = csrf_protection.generate_session_and_token()
    _set_auth_cookies(
        response,
        token_response.access_token,
        new_refresh,
        csrf_session,
        access_max_age=token_response.expires_in,
    )

    token_response.csrf_token = csrf_token
    return token_response


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    user: User = Depends(get_current_active_user),
    service: AuthService = Depends(get_auth_service),
    ip_address: str | None = Depends(get_client_ip),
    refresh_token: str | None = Depends(get_refresh_token_cookie),
    _csrf: None = Depends(validate_csrf_token),
) -> None:
    if refresh_token:
        await service.logout(
            refresh_token=refresh_token,
            user_id=user.id,
            username=user.username,
            ip_address=ip_address,
        )
    _clear_auth_cookies(response)


@router.post("/logout-all", status_code=204)
async def logout_all(
    response: Response,
    user: User = Depends(get_current_active_user),
    service: AuthService = Depends(get_auth_service),
    ip_address: str | None = Depends(get_client_ip),
    _csrf: None = Depends(validate_csrf_token),
) -> None:
    """Revoke every refresh token for the user and clear this session's cookies."""
    await service.logout_all(
        user_id=user.id,
        username=user.username,
        ip_address=ip_address,
    )
    _clear_auth_cookies(response)


@router.post("/csrf", response_model=CsrfTokenResponse)
async def issue_csrf_token(
    response: Response,
    _user: User = Depends(get_current_active_user),
) -> CsrfTokenResponse:
    """Issue a CSRF token for an authenticated session (e.g. after page reload)."""
    csrf_session, csrf_token = csrf_protection.generate_session_and_token()
    response.set_cookie(
        key="csrf_session",
        value=csrf_session,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.jwt_refresh_token_expire_days * 24 * 60 * 60,
        domain=settings.cookie_domain,
    )
    return CsrfTokenResponse(csrf_token=csrf_token)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    user: User = Depends(get_current_active_user),
) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role.value,
        is_active=user.is_active,
    )


@router.post("/change-password", status_code=204)
async def change_password(
    body: PasswordChangeRequest,
    response: Response,
    user: User = Depends(get_current_active_user),
    service: AuthService = Depends(get_auth_service),
    ip_address: str | None = Depends(get_client_ip),
    _csrf: None = Depends(validate_csrf_token),
    _rate_limit: None = Depends(rate_limit_password),
) -> None:
    await service.change_password(
        user_id=user.id,
        current_password=body.current_password,
        new_password=body.new_password,
        ip_address=ip_address,
    )
    _clear_auth_cookies(response)


@router.post("/forgot-password", response_model=ForgotPasswordResponse, status_code=202)
async def forgot_password(
    body: ForgotPasswordRequest,
    ip_address: str | None = Depends(get_client_ip),
    _rate_limit: None = Depends(rate_limit_password),
) -> ForgotPasswordResponse:
    """Request password reset email.

    This is a placeholder endpoint. In production, this would:
    1. Check if email exists
    2. Generate a secure reset token
    3. Send reset email with token link
    4. Store token hash with expiry in database

    For security, always returns success to prevent email enumeration.
    """
    logger.info("Password reset requested for email: %s from IP: %s", body.email, ip_address)
    return ForgotPasswordResponse()
