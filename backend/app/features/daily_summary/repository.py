"""Repository for daily briefing summaries on generated_summaries."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.daily_summary import DAILY_SUMMARY_MODEL, DAILY_SUMMARY_TYPE
from app.infrastructure.database.models import GeneratedSummaryModel, generate_uuid


class DailySummaryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_run_and_user(
        self, run_id: str, user_id: str
    ) -> GeneratedSummaryModel | None:
        stmt = (
            select(GeneratedSummaryModel)
            .where(
                GeneratedSummaryModel.run_id == run_id,
                GeneratedSummaryModel.created_by == user_id,
                GeneratedSummaryModel.summary_type == DAILY_SUMMARY_TYPE,
            )
            .order_by(GeneratedSummaryModel.updated_at.desc().nullslast())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_for_user(
        self, summary_id: str, user_id: str
    ) -> GeneratedSummaryModel | None:
        stmt = select(GeneratedSummaryModel).where(
            GeneratedSummaryModel.id == summary_id,
            GeneratedSummaryModel.created_by == user_id,
            GeneratedSummaryModel.summary_type == DAILY_SUMMARY_TYPE,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(
        self, user_id: str, *, limit: int = 30, offset: int = 0
    ) -> tuple[list[GeneratedSummaryModel], int]:
        base = select(GeneratedSummaryModel).where(
            GeneratedSummaryModel.created_by == user_id,
            GeneratedSummaryModel.summary_type == DAILY_SUMMARY_TYPE,
        )
        count_result = await self.session.execute(base)
        total = len(count_result.scalars().all())
        stmt = (
            base.order_by(GeneratedSummaryModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def upsert(
        self,
        *,
        run_id: str,
        user_id: str,
        report_date: str,
        content: str,
        status: str,
        metadata: dict[str, Any],
        error_message: str | None = None,
        generation_time_ms: float | None = None,
    ) -> GeneratedSummaryModel:
        existing = await self.get_by_run_and_user(run_id, user_id)
        now = datetime.now(UTC)
        meta_json = json.dumps(metadata)
        if existing:
            existing.content = content
            existing.status = status
            existing.report_date = report_date
            existing.metadata_json = meta_json
            existing.error_message = error_message
            existing.generation_time_ms = generation_time_ms
            existing.model_used = DAILY_SUMMARY_MODEL
            existing.updated_at = now
            await self.session.commit()
            await self.session.refresh(existing)
            return existing

        row = GeneratedSummaryModel(
            id=generate_uuid(),
            prompt_template_id=None,
            summary_type=DAILY_SUMMARY_TYPE,
            content=content,
            metadata_json=meta_json,
            statistics_json=None,
            model_used=DAILY_SUMMARY_MODEL,
            token_usage_json=None,
            generation_time_ms=generation_time_ms,
            status=status,
            error_message=error_message,
            run_id=run_id,
            report_date=report_date,
            created_by=user_id,
            created_at=now,
            updated_at=now,
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row
