"""Automation orchestration — delegates browser work to automation-engine."""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.security.encryption import decrypt_secret, encrypt_secret, mask_secret
from app.features.automation.engine_client import AutomationEngineClient
from app.features.automation.repository import AutomationRepository
from app.features.automation.schemas import (
    AutomationControlResponse,
    AutomationHistoryResponse,
    AutomationLogEntry,
    AutomationLogsResponse,
    AutomationProfileCreate,
    AutomationProfileListResponse,
    AutomationProfileResponse,
    AutomationProfileUpdate,
    AutomationRunResponse,
    AutomationRunSummary,
    AutomationStatusResponse,
    ReportSequenceItem,
)
from app.infrastructure.database.models import AutomationProfileModel, AutomationRunModel

logger = logging.getLogger(__name__)


class AutomationService:
    def __init__(
        self,
        repository: AutomationRepository,
        engine_client: AutomationEngineClient | None = None,
    ):
        self.repository = repository
        self.engine = engine_client or AutomationEngineClient()

    def _profile_to_response(self, model: AutomationProfileModel) -> AutomationProfileResponse:
        username = decrypt_secret(model.username_encrypted)
        return AutomationProfileResponse(
            id=model.id,
            name=model.name,
            slug=model.slug,
            portal_url=model.portal_url,
            username_masked=mask_secret(username),
            download_folder=model.download_folder,
            browser=model.browser,
            headless=model.headless,
            timeout_ms=model.timeout_ms,
            retry_count=model.retry_count,
            delay_seconds=model.delay_seconds,
            report_sequence=[
                ReportSequenceItem(**item)
                for item in self.repository.deserialize_json(model.report_sequence_json)
            ],
            is_enabled=model.is_enabled,
            created_at=model.created_at.isoformat(),
            updated_at=model.updated_at.isoformat(),
        )

    def _run_to_summary(self, run: AutomationRunModel) -> AutomationRunSummary:
        profile_name = run.profile.name if run.profile else "Unknown"
        return AutomationRunSummary(
            id=run.id,
            profile_id=run.profile_id,
            profile_name=profile_name,
            status=run.status,
            trigger_type=run.trigger_type,
            success_count=run.success_count,
            failure_count=run.failure_count,
            error_message=run.error_message,
            started_at=run.started_at.isoformat() if run.started_at else None,
            completed_at=run.completed_at.isoformat() if run.completed_at else None,
            created_at=run.created_at.isoformat(),
        )

    async def list_profiles(self) -> AutomationProfileListResponse:
        profiles = await self.repository.list_profiles()
        items = [self._profile_to_response(p) for p in profiles]
        return AutomationProfileListResponse(profiles=items, total=len(items))

    async def get_profile(self, profile_id: str) -> AutomationProfileResponse:
        model = await self.repository.get_profile(profile_id)
        if not model:
            raise NotFoundError("AutomationProfile", profile_id)
        return self._profile_to_response(model)

    async def create_profile(
        self,
        data: AutomationProfileCreate,
        user_id: str | None = None,
    ) -> AutomationProfileResponse:
        if await self.repository.get_profile_by_slug(data.slug):
            raise ValidationError(f"Profile slug already exists: {data.slug}")

        model = await self.repository.create_profile(
            {
                "name": data.name,
                "slug": data.slug,
                "portal_url": data.portal_url,
                "username_encrypted": encrypt_secret(data.username),
                "password_encrypted": encrypt_secret(data.password),
                "download_folder": data.download_folder,
                "browser": data.browser,
                "headless": data.headless,
                "timeout_ms": data.timeout_ms,
                "retry_count": data.retry_count,
                "delay_seconds": data.delay_seconds,
                "report_sequence_json": json.dumps(
                    [r.model_dump() for r in data.report_sequence]
                ),
                "is_enabled": data.is_enabled,
                "created_by": user_id,
                "updated_by": user_id,
            }
        )
        return self._profile_to_response(model)

    async def update_profile(
        self,
        profile_id: str,
        data: AutomationProfileUpdate,
        user_id: str | None = None,
    ) -> AutomationProfileResponse:
        model = await self.repository.get_profile(profile_id)
        if not model:
            raise NotFoundError("AutomationProfile", profile_id)

        updates: dict[str, Any] = {"updated_by": user_id}
        raw = data.model_dump(exclude_unset=True)

        if "username" in raw:
            updates["username_encrypted"] = encrypt_secret(raw.pop("username"))
        if "password" in raw:
            updates["password_encrypted"] = encrypt_secret(raw.pop("password"))
        if "report_sequence" in raw:
            seq = raw.pop("report_sequence")
            updates["report_sequence_json"] = json.dumps(
                [r.model_dump() if hasattr(r, "model_dump") else r for r in seq]
            )

        updates.update(raw)
        updated = await self.repository.update_profile(profile_id, updates)
        return self._profile_to_response(updated)

    async def start_run(
        self,
        profile_id: str | None = None,
        user_id: str | None = None,
    ) -> AutomationRunResponse:
        active = await self.repository.get_active_run()
        if active:
            raise ValidationError("An automation run is already active")

        if profile_id:
            profile = await self.repository.get_profile(profile_id)
        else:
            profiles = await self.repository.list_profiles(enabled_only=True)
            profile = profiles[0] if profiles else None

        if not profile:
            raise NotFoundError("AutomationProfile", profile_id or "default")
        if not profile.is_enabled:
            raise ValidationError("Profile is disabled")

        run = await self.repository.create_run(profile.id, user_id=user_id)
        await self.repository.add_log(run.id, "Run queued", "info")

        payload = self._build_engine_payload(profile, run.id)
        try:
            await self.engine.start_run(payload)
            await self.repository.mark_run_started(run.id)
            await self.repository.add_log(run.id, "Automation engine started", "info")
        except Exception as e:
            await self.repository.mark_run_completed(
                run.id, "failed", error_message=str(e)
            )
            await self.repository.add_log(run.id, f"Failed to start: {e}", "error")
            raise

        return AutomationRunResponse(
            run_id=run.id,
            status="running",
            message="Automation run started",
        )

    def _build_engine_payload(
        self,
        profile: AutomationProfileModel,
        run_id: str,
    ) -> dict[str, Any]:
        return {
            "run_id": run_id,
            "profile_id": profile.id,
            "portal_url": profile.portal_url,
            "username": decrypt_secret(profile.username_encrypted),
            "password": decrypt_secret(profile.password_encrypted),
            "download_folder": profile.download_folder,
            "browser": profile.browser,
            "headless": profile.headless,
            "timeout_ms": profile.timeout_ms,
            "retry_count": profile.retry_count,
            "delay_seconds": profile.delay_seconds,
            "report_sequence": self.repository.deserialize_json(
                profile.report_sequence_json
            ),
            "session_state": (
                decrypt_secret(profile.session_state_encrypted)
                if profile.session_state_encrypted
                else None
            ),
            "callback_url": f"{settings.api_prefix}/automation/callback",
            "backend_base_url": "http://backend:8000"
            if settings.environment != "development"
            else "http://127.0.0.1:8000",
            "service_token": settings.automation_service_token,
            "downloads_root": settings.automation_downloads_dir,
        }

    async def stop_run(self) -> AutomationControlResponse:
        active = await self.repository.get_active_run()
        if not active:
            return AutomationControlResponse(
                success=False, status="idle", message="No active run"
            )
        try:
            await self.engine.stop_run(active.id)
        except Exception:
            logger.warning("Engine stop call failed; marking run stopped locally")
        await self.repository.update_run(
            active.id,
            {"status": "stopped", "completed_at": datetime.now(UTC)},
        )
        await self.repository.add_log(active.id, "Run stopped by user", "warning")
        return AutomationControlResponse(
            success=True,
            run_id=active.id,
            status="stopped",
            message="Automation stopped",
        )

    async def pause_run(self) -> AutomationControlResponse:
        active = await self.repository.get_active_run()
        if not active or active.status != "running":
            return AutomationControlResponse(
                success=False, status=active.status if active else "idle",
                message="No running automation to pause",
            )
        await self.engine.pause_run(active.id)
        await self.repository.update_run(active.id, {"status": "paused"})
        await self.repository.add_log(active.id, "Run paused", "info")
        return AutomationControlResponse(
            success=True, run_id=active.id, status="paused", message="Automation paused"
        )

    async def resume_run(self) -> AutomationControlResponse:
        active = await self.repository.get_active_run()
        if not active or active.status != "paused":
            return AutomationControlResponse(
                success=False,
                status=active.status if active else "idle",
                message="No paused automation to resume",
            )
        await self.engine.resume_run(active.id)
        await self.repository.update_run(active.id, {"status": "running"})
        await self.repository.add_log(active.id, "Run resumed", "info")
        return AutomationControlResponse(
            success=True, run_id=active.id, status="running", message="Automation resumed"
        )

    async def get_status(self) -> AutomationStatusResponse:
        active = await self.repository.get_active_run()
        runs, _ = await self.repository.list_runs(limit=1)
        last_run = runs[0] if runs else None
        total, failures, rate = await self.repository.get_run_stats()

        return AutomationStatusResponse(
            active_run=self._run_to_summary(active) if active else None,
            last_run=self._run_to_summary(last_run) if last_run else None,
            next_scheduled_at=None,
            success_rate=round(rate, 1),
            total_runs=total,
            total_failures=failures,
            is_paused=active.status in {"paused", "pause_requested"} if active else False,
        )

    async def get_history(self, limit: int = 50, offset: int = 0) -> AutomationHistoryResponse:
        runs, total = await self.repository.list_runs(limit=limit, offset=offset)
        return AutomationHistoryResponse(
            runs=[self._run_to_summary(r) for r in runs],
            total=total,
        )

    async def get_logs(
        self,
        run_id: str | None = None,
        limit: int = 200,
    ) -> AutomationLogsResponse:
        if not run_id:
            active = await self.repository.get_active_run()
            if active:
                run_id = active.id
            else:
                runs, _ = await self.repository.list_runs(limit=1)
                run_id = runs[0].id if runs else None

        logs = await self.repository.list_logs(run_id=run_id, limit=limit)
        return AutomationLogsResponse(
            run_id=run_id,
            logs=[
                AutomationLogEntry(
                    id=log.id,
                    level=log.level,
                    message=log.message,
                    created_at=log.created_at.isoformat(),
                )
                for log in logs
            ],
            total=len(logs),
        )

    async def handle_callback(self, data: dict[str, Any]) -> None:
        run_id = data["run_id"]
        run = await self.repository.get_run(run_id)
        if not run:
            raise NotFoundError("AutomationRun", run_id)

        if data.get("log_message"):
            await self.repository.add_log(
                run_id,
                data["log_message"],
                data.get("log_level", "info"),
            )

        updates: dict[str, Any] = {}
        if "status" in data:
            updates["status"] = data["status"]
        if "success_count" in data:
            updates["success_count"] = data["success_count"]
        if "failure_count" in data:
            updates["failure_count"] = data["failure_count"]
        if "current_report_index" in data:
            updates["current_report_index"] = data["current_report_index"]
        if "error_message" in data:
            updates["error_message"] = data["error_message"]
        if data.get("status") in ("completed", "failed", "stopped"):
            updates["completed_at"] = datetime.now(UTC)

        if updates:
            await self.repository.update_run(run_id, updates)

        artifact = data.get("artifact")
        if artifact:
            await self.repository.add_artifact(
                run_id,
                artifact.get("type", "download"),
                artifact["file_path"],
                file_size_bytes=artifact.get("file_size_bytes"),
                report_name=artifact.get("report_name"),
            )

        if data.get("session_state"):
            encrypted = encrypt_secret(data["session_state"])
            await self.repository.update_profile(
                run.profile_id,
                {"session_state_encrypted": encrypted},
            )
