from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from jose import JWTError, jwt

from app.core.config import settings
from app.core.exceptions import AuthenticationError


class JWTHandler:
    def __init__(self) -> None:
        self._secret = settings.jwt_secret_key
        self._algorithm = settings.jwt_algorithm
        self._access_expire = settings.jwt_access_token_expire_minutes
        self._refresh_expire = settings.jwt_refresh_token_expire_days

    def create_access_token(
        self,
        subject: str,
        extra_claims: dict[str, Any] | None = None,
        expire_minutes: int | None = None,
    ) -> str:
        minutes = expire_minutes if expire_minutes is not None else self._access_expire
        expire = datetime.now(UTC) + timedelta(minutes=minutes)
        claims = {
            "sub": subject,
            "exp": expire,
            "type": "access",
            "iat": datetime.now(UTC),
        }
        if extra_claims:
            claims.update(extra_claims)
        return jwt.encode(claims, self._secret, algorithm=self._algorithm)

    def create_refresh_token(self, subject: str, expire_days: int | None = None) -> str:
        days = expire_days if expire_days is not None else self._refresh_expire
        expire = datetime.now(UTC) + timedelta(days=days)
        claims = {
            "sub": subject,
            "exp": expire,
            "type": "refresh",
            "iat": datetime.now(UTC),
            "jti": str(uuid4()),
        }
        return jwt.encode(claims, self._secret, algorithm=self._algorithm)

    def decode_token(self, token: str, token_type: str = "access") -> dict[str, Any]:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._algorithm])
            if payload.get("type") != token_type:
                raise AuthenticationError(f"Invalid token type: expected {token_type}")
            return payload
        except JWTError as e:
            raise AuthenticationError(f"Invalid or expired token: {e}") from e

    def get_subject(self, token: str, token_type: str = "access") -> str:
        payload = self.decode_token(token, token_type)
        subject = payload.get("sub")
        if not subject:
            raise AuthenticationError("Token missing subject claim")
        return subject


jwt_handler = JWTHandler()
