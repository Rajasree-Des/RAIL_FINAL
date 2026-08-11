"""Fire-and-forget helpers to record user activity from any service."""

from __future__ import annotations

import logging
from typing import Any

from app.features.activity.service import record_activity
from app.infrastructure.database.models import UserActivityModel
from app.infrastructure.database.session import SessionLocal
from sqlalchemy import text

logger = logging.getLogger(__name__)

_table_ensured = False


async def ensure_user_activity_table() -> None:
    """Best-effort create table when alembic CLI is unavailable.

    Runs the DDL once per process (called at startup and lazily as a fallback).
    """
    global _table_ensured
    if _table_ensured:
        return
    try:
        async with SessionLocal() as session:
            await session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS user_activity (
                        id VARCHAR(36) PRIMARY KEY,
                        user_id VARCHAR(64) NOT NULL,
                        action VARCHAR(64) NOT NULL,
                        message TEXT NOT NULL,
                        status VARCHAR(16) NOT NULL DEFAULT 'info',
                        report_slug VARCHAR(64),
                        run_id VARCHAR(36),
                        metadata_json TEXT,
                        dedupe_key VARCHAR(255),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE (user_id, dedupe_key)
                    )
                    """
                )
            )
            await session.commit()
        _table_ensured = True
    except Exception as exc:
        logger.debug("ensure_user_activity_table: %s", exc)


async def emit_activity(
    *,
    user_id: str | None,
    action: str,
    message: str,
    status: str = "info",
    report_slug: str | None = None,
    run_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    dedupe_key: str | None = None,
) -> None:
    if not user_id:
        return
    try:
        await ensure_user_activity_table()
        async with SessionLocal() as session:
            await record_activity(
                session,
                user_id=user_id,
                action=action,
                message=message,
                status=status,
                report_slug=report_slug,
                run_id=run_id,
                metadata=metadata,
                dedupe_key=dedupe_key,
            )
    except Exception as exc:
        logger.warning("Failed to record activity %s: %s", action, exc)
