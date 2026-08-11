"""Activity recording and query service."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.activity.hub import activity_hub
from app.features.activity.repository import ActivityRepository
from app.features.activity.schemas import ActivityEntry, ActivityListResponse, ActivityRecentResponse
from app.infrastructure.database.models import UserActivityModel

logger = logging.getLogger(__name__)

SECRET_KEY_RE = re.compile(
    r"(password|passwd|secret|token|cookie|authorization|api[_-]?key|csrf)",
    re.IGNORECASE,
)

# Redact assignment-style secret values in free-text messages
SECRET_VALUE_RE = re.compile(
    r"(?i)\b(password|passwd|secret|token|cookie|authorization|api[_-]?key|csrf)\b\s*[:=]\s*([^\s,;]+)",
)


def scrub_metadata(metadata: Any) -> Any:
    if metadata is None:
        return {}
    if isinstance(metadata, list):
        return [scrub_metadata(item) for item in metadata]
    if not isinstance(metadata, dict):
        if isinstance(metadata, str) and len(metadata) > 500:
            return metadata[:500] + "…"
        return metadata
    cleaned: dict[str, Any] = {}
    for key, value in metadata.items():
        if SECRET_KEY_RE.search(str(key)):
            continue
        if isinstance(value, dict):
            cleaned[key] = scrub_metadata(value)
        elif isinstance(value, list):
            cleaned[key] = scrub_metadata(value)
        elif isinstance(value, str) and len(value) > 500:
            cleaned[key] = value[:500] + "…"
        else:
            cleaned[key] = value
    return cleaned


def scrub_message(message: str) -> str:
    """Redact secret-like values from activity messages (never store credentials)."""
    if not message:
        return message
    redacted = SECRET_VALUE_RE.sub(r"\1=[REDACTED]", message)
    if len(redacted) > 1000:
        redacted = redacted[:1000] + "…"
    return redacted


def _created_at_iso(dt: datetime | None) -> str:
    """UTC ISO-8601 with explicit offset.

    SQLite returns naive datetimes (stored in UTC); without the offset the
    browser would parse them as local time and show the wrong clock time.
    """
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()


def to_entry(row: UserActivityModel) -> ActivityEntry:
    meta: dict[str, Any] = {}
    if row.metadata_json:
        try:
            meta = json.loads(row.metadata_json)
        except json.JSONDecodeError:
            meta = {}
    return ActivityEntry(
        id=row.id,
        user_id=row.user_id,
        action=row.action,
        message=row.message,
        status=row.status,  # type: ignore[arg-type]
        report_slug=row.report_slug,
        run_id=row.run_id,
        metadata=meta if isinstance(meta, dict) else {},
        created_at=_created_at_iso(row.created_at),
    )


class ActivityService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ActivityRepository(session)

    async def _publish(self, user_id: str, event: dict[str, Any]) -> None:
        main = activity_hub._main_loop
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if main is not None and running is not None and running is not main:
            activity_hub.publish_threadsafe(user_id, event)
            return
        try:
            await activity_hub.publish(user_id, event)
        except RuntimeError:
            activity_hub.publish_threadsafe(user_id, event)

    async def record(
        self,
        *,
        user_id: str,
        action: str,
        message: str,
        status: str = "info",
        report_slug: str | None = None,
        run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        dedupe_key: str | None = None,
    ) -> ActivityEntry | None:
        if not user_id:
            return None
        cleaned = scrub_metadata(metadata)
        if not isinstance(cleaned, dict):
            cleaned = {}
        meta_json = json.dumps(cleaned) if cleaned else None
        safe_message = scrub_message(message)
        row = await self._repo.create(
            user_id=user_id,
            action=action,
            message=safe_message,
            status=status,
            report_slug=report_slug,
            run_id=run_id,
            metadata_json=meta_json,
            dedupe_key=dedupe_key,
        )
        if row is None:
            logger.debug(
                "activity_deduped user=%s action=%s dedupe_key=%s",
                user_id,
                action,
                dedupe_key,
            )
            return None
        entry = to_entry(row)
        await self._publish(user_id, entry.model_dump())
        return entry

    async def list_activity(
        self,
        user_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        report_slug: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> ActivityListResponse:
        rows, total = await self._repo.list_for_user(
            user_id,
            limit=limit,
            offset=offset,
            status=status,
            report_slug=report_slug,
            date_from=date_from,
            date_to=date_to,
        )
        return ActivityListResponse(
            items=[to_entry(r) for r in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def recent(self, user_id: str, *, limit: int = 10) -> ActivityRecentResponse:
        rows, _ = await self._repo.list_for_user(user_id, limit=limit, offset=0)
        return ActivityRecentResponse(items=[to_entry(r) for r in rows])

    async def events_after(self, user_id: str, after_id: str, *, limit: int = 50) -> list[ActivityEntry]:
        rows = await self._repo.get_after(user_id, after_id, limit=limit)
        return [to_entry(r) for r in rows]


async def record_activity(
    session: AsyncSession,
    *,
    user_id: str | None,
    action: str,
    message: str,
    status: str = "info",
    report_slug: str | None = None,
    run_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    dedupe_key: str | None = None,
) -> ActivityEntry | None:
    """Convenience helper for insertion points outside request DI."""
    if not user_id:
        return None
    service = ActivityService(session)
    return await service.record(
        user_id=user_id,
        action=action,
        message=message,
        status=status,
        report_slug=report_slug,
        run_id=run_id,
        metadata=metadata,
        dedupe_key=dedupe_key,
    )
