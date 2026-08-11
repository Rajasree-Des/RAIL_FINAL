"""Data access for user activity rows."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import UserActivityModel


class ActivityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: str,
        action: str,
        message: str,
        status: str,
        report_slug: str | None = None,
        run_id: str | None = None,
        metadata_json: str | None = None,
        dedupe_key: str | None = None,
    ) -> UserActivityModel | None:
        row = UserActivityModel(
            user_id=user_id,
            action=action,
            message=message,
            status=status,
            report_slug=report_slug,
            run_id=run_id,
            metadata_json=metadata_json,
            dedupe_key=dedupe_key,
            # Client-side timestamp keeps microsecond ordering for after_id replay
            created_at=datetime.now(UTC),
        )
        self._session.add(row)
        try:
            await self._session.commit()
            await self._session.refresh(row)
            return row
        except IntegrityError:
            await self._session.rollback()
            return None

    async def list_for_user(
        self,
        user_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        report_slug: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        after_id: str | None = None,
    ) -> tuple[list[UserActivityModel], int]:
        filters: list[Any] = [UserActivityModel.user_id == user_id]
        if status:
            filters.append(UserActivityModel.status == status)
        if report_slug:
            filters.append(UserActivityModel.report_slug == report_slug)
        if date_from is not None:
            filters.append(UserActivityModel.created_at >= date_from)
        if date_to is not None:
            filters.append(UserActivityModel.created_at <= date_to)
        if after_id:
            newer = await self.get_after(user_id, after_id, limit=10_000)
            newer_ids = [r.id for r in newer]
            if not newer_ids:
                return [], 0
            filters.append(UserActivityModel.id.in_(newer_ids))

        where = and_(*filters)
        count_stmt = select(func.count()).select_from(UserActivityModel).where(where)
        total = (await self._session.execute(count_stmt)).scalar_one()

        stmt = (
            select(UserActivityModel)
            .where(where)
            .order_by(UserActivityModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = list((await self._session.execute(stmt)).scalars().all())
        return rows, total

    async def list_all(
        self,
        *,
        limit: int = 10_000,
        offset: int = 0,
    ) -> tuple[list[UserActivityModel], int]:
        """Admin-only: all users' activity rows (system log export)."""
        count_stmt = select(func.count()).select_from(UserActivityModel)
        total = (await self._session.execute(count_stmt)).scalar_one()

        stmt = (
            select(UserActivityModel)
            .order_by(UserActivityModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = list((await self._session.execute(stmt)).scalars().all())
        return rows, total

    async def get_after(
        self,
        user_id: str,
        after_id: str,
        *,
        limit: int = 50,
    ) -> list[UserActivityModel]:
        after_row = await self._session.get(UserActivityModel, after_id)
        if not after_row or after_row.user_id != user_id:
            return []
        cursor_ts = after_row.created_at
        if cursor_ts is None:
            return []

        # Compare against the raw stored value (same storage form on both sides),
        # >= so same-second siblings still replay (SSE seen-set dedupes).
        stmt = (
            select(UserActivityModel)
            .where(
                UserActivityModel.user_id == user_id,
                UserActivityModel.id != after_id,
                UserActivityModel.created_at >= cursor_ts,
            )
            .order_by(UserActivityModel.created_at.asc(), UserActivityModel.id.asc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())
