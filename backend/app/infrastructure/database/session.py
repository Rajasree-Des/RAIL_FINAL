"""Async SQLAlchemy session factory — safe across event loops / worker threads.

Automation runs Playwright in a dedicated thread via ``asyncio.run()``, which
creates a *new* event loop. AsyncEngine connection pools are bound to the loop
that first used them. Sharing uvicorn's engine with that worker loop causes
ingest/process DB writes to hang or fail with "Future attached to a different
loop", while portal extraction (filesystem-only) still succeeds.

This module lazily creates one AsyncEngine + sessionmaker per running event
loop, so the API server and the automation worker never share pooled
connections across loops.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

logger = logging.getLogger(__name__)

_engines: dict[int, AsyncEngine] = {}
_sessionmakers: dict[int, async_sessionmaker[AsyncSession]] = {}


def _to_async_url(url: str) -> str:
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _loop_key() -> int:
    try:
        return id(asyncio.get_running_loop())
    except RuntimeError:
        # No running loop (sync import / script bootstrap): use a sentinel.
        return 0


def _get_engine() -> AsyncEngine:
    key = _loop_key()
    engine = _engines.get(key)
    if engine is None:
        engine = create_async_engine(_to_async_url(settings.database_url), echo=False)
        _engines[key] = engine
        logger.debug("Created AsyncEngine for event loop key=%s", key)
    return engine


def _get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    key = _loop_key()
    maker = _sessionmakers.get(key)
    if maker is None:
        maker = async_sessionmaker(
            _get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
        _sessionmakers[key] = maker
    return maker


class _SessionLocalProxy:
    """Callable proxy so ``async with SessionLocal() as session`` stays unchanged."""

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return _get_sessionmaker()(*args, **kwargs)

    def configure(self, *args: Any, **kwargs: Any) -> Any:
        return _get_sessionmaker().configure(*args, **kwargs)


SessionLocal = _SessionLocalProxy()


class _EngineProxy:
    """Attribute proxy for scripts that import ``engine`` (e.g. ensure_tables)."""

    def begin(self, *args: Any, **kwargs: Any) -> Any:
        return _get_engine().begin(*args, **kwargs)

    def connect(self, *args: Any, **kwargs: Any) -> Any:
        return _get_engine().connect(*args, **kwargs)

    def dispose(self, *args: Any, **kwargs: Any) -> Any:
        return _get_engine().dispose(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(_get_engine(), name)


engine = _EngineProxy()


async def dispose_current_loop_engine() -> None:
    """Dispose the AsyncEngine bound to the current event loop (worker cleanup)."""
    key = _loop_key()
    maker = _sessionmakers.pop(key, None)
    eng = _engines.pop(key, None)
    if eng is not None:
        await eng.dispose()
        logger.debug("Disposed AsyncEngine for event loop key=%s", key)
    del maker


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
