"""Persist CDP automation runs and secure artifact path resolution."""

from __future__ import annotations

import json
import logging
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.automation.config import config
from app.automation.merged_report_catalog import merged_download_urls
from app.automation.report_keys import canonicalize_report_key
from app.automation.schemas import MultiReportResult, ReportResult
from app.automation.utils import log_automation_event
from app.infrastructure.database.models import (
    AutomationArtifactModel,
    AutomationProfileModel,
    AutomationRunModel,
)

logger = logging.getLogger(__name__)

CDP_PROFILE_SLUG = "cdp-in-process"
CDP_PROFILE_NAME = "CDP In-Process Automation"


class ArtifactPathError(Exception):
    """Raised when an artifact path is invalid or missing."""

    def __init__(self, message: str, *, status_code: int = 404) -> None:
        super().__init__(message)
        self.status_code = status_code


def storage_roots() -> list[Path]:
    return [
        Path(config.output_excel_dir).resolve(),
        Path(config.output_pdf_dir).resolve(),
        Path(config.extracted_data_dir).resolve(),
        Path(config.pdf_archive_dir).resolve(),
    ]


def is_under_storage(path: Path) -> bool:
    resolved = path.resolve()
    for root in storage_roots():
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False

def is_under_output_pdf(path: Path) -> bool:
    root = Path(config.output_pdf_dir).resolve()
    try:
        path.resolve().relative_to(root)
        return True
    except ValueError:
        return False


def is_under_output_excel(path: Path) -> bool:
    root = Path(config.output_excel_dir).resolve()
    try:
        path.resolve().relative_to(root)
        return True
    except ValueError:
        return False


def validate_artifact_file(
    path: Path,
    *,
    require_pdf_header: bool = False,
    file_type: str | None = None,
    min_mtime: float | None = None,
) -> Path:
    if ".." in path.parts:
        raise ArtifactPathError("Path traversal blocked", status_code=400)
    resolved = path.resolve()
    if not is_under_storage(resolved):
        raise ArtifactPathError("File outside storage root", status_code=400)

    # Final PDFs must live under storage/output/pdf only (never archive/CSV/ZIP).
    if file_type == "pdf" or (require_pdf_header and resolved.suffix.lower() == ".pdf"):
        if not is_under_output_pdf(resolved):
            raise ArtifactPathError("PDF must be under output/pdf", status_code=400)
        if resolved.suffix.lower() != ".pdf":
            raise ArtifactPathError("PDF suffix required", status_code=400)
        require_pdf_header = True
    elif file_type == "excel":
        if not is_under_output_excel(resolved):
            raise ArtifactPathError("Excel must be under output/excel", status_code=400)

    if not resolved.is_file():
        raise ArtifactPathError("File not found", status_code=404)
    stat = resolved.stat()
    if stat.st_size <= 0:
        raise ArtifactPathError("Empty file", status_code=404)
    if min_mtime is not None and stat.st_mtime < min_mtime:
        raise ArtifactPathError("Stale artifact file", status_code=500)
    if require_pdf_header:
        header = resolved.read_bytes()[:5]
        if header != b"%PDF-":
            raise ArtifactPathError("Invalid PDF", status_code=500)
    if file_type == "excel":
        if resolved.suffix.lower() != ".xlsx":
            raise ArtifactPathError("Excel suffix required", status_code=400)
        if not zipfile.is_zipfile(resolved):
            raise ArtifactPathError("Invalid Excel", status_code=500)
        try:
            with zipfile.ZipFile(resolved) as workbook_zip:
                names = set(workbook_zip.namelist())
                required_entries = {"[Content_Types].xml", "xl/workbook.xml"}
                if not required_entries.issubset(names):
                    raise ArtifactPathError("Incomplete Excel", status_code=500)
                corrupt_member = workbook_zip.testzip()
                if corrupt_member is not None:
                    raise ArtifactPathError("Corrupt Excel", status_code=500)
        except ArtifactPathError:
            raise
        except zipfile.BadZipFile as exc:
            raise ArtifactPathError("Invalid Excel", status_code=500) from exc
    return resolved


def build_dual_artifact_metadata(
    *,
    selected_column_ids: list[str] | None,
    column_order: list[str] | None = None,
    configuration_source: str | None = None,
    run_id: str | None = None,
    report_slug: str | None = None,
) -> dict[str, Any]:
    order = list(column_order or selected_column_ids or [])
    metadata: dict[str, Any] = {
        "selected_column_ids": list(selected_column_ids or order),
        "column_order": order,
    }
    if configuration_source:
        metadata["configuration_source"] = configuration_source
    if run_id:
        metadata["run_id"] = run_id
    if report_slug:
        metadata["report_slug"] = report_slug
    return metadata


