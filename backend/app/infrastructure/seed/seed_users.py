import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security.password import password_hasher
from app.domain.entities.user import UserRole
from app.features.auth.repository import UserRepository

logger = logging.getLogger(__name__)


def _admin_email(username: str) -> str:
    return f"{username.lower()}@railway.local"


async def seed_admin_user(session: AsyncSession) -> None:
    username = (settings.default_admin_username or "").strip()
    password = settings.default_admin_password or ""

    if not username or not password:
        logger.warning(
            "DEFAULT_ADMIN_USERNAME and DEFAULT_ADMIN_PASSWORD not set; skipping admin seed"
        )
        return

    user_repo = UserRepository(session)
    existing = await user_repo.get_by_username(username)
    if existing:
        # Dev-only: keep local admin password aligned with .env so login doesn't drift.
        if not settings.is_production and not password_hasher.verify(
            password, existing.password_hash
        ):
            logger.warning(
                "Admin user %r password does not match DEFAULT_ADMIN_PASSWORD; resetting (dev)",
                username,
            )
            await user_repo.update_password(
                existing.id, password_hasher.hash(password)
            )
            return
        logger.info("Admin user %r already exists, skipping", username)
        return

    logger.info("Creating default admin user %r", username)
    await user_repo.create(
        user_id=str(uuid.uuid4()),
        username=username,
        email=_admin_email(username),
        password_hash=password_hasher.hash(password),
        role=UserRole.ADMIN,
    )
    logger.info("Default admin user %r created successfully", username)
