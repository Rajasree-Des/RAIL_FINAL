"""Authenticated user activity APIs (list, recent, SSE stream)."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Annotated, AsyncIterator

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import User
from app.features.activity.dependencies import get_activity_service
from app.features.activity.hub import activity_hub
from app.features.activity.schemas import ActivityListResponse, ActivityRecentResponse
from app.features.activity.service import ActivityService
from app.features.auth.dependencies import get_current_active_user
from app.infrastructure.database.session import get_db_session

router = APIRouter(prefix="/activity", tags=["activity"])


def _to_utc(dt: datetime | None) -> datetime | None:
    """Normalize filter datetimes to naive UTC wall time.

    Rows are stored as naive UTC; SQLite's bind processor drops tzinfo
    without converting, so aware inputs (e.g. +05:30) must be converted
    here or the boundary would be off by the offset.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(UTC).replace(tzinfo=None)


@router.get("", response_model=ActivityListResponse)
async def list_activity(
    user: Annotated[User, Depends(get_current_active_user)],
    service: Annotated[ActivityService, Depends(get_activity_service)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
    report_slug: str | None = Query(None),
    date_from: datetime | None = Query(None, alias="from"),
    date_to: datetime | None = Query(None, alias="to"),
) -> ActivityListResponse:
    return await service.list_activity(
        user.id,
        limit=limit,
        offset=offset,
        status=status,
        report_slug=report_slug,
        date_from=_to_utc(date_from),
        date_to=_to_utc(date_to),
    )


@router.get("/recent", response_model=ActivityRecentResponse)
async def recent_activity(
    user: Annotated[User, Depends(get_current_active_user)],
    service: Annotated[ActivityService, Depends(get_activity_service)],
    limit: int = Query(10, ge=1, le=50),
) -> ActivityRecentResponse:
    return await service.recent(user.id, limit=limit)


@router.get("/stream")
async def stream_activity(
    request: Request,
    user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    after_id: str | None = Query(None),
) -> StreamingResponse:
    """Server-Sent Events stream of the current user's activity."""
    service = ActivityService(session)
    resume_id = after_id or last_event_id

    async def event_generator() -> AsyncIterator[str]:
        queue = await activity_hub.subscribe(user.id)
        seen: set[str] = set()
        try:
            if resume_id:
                missed = await service.events_after(user.id, resume_id, limit=50)
                for entry in missed:
                    if entry.id in seen:
                        continue
                    seen.add(entry.id)
                    payload = entry.model_dump()
                    yield f"id: {entry.id}\ndata: {json.dumps(payload)}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    continue
                event_id = str(event.get("id") or "")
                if event_id and event_id in seen:
                    continue
                if event_id:
                    seen.add(event_id)
                yield f"id: {event_id}\ndata: {json.dumps(event)}\n\n"
        finally:
            await activity_hub.unsubscribe(user.id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
