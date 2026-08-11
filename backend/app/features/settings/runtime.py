"""Runtime helpers for reading settings from other features.

Reads go through the settings cache (invalidated on every settings write),
falling back to a direct DB lookup on cold cache.
"""

import json
import logging
from typing import Any

from app.features.settings.cache import CACHE_KEY_ALL, settings_cache

logger = logging.getLogger(__name__)

SESSION_TIMEOUT_MINUTES: dict[str, int] = {
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "never": 30 * 24 * 60,  # "never" maps to 30 days
}
DEFAULT_SESSION_TIMEOUT_MINUTES = 30


async def get_effective_setting(category: str, key: str, default: Any = None) -> Any:
    """Resolve one effective setting value (override or default)."""
    cached = await settings_cache.get(CACHE_KEY_ALL)
    if cached:
        for cat in cached.get("categories", []):
            if cat.get("slug") != category:
                continue
            for setting in cat.get("settings", []):
                if setting.get("key") == key:
                    return setting.get("value")
        return default

    try:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.infrastructure.database.models import AppSettingDefinitionModel
        from app.infrastructure.database.session import SessionLocal

        async with SessionLocal() as session:
            result = await session.execute(
                select(AppSettingDefinitionModel)
                .options(selectinload(AppSettingDefinitionModel.value))
                .where(
                    AppSettingDefinitionModel.category == category,
                    AppSettingDefinitionModel.key == key,
                )
            )
            definition = result.scalar_one_or_none()
            if definition is None:
                return default
            raw = definition.value.value_json if definition.value else definition.default_value
            return json.loads(raw) if raw else default
    except Exception:
        logger.warning("Failed to read setting %s.%s; using default", category, key, exc_info=True)
        return default


async def get_session_timeout_minutes() -> int:
    """Access-token lifetime in minutes from the account.session_timeout setting."""
    value = await get_effective_setting("account", "session_timeout", "30m")
    return SESSION_TIMEOUT_MINUTES.get(str(value), DEFAULT_SESSION_TIMEOUT_MINUTES)