async def ensure_schema_columns(session: AsyncSession) -> None:
    """Best-effort SQLite column add for environments without alembic CLI."""
    from sqlalchemy import text

    statements = [
        "ALTER TABLE automation_runs ADD COLUMN result_json TEXT",
        "ALTER TABLE automation_artifacts ADD COLUMN report_slug VARCHAR(64)",
        "ALTER TABLE automation_artifacts ADD COLUMN status VARCHAR(32) DEFAULT 'ready'",
        "ALTER TABLE automation_artifacts ADD COLUMN metadata_json TEXT",
        "ALTER TABLE automation_runs ADD COLUMN date_from DATE",
        "ALTER TABLE automation_runs ADD COLUMN date_to DATE",
    ]
    for stmt in statements:
        try:
            await session.execute(text(stmt))
            await session.commit()
        except Exception:
            await session.rollback()


async def ensure_cdp_profile(session: AsyncSession) -> AutomationProfileModel:
    await ensure_schema_columns(session)
    result = await session.execute(
        select(AutomationProfileModel).where(
            AutomationProfileModel.slug == CDP_PROFILE_SLUG,
            AutomationProfileModel.is_deleted.is_(False),
        )
    )
    profile = result.scalar_one_or_none()
    if profile:
        return profile

    profile = AutomationProfileModel(
        id=str(uuid4()),
        name=CDP_PROFILE_NAME,
        slug=CDP_PROFILE_SLUG,
        portal_url=config.railmadad_url,
        username_encrypted="",
        password_encrypted="",
        download_folder="storage/downloads",
        browser="chromium",
        headless=False,
        timeout_ms=config.timeout * 1000,
        retry_count=1,
        delay_seconds=0,
        report_sequence_json=json.dumps(
            [
                "report1",
                "division",
                "train-no",
                "types",
                "scr-train",
                "scr-station",
            ]
        ),
        is_enabled=True,
        is_deleted=False,
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return profile


async def create_cdp_run(
    session: AsyncSession,
    *,
    user_id: str | None = None,
    run_id: str | None = None,
    trigger_type: str = "cdp_in_process",
    manual_config: dict | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> AutomationRunModel:
    from datetime import date as date_type

    profile = await ensure_cdp_profile(session)
    run = AutomationRunModel(
        id=run_id or str(uuid4()),
        profile_id=profile.id,
        status="running",
        trigger_type=trigger_type,
        started_at=datetime.now(UTC),
        created_by=user_id,
    )
    if date_from and date_to:
        run.date_from = date_type.fromisoformat(date_from)
        run.date_to = date_type.fromisoformat(date_to)
    if manual_config is not None:
        import json

        run.result_json = json.dumps({"manual_config": manual_config})
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def persist_run_progress(
    run_id: str,
    reports: list[ReportResult],
    *,
    status: str = "running",
) -> None:
    """Write mid-run result_json so GET /runs/{id} can power UI polling."""
    from app.infrastructure.database.session import SessionLocal

    terminal_or_control = {
        "paused",
        "pause_requested",
        "stopped",
        "cancel_requested",
        "completed",
        "failed",
    }

    try:
        async with SessionLocal() as session:
            run = await session.get(AutomationRunModel, run_id)
            if not run:
                return
            success = sum(1 for r in reports if r.status == "success")
            failed = sum(1 for r in reports if r.status in {"failed", "partial_success"})
            partial = MultiReportResult(
                success=False,
                connected=True,
                tab_found=True,
                reports=reports,
                run_id=run_id,
                reports_successful=success,
                reports_failed=failed,
                **merged_download_urls(run_id),
            )
            manual_config = None
            if run.result_json:
                try:
                    existing = json.loads(run.result_json)
                    if isinstance(existing, dict) and "manual_config" in existing:
                        manual_config = existing.get("manual_config")
                except Exception:
                    manual_config = None
            if manual_config is not None:
                run.result_json = json.dumps(
                    {"manual_config": manual_config, "result": partial.model_dump()}
                )
            else:
                run.result_json = partial.model_dump_json()
            run.success_count = success
            run.failure_count = failed
            # Never clobber pause/stop control states with mid-run "running".
            if status and run.status not in terminal_or_control:
                run.status = status
            elif status and status in terminal_or_control:
                run.status = status
            await session.commit()
            log_automation_event(
                logger,
                "progress_updated",
                run_id=run_id,
                reports_successful=success,
                reports_failed=failed,
                report_count=len(reports),
            )
    except Exception as exc:
        logger.warning("persist_run_progress failed: %s", exc)


async def finalize_cdp_run(
    session: AsyncSession,
    run_id: str,
    result: MultiReportResult,
    *,
    user_id: str | None = None,
) -> AutomationRunModel | None:
    run = await session.get(AutomationRunModel, run_id)
    if not run:
        return None
    success = sum(1 for r in result.reports if r.status == "success")
    failed = sum(1 for r in result.reports if r.status in {"failed", "partial_success"})
    user_stopped = bool(
        result.stopped_early and result.stop_reason == "USER_CANCELLED"
    ) or run.status == "stopped"
    if user_stopped:
        run.status = "stopped"
    elif result.success:
        run.status = "completed"
    elif success > 0 and failed > 0:
        run.status = "completed"
    elif success > 0:
        run.status = "completed"
    else:
        run.status = "failed"
    run.success_count = success
    run.failure_count = failed
    run.completed_at = datetime.now(UTC)
    run.error_message = result.error
    manual_config = None
    if run.result_json:
        try:
            import json

            existing = json.loads(run.result_json)
            if isinstance(existing, dict) and "manual_config" in existing:
                manual_config = existing.get("manual_config")
        except Exception:
            manual_config = None
    if manual_config is not None:
        import json

        run.result_json = json.dumps(
            {
                "manual_config": manual_config,
                "result": result.model_dump(),
            }
        )
    else:
        run.result_json = result.model_dump_json()
    await session.commit()
    await session.refresh(run)

    log_automation_event(
        logger,
        "run_terminal_status",
        run_id=run_id,
        run_status=run.status,
        reports_successful=success,
        reports_failed=failed,
        user_stopped=user_stopped,
    )

    actor = user_id or run.created_by
    if actor and not user_stopped:
        try:
            from app.features.activity.emit import emit_activity

            await emit_activity(
                user_id=actor,
                action="AUTOMATION_COMPLETED" if result.success else "AUTOMATION_FAILED",
                message=(
                    f"Automation finished: {success} succeeded, {failed} failed"
                    if result.success
                    else (result.error or "Automation failed")
                ),
                status="success" if result.success else "error",
                run_id=run_id,
                dedupe_key=f"automation_final:{run_id}",
                metadata={
                    "reports_successful": success,
                    "reports_failed": failed,
                    "total_duration_seconds": result.total_duration_seconds,
                },
            )
        except Exception:
            pass

    # Auto-generate Daily Summary after run reaches terminal state (non-blocking).
    if actor and run.trigger_type != "manual_report":
        try:
            from app.features.daily_summary.service import generate_daily_summary_after_run

            await generate_daily_summary_after_run(session, run_id, actor)
        except Exception:
            logger.exception("finalize_cdp_run daily summary hook failed run_id=%s", run_id)

    return run


async def mark_run_stopped(
    session: AsyncSession,
    run_id: str,
    *,
    user_id: str | None = None,
    error_message: str = "Report generation stopped by user",
    intermediate: bool = False,
) -> AutomationRunModel | None:
    """Mark a CDP run stopped (or cancel_requested) without wiping artifacts."""
    run = await session.get(AutomationRunModel, run_id)
    if not run:
        return None
    if run.status in {"completed", "failed", "stopped"}:
        return run
    run.status = "cancel_requested" if intermediate else "stopped"
    if not intermediate:
        run.completed_at = datetime.now(UTC)
    run.error_message = error_message
    await session.commit()
    await session.refresh(run)

    actor = user_id or run.created_by
    if actor and not intermediate:
        try:
            from app.features.activity.emit import emit_activity

            await emit_activity(
                user_id=actor,
                action="AUTOMATION_STOPPED",
                message="Report generation stopped by user",
                status="warning",
                run_id=run_id,
                dedupe_key=f"automation_stopped:{run_id}",
            )
        except Exception:
            pass
    return run


async def set_run_status(
    session: AsyncSession,
    run_id: str,
    status: str,
    *,
    user_id: str | None = None,
    activity_action: str | None = None,
    activity_message: str | None = None,
) -> AutomationRunModel | None:
    run = await session.get(AutomationRunModel, run_id)
    if not run:
        return None
    if run.status in {"completed", "failed", "stopped"} and status not in {
        "completed",
        "failed",
        "stopped",
    }:
        return run
    run.status = status
    if status in {"stopped", "completed", "failed"} and run.completed_at is None:
        run.completed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(run)

    actor = user_id or run.created_by
    if actor and activity_action and activity_message:
        try:
            from app.features.activity.emit import emit_activity

            await emit_activity(
                user_id=actor,
                action=activity_action,
                message=activity_message,
                status="warning" if "stop" in activity_action.lower() or "pause" in activity_action.lower() else "info",
                run_id=run_id,
                dedupe_key=f"{activity_action.lower()}:{run_id}:{status}",
            )
        except Exception:
            pass
    return run


async def register_artifact(
    session: AsyncSession,
    *,
    run_id: str,
    report_slug: str,
    report_name: str | None,
    file_type: str,
    file_path: str | Path,
    status: str = "ready",
    metadata: dict[str, Any] | None = None,
) -> AutomationArtifactModel | None:
    path = Path(file_path)
    run = await session.get(AutomationRunModel, run_id)
    min_mtime: float | None = None
    if run and run.started_at:
        started = run.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        min_mtime = started.timestamp() - 2.0

    try:
        validated = validate_artifact_file(
            path,
            require_pdf_header=(file_type == "pdf"),
            file_type=file_type,
            min_mtime=min_mtime,
        )
        size = validated.stat().st_size
        final_status = status
    except ArtifactPathError:
        validated = path
        size = 0
        final_status = "missing"

    artifact = AutomationArtifactModel(
        id=str(uuid4()),
        run_id=run_id,
        artifact_type=file_type,
        file_path=str(validated),
        file_size_bytes=size,
        report_name=report_name or report_slug,
        report_slug=canonicalize_report_key(report_slug),
        status=final_status,
        metadata_json=json.dumps(metadata) if metadata else None,
    )
    session.add(artifact)
    await session.commit()
    await session.refresh(artifact)
    log_automation_event(
        logger,
        "artifact_registered",
        run_id=run_id,
        artifact_id=artifact.id,
        report_slug=artifact.report_slug,
        file_type=file_type,
        status=final_status,
        file_size=size,
    )
    if final_status == "ready" and file_type in {"excel", "pdf"}:
        try:
            run = await session.get(AutomationRunModel, run_id)
            actor = run.created_by if run else None
            if actor:
                from app.features.activity.emit import emit_activity

                kind = "EXCEL_GENERATED" if file_type == "excel" else "PDF_GENERATED"
                await emit_activity(
                    user_id=actor,
                    action=kind,
                    message=f"{file_type.upper()} generated for {artifact.report_slug}",
                    status="success",
                    report_slug=artifact.report_slug,
                    run_id=run_id,
                    dedupe_key=f"{file_type}_generated:{artifact.id}",
                    metadata={"artifact_id": artifact.id, "file_type": file_type},
                )
        except Exception:
            pass
    return artifact


async def get_artifact(
    session: AsyncSession, artifact_id: str
) -> AutomationArtifactModel | None:
    return await session.get(AutomationArtifactModel, artifact_id)


async def list_run_artifacts(
    session: AsyncSession, run_id: str
) -> list[AutomationArtifactModel]:
    result = await session.execute(
        select(AutomationArtifactModel)
        .where(AutomationArtifactModel.run_id == run_id)
        .order_by(AutomationArtifactModel.created_at.desc())
    )
    return list(result.scalars().all())


def artifact_public_dict(artifact: AutomationArtifactModel) -> dict[str, Any]:
    return {
        "id": artifact.id,
        "run_id": artifact.run_id,
        "report_slug": artifact.report_slug,
        "report_name": artifact.report_name,
        "file_type": artifact.artifact_type,
        "file_size": artifact.file_size_bytes,
        "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
        "status": artifact.status or "ready",
        "preview_url": (
            f"/api/v1/automation/artifacts/{artifact.id}/preview"
            if artifact.artifact_type == "pdf"
            else None
        ),
        "download_url": f"/api/v1/automation/artifacts/{artifact.id}/download",
    }


_PATH_FIELDS = (
    "excel_path",
    "pdf_path",
    "source_paths",
    "source_csv_path",
    "archive_path",
    "source_a_path",
    "source_b_path",
)


def public_report_dict(report: ReportResult | dict[str, Any]) -> dict[str, Any]:
    """Serialize a report result without exposing filesystem paths."""
    data = report.model_dump() if isinstance(report, ReportResult) else dict(report)
    for key in _PATH_FIELDS:
        data.pop(key, None)
    return data


def scrub_multi_result(result: MultiReportResult) -> MultiReportResult:
    """Return a copy of MultiReportResult safe for API clients."""
    scrubbed = result.model_copy(deep=True)
    scrubbed.reports = [
        ReportResult(**public_report_dict(r)) for r in result.reports
    ]
    return scrubbed



def enrich_report_urls(result: ReportResult, artifact_ids: dict[str, str]) -> ReportResult:
    """Attach artifact-based URLs onto a ReportResult."""
    pdf_id = artifact_ids.get("pdf")
    excel_id = artifact_ids.get("excel")
    data = result.model_dump()
    if pdf_id:
        data["pdf_download_url"] = f"/api/v1/automation/artifacts/{pdf_id}/download"
        data["pdf_preview_url"] = f"/api/v1/automation/artifacts/{pdf_id}/preview"
    if excel_id:
        data["excel_download_url"] = f"/api/v1/automation/artifacts/{excel_id}/download"
    return ReportResult(**data)
