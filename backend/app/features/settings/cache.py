"""Redis-backed settings cache with in-memory fallback."""

import json
import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

CACHE_KEY_ALL = "app_settings:all"
CACHE_KEY_CATEGORY_PREFIX = "app_settings:category:"
CACHE_TTL_SECONDS = 300


class SettingsCache:
    """Cache merged settings payloads."""

    def __init__(self) -> None:
        self._redis = None
        self._redis_available = False
        self._memory: dict[str, str] = {}

    async def _get_redis(self):
        if self._redis is not None:
            return self._redis if self._redis_available else None

        try:
            import redis.asyncio as redis

            self._redis = redis.from_url(settings.redis_url, decode_responses=True)
            await self._redis.ping()
            self._redis_available = True
            return self._redis
        except Exception:
            logger.debug("Redis unavailable for settings cache; using in-memory fallback")
            self._redis_available = False
            return None

    async def get(self, key: str) -> Any | None:
        redis = await self._get_redis()
        if redis:
            raw = await redis.get(key)
        else:
            raw = self._memory.get(key)

        if raw is None:
            return None
        return json.loads(raw)

    async def set(self, key: str, value: Any) -> None:
        raw = json.dumps(value)
        redis = await self._get_redis()
        if redis:
            await redis.setex(key, CACHE_TTL_SECONDS, raw)
        else:
            self._memory[key] = raw

    async def invalidate_all(self) -> None:
        redis = await self._get_redis()
        if redis:
            keys = await redis.keys("app_settings:*")
            if keys:
                await redis.delete(*keys)
        self._memory.clear()


settings_cache = SettingsCache()
