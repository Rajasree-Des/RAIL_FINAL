import hashlib
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import User, UserRole
from app.infrastructure.database.models import RefreshTokenModel, UserModel

logger = logging.getLogger(__name__)


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: str) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_username(self, username: str) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.username == username.lower())
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == email.lower())
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def create(
        self,
        user_id: str,
        username: str,
        email: str,
        password_hash: str,
        role: UserRole = UserRole.VIEWER,
    ) -> User:
        model = UserModel(
            id=user_id,
            username=username.lower(),
            email=email.lower(),
            password_hash=password_hash,
            role=role.value,
            is_active=True,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def update_last_login(self, user_id: str) -> None:
        await self._session.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(last_login=datetime.now(UTC))
        )
        await self._session.commit()

    async def update_password(self, user_id: str, password_hash: str) -> None:
        await self._session.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(password_hash=password_hash, updated_at=datetime.now(UTC))
        )
        await self._session.commit()

    @staticmethod
    def _to_entity(model: UserModel) -> User:
        return User(
            id=model.id,
            username=model.username,
            email=model.email,
            password_hash=model.password_hash,
            role=UserRole(model.role),
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
            last_login=model.last_login,
        )


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    async def create(self, user_id: str, token: str, expires_days: int) -> None:
        model = RefreshTokenModel(
            user_id=user_id,
            token_hash=self._hash_token(token),
            expires_at=datetime.now(UTC) + timedelta(days=expires_days),
        )
        self._session.add(model)
        await self._session.commit()

    async def validate(self, token: str) -> str | None:
        token_hash = self._hash_token(token)
        result = await self._session.execute(
            select(RefreshTokenModel).where(
                RefreshTokenModel.token_hash == token_hash,
                RefreshTokenModel.revoked_at.is_(None),
            )
        )
        model = result.scalar_one_or_none()

        if not model or model.is_expired:
            return None

        return model.user_id

    async def revoke(self, token: str) -> None:
        token_hash = self._hash_token(token)
        await self._session.execute(
            update(RefreshTokenModel)
            .where(RefreshTokenModel.token_hash == token_hash)
            .values(revoked_at=datetime.now(UTC))
        )
        await self._session.commit()

    async def revoke_all_for_user(self, user_id: str) -> None:
        await self._session.execute(
            update(RefreshTokenModel)
            .where(
                RefreshTokenModel.user_id == user_id,
                RefreshTokenModel.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(UTC))
        )
        await self._session.commit()
