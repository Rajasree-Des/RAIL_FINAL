"""Data access for automation profiles and runs."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.json_utils import deserialize_json, serialize_json
from app.infrastructure.database.models import (
    AutomationArtifactModel,
    AutomationLogModel,
    AutomationProfileModel,
    AutomationRunModel,
)


class AutomationRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def serialize_json(data: Any) -> str:
        return serialize_json(data)

    @staticmethod
    def deserialize_json(raw: str | None) -> Any:
        if not raw:
            return []
        return deserialize_json(raw, default=[])

    async def list_profiles(self, enabled_only: bool = False) -> list[AutomationProfileModel]:
        stmt = select(AutomationProfileModel).where(
            AutomationProfileModel.is_deleted.is_(False)
        )
        if enabled_only:
            stmt = stmt.where(AutomationProfileModel.is_enabled.is_(True))
        stmt = stmt.order_by(AutomationProfileModel.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_profile(self, profile_id: str) -> AutomationProfileModel | None:
        stmt = select(AutomationProfileModel).where(
            AutomationProfileModel.id == profile_id,
            AutomationProfileModel.is_deleted.is_(False),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_profile_by_slug(self, slug: str) -> AutomationProfileModel | None:
        stmt = select(AutomationProfileModel).where(
            AutomationProfileModel.slug == slug,
            AutomationProfileModel.is_deleted.is_(False),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_profile(self, data: dict[str, Any]) -> AutomationProfileModel:
        model = AutomationProfileModel(**data)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return model

    async def update_profile(
        self,
        profile_id: str,
        data: dict[str, Any],
    ) -> AutomationProfileModel | None:
        model = await self.get_profile(profile_id)
        if not model:
            return None
        for key, value in data.items():
            setattr(model, key, value)
        await self._session.commit()
        await self._session.refresh(model)
        return model

    async def create_run(
        self,
        profile_id: str,
        trigger_type: str = "manual",
        user_id: str | None = None,
    ) -> AutomationRunModel:
        run = AutomationRunModel(
            profile_id=profile_id,
            status="pending",
            trigger_type=trigger_type,
            created_by=user_id,
        )
        self._session.add(run)
        await self._session.commit()
        await self._session.refresh(run)
        return run

    async def get_run(self, run_id: str) -> AutomationRunModel | None:
        stmt = (
            select(AutomationRunModel)
            .options(
                selectinload(AutomationRunModel.profile),
                selectinload(AutomationRunModel.logs),
                selectinload(AutomationRunModel.artifacts),
            )
            .where(AutomationRunModel.id == run_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_run(self) -> AutomationRunModel | None:
        stmt = (
            select(AutomationRunModel)
            .options(selectinload(AutomationRunModel.profile))
            .where(AutomationRunModel.status.in_(["pending", "running", "paused", "pause_requested", "cancel_requested"]))
            .order_by(desc(AutomationRunModel.created_at))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_run(self, run_id: str, data: dict[str, Any]) -> AutomationRunModel | None:
        run = await self.get_run(run_id)
        if not run:
            return None
        for key, value in data.items():
            setattr(run, key, value)
        await self._session.commit()
        await self._session.refresh(run)
        return run

    async def add_log(
        self,
        run_id: str,
        message: str,
        level: str = "info",
    ) -> AutomationLogModel:
        log = AutomationLogModel(run_id=run_id, level=level, message=message)
        self._session.add(log)
        await self._session.commit()
        await self._session.refresh(log)
        return log

    async def add_artifact(
        self,
        run_id: str,
        artifact_type: str,
        file_path: str,
        *,
        file_size_bytes: int | None = None,
        report_name: str | None = None,
    ) -> AutomationArtifactModel:
        artifact = AutomationArtifactModel(
            run_id=run_id,
            artifact_type=artifact_type,
            file_path=file_path,
            file_size_bytes=file_size_bytes,
            report_name=report_name,
        )
        self._session.add(artifact)
        await self._session.commit()
        await self._session.refresh(artifact)
        return artifact

    async def list_runs(self, limit: int = 50, offset: int = 0) -> tuple[list[AutomationRunModel], int]:
        count_stmt = select(func.count()).select_from(AutomationRunModel)
        total = (await self._session.execute(count_stmt)).scalar_one()

        stmt = (
            select(AutomationRunModel)
            .options(selectinload(AutomationRunModel.profile))
            .order_by(desc(AutomationRunModel.created_at))
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all()), total

    async def list_logs(
        self,
        run_id: str | None = None,
        limit: int = 200,
    ) -> list[AutomationLogModel]:
        stmt = select(AutomationLogModel).order_by(desc(AutomationLogModel.created_at))
        if run_id:
            stmt = stmt.where(AutomationLogModel.run_id == run_id)
        stmt = stmt.limit(limit)
        result = await self._session.execute(stmt)
        return list(reversed(result.scalars().all()))

    async def get_run_stats(self) -> tuple[int, int, float]:
        total_stmt = select(func.count()).select_from(AutomationRunModel)
        total = (await self._session.execute(total_stmt)).scalar_one()

        failed_stmt = select(func.count()).select_from(AutomationRunModel).where(
            AutomationRunModel.status == "failed"
        )
        failures = (await self._session.execute(failed_stmt)).scalar_one()

        success_stmt = select(func.count()).select_from(AutomationRunModel).where(
            AutomationRunModel.status == "completed"
        )
        successes = (await self._session.execute(success_stmt)).scalar_one()

        rate = (successes / total * 100) if total > 0 else 0.0
        return total, failures, rate

    async def mark_run_started(self, run_id: str) -> None:
        await self.update_run(
            run_id,
            {"status": "running", "started_at": datetime.now(UTC)},
        )

    async def mark_run_completed(
        self,
        run_id: str,
        status: str,
        *,
        success_count: int = 0,
        failure_count: int = 0,
        error_message: str | None = None,
    ) -> None:
        await self.update_run(
            run_id,
            {
                "status": status,
                "success_count": success_count,
                "failure_count": failure_count,
                "error_message": error_message,
                "completed_at": datetime.now(UTC),
            },
        )
