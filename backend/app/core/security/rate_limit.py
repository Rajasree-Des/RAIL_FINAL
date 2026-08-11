"""Redis-based rate limiting for the Railway Report Platform.

Implements a sliding window rate limiter with configurable limits per endpoint type.
"""

import asyncio
import hashlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from fastapi import Request

from app.core.config import settings
from app.core.exceptions import RateLimitError
from app.core.request_utils import get_client_identifier

logger = logging.getLogger(__name__)


class RateLimitType(str, Enum):
    """Rate limit categories with different thresholds."""
    LOGIN = "login"
    REGISTER = "register"
    PASSWORD = "password"
    API_GENERAL = "api_general"
    UPLOAD = "upload"


@dataclass
class RateLimitConfig:
    """Configuration for a rate limit rule."""
    max_requests: int
    window_seconds: int

    @property
    def window_ms(self) -> int:
        return self.window_seconds * 1000


RATE_LIMITS: dict[RateLimitType, RateLimitConfig] = {
    RateLimitType.LOGIN: RateLimitConfig(max_requests=5, window_seconds=900),
    RateLimitType.REGISTER: RateLimitConfig(max_requests=3, window_seconds=3600),
    RateLimitType.PASSWORD: RateLimitConfig(max_requests=3, window_seconds=3600),
    RateLimitType.API_GENERAL: RateLimitConfig(max_requests=100, window_seconds=60),
    RateLimitType.UPLOAD: RateLimitConfig(max_requests=10, window_seconds=60),
}


class RateLimiter:
    """Sliding window rate limiter using Redis."""

    def __init__(self) -> None:
        self._redis = None
        self._redis_available = False
        self._lock = asyncio.Lock()

    async def _get_redis(self):
        """Lazy initialize Redis connection."""
        if self._redis is not None:
            return self._redis if self._redis_available else None

        async with self._lock:
            if self._redis is not None:
                return self._redis if self._redis_available else None

            try:
                import redis.asyncio as redis
                self._redis = redis.from_url(
                    settings.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                )
                await self._redis.ping()
                self._redis_available = True
                logger.info("Redis connection established for rate limiting")
                return self._redis
            except Exception as e:
                logger.warning(f"Redis not available, rate limiting disabled: {e}")
                self._redis_available = False
                return None

    def _get_key(self, identifier: str, limit_type: RateLimitType) -> str:
        """Generate a Redis key for the rate limit bucket."""
        hashed = hashlib.sha256(identifier.encode()).hexdigest()[:16]
        return f"ratelimit:{limit_type.value}:{hashed}"

    async def check_rate_limit(
        self,
        identifier: str,
        limit_type: RateLimitType,
    ) -> tuple[bool, int]:
        """Check if request is within rate limit.

        Args:
            identifier: Unique identifier (IP, user ID, etc.)
            limit_type: Type of rate limit to apply

        Returns:
            Tuple of (allowed: bool, remaining: int)
        """
        redis = await self._get_redis()
        if redis is None:
            return True, -1

        config = RATE_LIMITS[limit_type]
        key = self._get_key(identifier, limit_type)
        now = int(time.time() * 1000)
        window_start = now - config.window_ms

        try:
            pipe = redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.zadd(key, {str(now): now})
            pipe.expire(key, config.window_seconds + 10)
            results = await pipe.execute()

            current_count = results[1]
            remaining = max(0, config.max_requests - current_count - 1)

            if current_count >= config.max_requests:
                await redis.zrem(key, str(now))
                return False, 0

            return True, remaining

        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            return True, -1

    async def is_rate_limited(
        self,
        identifier: str,
        limit_type: RateLimitType,
    ) -> bool:
        """Check if identifier is rate limited."""
        allowed, _ = await self.check_rate_limit(identifier, limit_type)
        return not allowed

    async def check_or_raise(
        self,
        identifier: str,
        limit_type: RateLimitType,
    ) -> int:
        """Check rate limit and raise error if exceeded.

        Returns:
            Number of remaining requests
        """
        allowed, remaining = await self.check_rate_limit(identifier, limit_type)
        if not allowed:
            config = RATE_LIMITS[limit_type]
            raise RateLimitError(
                f"Rate limit exceeded. Try again in {config.window_seconds} seconds."
            )
        return remaining


rate_limiter = RateLimiter()


def rate_limit(limit_type: RateLimitType) -> Callable:
    """Dependency factory for rate limiting specific endpoints.

    Usage:
        @router.post("/login")
        async def login(
            ...,
            _rate_limit: None = Depends(rate_limit(RateLimitType.LOGIN)),
        ):
            ...
    """
    async def rate_limit_dependency(request: Request) -> None:
        identifier = get_client_identifier(request)
        await rate_limiter.check_or_raise(identifier, limit_type)

    return rate_limit_dependency


async def rate_limit_login(request: Request) -> None:
    """Rate limit dependency for login endpoint."""
    identifier = get_client_identifier(request)
    await rate_limiter.check_or_raise(identifier, RateLimitType.LOGIN)


async def rate_limit_register(request: Request) -> None:
    """Rate limit dependency for registration endpoint."""
    identifier = get_client_identifier(request)
    await rate_limiter.check_or_raise(identifier, RateLimitType.REGISTER)


async def rate_limit_password(request: Request) -> None:
    """Rate limit dependency for password-related endpoints."""
    identifier = get_client_identifier(request)
    await rate_limiter.check_or_raise(identifier, RateLimitType.PASSWORD)


async def rate_limit_upload(request: Request) -> None:
    """Rate limit dependency for file upload endpoint."""
    identifier = get_client_identifier(request)
    await rate_limiter.check_or_raise(identifier, RateLimitType.UPLOAD)
