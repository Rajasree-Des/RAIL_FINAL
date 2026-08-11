"""Best-effort schema ensure for daily summary columns (when alembic CLI is shadowed)."""

from __future__ import annotations

import logging

from sqlalchemy import text

from app.infrastructure.database.session import SessionLocal

logger = logging.getLogger(__name__)

_ensured = False


async def ensure_daily_summary_schema() -> None:
    """Add run_id / report_date / updated_at on generated_summaries if missing."""
    global _ensured
    if _ensured:
        return
    try:
        async with SessionLocal() as session:
            # SQLite / Postgres compatible ALTER IF via try/except per column
            for ddl in (
                "ALTER TABLE generated_summaries ADD COLUMN run_id VARCHAR(36)",
                "ALTER TABLE generated_summaries ADD COLUMN report_date VARCHAR(16)",
                "ALTER TABLE generated_summaries ADD COLUMN updated_at DATETIME",
            ):
                try:
                    await session.execute(text(ddl))
                    await session.commit()
                except Exception:
                    await session.rollback()
            _ensured = True
    except Exception as exc:
        logger.debug("ensure_daily_summary_schema: %s", exc)
