"""Live system status derivation: DB, CDP, automation, storage."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.automation.config import config as automation_config
from app.core.config import settings
from app.features.dashboard.service import canonical_run_status
from app.features.system.cache_cleaner import CacheCleanResult, clear_whitelisted_cache
from app.features.system.log_export import collect_admin_events
from app.features.system.log_export_pdf import build_admin_events_pdf
from app.features.system.schemas import ClearCacheResponse, SystemComponentStatus, SystemInfoResponse
from app.infrastructure.database.models import AutomationRunModel

logger = logging.getLogger(__name__)

CDP_PROBE_TIMEOUT_SECONDS = 2.0
ACTIVE_STATUSES = frozenset({"pending", "running", "cancel_requested", "paused", "pause_requested"})


def _database_type(database_url: str) -> str:
    scheme = database_url.split("://", 1)[0].lower()
    if "postgresql" in scheme:
        return "PostgreSQL"
    if "sqlite" in scheme:
        return "SQLite"
    if "mysql" in scheme:
        return "MySQL"
    return scheme or "unknown"


def _storage_usage_bytes() -> int:
    root = Path("storage")
    if not root.is_dir():
        return 0
    total = 0
    for path in root.rglob("*"):
        try:
            if path.is_file():
                total += path.stat().st_size
        except OSError:
            continue
    return total


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()


class SystemService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _check_database(self) -> SystemComponentStatus:
        try:
            await self._session.execute(text("SELECT 1"))
            return SystemComponentStatus(ok=True, detail="Connected")
        except Exception as exc:
            logger.warning("System DB check failed: %s", exc)
            return SystemComponentStatus(ok=False, detail="Connection failed")

    async def _check_cdp(self) -> SystemComponentStatus:
        url = automation_config.chrome_debug_url.rstrip("/") + "/json/version"
        try:
            async with httpx.AsyncClient(timeout=CDP_PROBE_TIMEOUT_SECONDS) as client:
                response = await client.get(url)
            if response.status_code == 200:
                browser = response.json().get("Browser", "connected")
                return SystemComponentStatus(ok=True, detail=str(browser))
            return SystemComponentStatus(ok=False, detail=f"HTTP {response.status_code}")
        except Exception:
            return SystemComponentStatus(ok=False, detail="Not reachable")

    async def _run_summary(self) -> tuple[str, str | None, str | None, str | None]:
        """(automation_status, active_run_id, last_success_iso, last_failure_iso)."""
        newest = (
            await self._session.execute(
                select(AutomationRunModel)
                .order_by(AutomationRunModel.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        automation_status = "idle"
        active_run_id = None
        if newest is not None and newest.status in ACTIVE_STATUSES:
            automation_status = canonical_run_status(newest)
            active_run_id = newest.id

        last_success = (
            await self._session.execute(
                select(AutomationRunModel.completed_at)
                .where(
                    AutomationRunModel.status == "completed",
                    AutomationRunModel.failure_count == 0,
                )
                .order_by(AutomationRunModel.completed_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        last_failure = (
            await self._session.execute(
                select(AutomationRunModel.completed_at)
                .where(AutomationRunModel.status == "failed")
                .order_by(AutomationRunModel.completed_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        return automation_status, active_run_id, _iso(last_success), _iso(last_failure)

    async def info(self) -> SystemInfoResponse:
        database = await self._check_database()
        cdp = await self._check_cdp()

        if database.ok:
            automation_status, active_run_id, last_success, last_failure = (
                await self._run_summary()
            )
        else:
            automation_status, active_run_id, last_success, last_failure = (
                "unknown", None, None, None,
            )

        return SystemInfoResponse(
            app_version=settings.app_version,
            environment=settings.environment,
            backend=SystemComponentStatus(ok=True, detail="Running"),
            database=database,
            database_type=_database_type(settings.database_url),
            cdp=cdp,
            automation_status=automation_status,
            active_run_id=active_run_id,
            last_successful_run_at=last_success,
            last_failed_run_at=last_failure,
            storage_usage_bytes=_storage_usage_bytes(),
        )

    async def export_logs_pdf(self) -> bytes:
        events = await collect_admin_events(self._session)
        return build_admin_events_pdf(
            events,
            environment=settings.environment,
            app_version=settings.app_version,
        )

    async def clear_cache(self) -> ClearCacheResponse:
        from app.features.dashboard.analytics import clear_analytics_cache
        from app.features.settings.cache import settings_cache

        await settings_cache.invalidate_all()
        clear_analytics_cache()
        cleared = ["settings", "dashboard_analytics"]

        fs_result: CacheCleanResult = clear_whitelisted_cache()
        cleared.extend(fs_result.cleared)

        return ClearCacheResponse(
            success=True,
            cleared=cleared,
            files_removed=fs_result.files_removed,
            directories_removed=fs_result.directories_removed,
            bytes_freed=fs_result.bytes_freed,
            skipped_locked=fs_result.skipped_locked,
            partial=fs_result.partial,
        )
