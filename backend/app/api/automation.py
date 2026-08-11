"""API routes for in-process browser automation and run artifacts."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.automation.browser import BrowserConnectionError, probe_cdp_reachable
from app.automation.config import config
from app.automation.dependencies import get_automation_service
from app.automation.report_keys import canonicalize_report_key
from app.automation.merged_downloads import (
    MergedDownloadError,
    build_merged_excel,
    build_merged_pdf,
    merged_excel_filename,
    merged_pdf_filename,
)
from app.automation.merged_report_catalog import merged_download_urls
from app.automation.run_registry import (
    ArtifactPathError,
    artifact_public_dict,
    get_artifact,
    list_run_artifacts,
    public_report_dict,
    scrub_multi_result,
    validate_artifact_file,
)
from app.automation.schemas import MultiReportResult
from app.automation.service import AutomationService
from app.domain.entities.user import User
from app.features.auth.dependencies import require_admin, require_officer_or_admin, validate_csrf_token
from app.infrastructure.database.models import AutomationRunModel
from app.infrastructure.database.session import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/automation", tags=["automation"])

ALLOWED_PDF_KEYS = frozenset(
    {
        "report1",
        "division",
        "train-no",
        "types",
        "scr-train",
        "scr-station",
        "report9",
        "comprehensive-10-13",
        "report14",
        "report18",
        "bottom-report",
    }
)


class ArtifactMeta(BaseModel):
    id: str
    run_id: str
    report_slug: str | None = None
    report_name: str | None = None
    file_type: str
    file_size: int | None = None
    created_at: str | None = None
    status: str = "ready"
    preview_url: str | None = None
    download_url: str | None = None


class RunDetailResponse(BaseModel):
    run_id: str
    status: str
    started_at: str | None = None
    completed_at: str | None = None
    success_count: int = 0
    failure_count: int = 0
    error: str | None = None
    total_duration_seconds: float | None = None
    reports_successful: int = 0
    reports_failed: int = 0
    download_pdf_all_url: str | None = None
    download_excel_all_url: str | None = None
    reports: list[dict[str, Any]] = Field(default_factory=list)
    result: MultiReportResult | None = None


class StartAutomationRequest(BaseModel):
    report_slugs: list[str] | None = None
    async_mode: bool = False
    date_from: str | None = None
    date_to: str | None = None


class StartAcceptedResponse(BaseModel):
    run_id: str
    status: str = "running"
    message: str = "Automation started"
    success: bool = True
    connected: bool = False
    tab_found: bool = False
    reports: list[dict[str, Any]] = Field(default_factory=list)


def _resolve_latest_pdf(report_key: str) -> Path:
    """Resolve the newest PDF under storage/output/pdf/{canonical_key}/."""
    canonical = canonicalize_report_key(report_key)
    if canonical not in ALLOWED_PDF_KEYS:
        raise HTTPException(status_code=404, detail=f"Unknown report key: {report_key}")

    base = Path(config.output_pdf_dir).resolve()
    report_dir = (base / canonical).resolve()
    if not str(report_dir).startswith(str(base)):
        raise HTTPException(status_code=400, detail="Invalid report path")
    if not report_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"No PDF directory for {canonical}")

    pdfs = sorted(report_dir.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not pdfs:
        raise HTTPException(status_code=404, detail=f"No PDF found for {canonical}")

    pdf_path = pdfs[0]
    if pdf_path.stat().st_size <= 0:
        raise HTTPException(status_code=404, detail=f"PDF empty for {canonical}")

    header = pdf_path.read_bytes()[:5]
    if header != b"%PDF-":
        raise HTTPException(status_code=500, detail=f"Invalid PDF header for {canonical}")

    return pdf_path


def _validate_date_range(date_from: str | None, date_to: str | None) -> None:
    """Validate date_from/date_to parameters; raises HTTPException 422 on failure."""
    if (date_from is None) != (date_to is None):
        raise HTTPException(
            status_code=422,
            detail="Both date_from and date_to are required when specifying a date range",
        )
    if date_from is None:
        return

    import re
    from datetime import date as date_type

    iso_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    if not iso_pattern.match(date_from) or not iso_pattern.match(date_to):
        raise HTTPException(
            status_code=422,
            detail="date_from and date_to must be in YYYY-MM-DD format",
        )

    try:
        from_date = date_type.fromisoformat(date_from)
        to_date = date_type.fromisoformat(date_to)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid date value: {exc}",
        ) from exc

    if from_date > to_date:
        raise HTTPException(
            status_code=422,
            detail="date_from must not be after date_to",
        )


@router.post(
    "/start",
    dependencies=[Depends(require_admin), Depends(validate_csrf_token)],
)
async def start_automation(
    service: Annotated[AutomationService, Depends(get_automation_service)],
    _user: Annotated[User, Depends(require_admin)],
    body: StartAutomationRequest = StartAutomationRequest(),
) -> MultiReportResult | StartAcceptedResponse:
    """Connect to Chrome via CDP and run catalog reports.

    When ``async_mode`` is true, returns ``run_id`` immediately; poll GET /runs/{id}.
    """
    _validate_date_range(body.date_from, body.date_to)

    report_slugs = body.report_slugs
    if body.async_mode:
        try:
            await probe_cdp_reachable(config.chrome_debug_url)
        except BrowserConnectionError as exc:
            logger.warning("Automation async start blocked: CDP unreachable at %s", config.chrome_debug_url)
            return MultiReportResult(
                success=False,
                connected=False,
                tab_found=False,
                error=exc.message,
                error_code=exc.code,
            )
        run_id, status = await service.start_async(
            user_id=_user.id,
            report_slugs=report_slugs,
            date_from=body.date_from,
            date_to=body.date_to,
        )
        logger.info(
            "Automation async start: run_id=%s date_from=%s date_to=%s",
            run_id,
            body.date_from,
            body.date_to,
        )
        return StartAcceptedResponse(run_id=run_id, status=status)

    try:
        result = await service.start(
            user_id=_user.id,
            report_slugs=report_slugs,
            date_from=body.date_from,
            date_to=body.date_to,
        )
    except Exception as exc:
        logger.exception("Unexpected automation start failure")
        raise HTTPException(status_code=500, detail="Automation failed to start") from exc

    logger.info(
        "Automation start completed: success=%s connected=%s tab_found=%s report_count=%s run_id=%s",
        result.success,
        result.connected,
        result.tab_found,
        len(result.reports),
        result.run_id,
    )
    return scrub_multi_result(result)


@router.get(
    "/reports/{report_key}/pdf",
    dependencies=[Depends(require_admin)],
)
async def download_report_pdf(
    report_key: str,
    _user: Annotated[User, Depends(require_admin)],
) -> FileResponse:
    """Download the latest final PDF for a report (restricted to storage/output/pdf)."""
    pdf_path = _resolve_latest_pdf(report_key)
    logger.info("Serving PDF for %s: %s", report_key, pdf_path)
    try:
        from app.features.activity.emit import emit_activity

        canonical = canonicalize_report_key(report_key)
        await emit_activity(
            user_id=_user.id,
            action="PDF_DOWNLOADED",
            message=f"Downloaded latest PDF for {canonical}",
            status="success",
            report_slug=canonical,
            dedupe_key=f"pdf_latest_downloaded:{canonical}:{pdf_path.name}",
            metadata={"filename": pdf_path.name},
        )
    except Exception:
        pass
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=pdf_path.name,
        content_disposition_type="attachment",
    )


@router.get(
    "/runs/{run_id}",
    response_model=RunDetailResponse,
    dependencies=[Depends(require_admin)],
)
async def get_run(
    run_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    _user: Annotated[User, Depends(require_admin)],
) -> RunDetailResponse:
    from app.automation.reports import catalog

    run = await db.get(AutomationRunModel, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    result: MultiReportResult | None = None
    reports: list[dict[str, Any]] = []
    total_duration = None
    if run.result_json:
        try:
            parsed = MultiReportResult.model_validate_json(run.result_json)
            result = scrub_multi_result(parsed)
            reports = [public_report_dict(r) for r in result.reports]
            total_duration = result.total_duration_seconds
        except Exception:
            result = None

    # For in-progress runs, include all expected reports with "waiting" status for those not yet processed
    if run.status in ("running", "pending", "queued", "paused", "pause_requested"):
        processed_slugs = {r.get("slug") for r in reports}
        for catalog_report in catalog.reports:
            if catalog_report.slug not in processed_slugs:
                reports.append({
                    "slug": catalog_report.slug,
                    "dataset_key": catalog_report.slug,
                    "status": "waiting",
                    "error": None,
                })

    # Enrich missing URLs from registered artifacts
    try:
        artifacts = await list_run_artifacts(db, run_id)
        by_slug: dict[str, dict[str, str]] = {}
        for art in artifacts:
            slug = art.report_slug or ""
            bucket = by_slug.setdefault(slug, {})
            # Artifacts are newest-first; keep the first id per slug/type.
            if art.artifact_type not in bucket:
                bucket[art.artifact_type] = art.id
        for report in reports:
            slug = report.get("slug") or ""
            ids = by_slug.get(slug) or {}
            if ids.get("pdf") and not report.get("pdf_download_url"):
                report["pdf_download_url"] = f"/api/v1/automation/artifacts/{ids['pdf']}/download"
                report["pdf_preview_url"] = f"/api/v1/automation/artifacts/{ids['pdf']}/preview"
            if ids.get("excel") and not report.get("excel_download_url"):
                report["excel_download_url"] = (
                    f"/api/v1/automation/artifacts/{ids['excel']}/download"
                )
    except Exception:
        pass

    return RunDetailResponse(
        run_id=run.id,
        status=run.status,
        started_at=run.started_at.isoformat() if run.started_at else None,
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        success_count=run.success_count,
        failure_count=run.failure_count,
        error=run.error_message,
        total_duration_seconds=total_duration,
        reports_successful=result.reports_successful if result else run.success_count,
        reports_failed=result.reports_failed if result else run.failure_count,
        **merged_download_urls(run.id),
        reports=reports,
        result=result,
    )


class StopRunResponse(BaseModel):
    success: bool
    status: str
    message: str
    run_id: str


@router.post(
    "/runs/{run_id}/stop",
    response_model=StopRunResponse,
    dependencies=[Depends(require_admin), Depends(validate_csrf_token)],
)
async def stop_run(
    run_id: str,
    service: Annotated[AutomationService, Depends(get_automation_service)],
    _user: Annotated[User, Depends(require_admin)],
) -> StopRunResponse:
    """Stop an in-process CDP run at the next report checkpoint."""
    result = await service.stop(run_id, user_id=_user.id)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Run not found")
    return StopRunResponse(
        success=bool(result["success"]),
        status=str(result["status"]),
        message=str(result["message"]),
        run_id=str(result["run_id"]),
    )


@router.post(
    "/runs/{run_id}/pause",
    response_model=StopRunResponse,
    dependencies=[Depends(require_admin), Depends(validate_csrf_token)],
)
async def pause_run(
    run_id: str,
    service: Annotated[AutomationService, Depends(get_automation_service)],
    _user: Annotated[User, Depends(require_admin)],
) -> StopRunResponse:
    """Pause an in-process CDP run at the next cooperative checkpoint."""
    result = await service.pause(run_id, user_id=_user.id)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Run not found")
    if not result.get("success"):
        raise HTTPException(status_code=409, detail=str(result.get("message")))
    return StopRunResponse(
        success=bool(result["success"]),
        status=str(result["status"]),
        message=str(result["message"]),
        run_id=str(result["run_id"]),
    )


@router.post(
    "/runs/{run_id}/resume",
    response_model=StopRunResponse,
    dependencies=[Depends(require_admin), Depends(validate_csrf_token)],
)
async def resume_run(
    run_id: str,
    service: Annotated[AutomationService, Depends(get_automation_service)],
    _user: Annotated[User, Depends(require_admin)],
) -> StopRunResponse:
    """Resume a paused in-process CDP run."""
    result = await service.resume(run_id, user_id=_user.id)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Run not found")
    if not result.get("success"):
        raise HTTPException(status_code=409, detail=str(result.get("message")))
    return StopRunResponse(
        success=bool(result["success"]),
        status=str(result["status"]),
        message=str(result["message"]),
        run_id=str(result["run_id"]),
    )


@router.get(
    "/runs/{run_id}/artifacts",
    response_model=list[ArtifactMeta],
    dependencies=[Depends(require_admin)],
)
async def get_run_artifacts(
    run_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    _user: Annotated[User, Depends(require_admin)],
) -> list[ArtifactMeta]:
    run = await db.get(AutomationRunModel, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    artifacts = await list_run_artifacts(db, run_id)
    return [ArtifactMeta(**artifact_public_dict(a)) for a in artifacts]


@router.get(
    "/artifacts/{artifact_id}/preview",
    dependencies=[Depends(require_officer_or_admin)],
)
async def preview_artifact(
    artifact_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    _user: Annotated[User, Depends(require_officer_or_admin)],
) -> FileResponse:
    artifact = await get_artifact(db, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    if artifact.artifact_type != "pdf":
        raise HTTPException(status_code=400, detail="Only PDF artifacts support preview")
    run = await db.get(AutomationRunModel, artifact.run_id)
    if run and run.created_by and run.created_by != _user.id and not _user.can_access_admin():
        raise HTTPException(status_code=403, detail="Artifact not accessible")
    try:
        path = validate_artifact_file(
            Path(artifact.file_path),
            require_pdf_header=True,
            file_type="pdf",
        )
    except ArtifactPathError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    try:
        from app.features.activity.emit import emit_activity

        await emit_activity(
            user_id=_user.id,
            action="PDF_PREVIEWED",
            message=f"Previewed PDF for {artifact.report_slug or 'report'}",
            status="info",
            report_slug=artifact.report_slug,
            run_id=artifact.run_id,
            dedupe_key=f"pdf_previewed:{artifact_id}",
            metadata={"artifact_id": artifact_id},
        )
    except Exception:
        pass
    return FileResponse(
        path=str(path),
        media_type="application/pdf",
        filename=path.name,
        content_disposition_type="inline",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@router.get(
    "/artifacts/{artifact_id}/download",
    dependencies=[Depends(require_officer_or_admin)],
)
async def download_artifact(
    artifact_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    _user: Annotated[User, Depends(require_officer_or_admin)],
) -> FileResponse:
    artifact = await get_artifact(db, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    run = await db.get(AutomationRunModel, artifact.run_id)
    if run and run.created_by and run.created_by != _user.id and not _user.can_access_admin():
        raise HTTPException(status_code=403, detail="Artifact not accessible")
    try:
        path = validate_artifact_file(
            Path(artifact.file_path),
            require_pdf_header=artifact.artifact_type == "pdf",
            file_type=artifact.artifact_type,
        )
    except ArtifactPathError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    if artifact.artifact_type == "pdf" and path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="PDF suffix required")

    media = (
        "application/pdf"
        if artifact.artifact_type == "pdf"
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    try:
        from app.features.activity.emit import emit_activity

        action = (
            "PDF_DOWNLOADED" if artifact.artifact_type == "pdf" else "EXCEL_DOWNLOADED"
        )
        await emit_activity(
            user_id=_user.id,
            action=action,
            message=f"Downloaded {artifact.artifact_type} for {artifact.report_slug or 'report'}",
            status="success",
            report_slug=artifact.report_slug,
            run_id=artifact.run_id,
            dedupe_key=f"{artifact.artifact_type}_downloaded:{artifact_id}",
            metadata={"artifact_id": artifact_id},
        )
    except Exception:
        pass
    return FileResponse(
        path=str(path),
        media_type=media,
        filename=path.name,
        content_disposition_type="attachment",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@router.get(
    "/runs/{run_id}/download/pdf/all",
    dependencies=[Depends(require_admin)],
)
async def download_merged_pdf_all(
    run_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    _user: Annotated[User, Depends(require_admin)],
) -> Response:
    run = await db.get(AutomationRunModel, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    artifacts = await list_run_artifacts(db, run_id)
    generated_at = run.completed_at or run.started_at
    try:
        payload = build_merged_pdf(
            artifacts,
            run_id=run_id,
            generated_at=generated_at,
        )
    except MergedDownloadError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Merged PDF build failed for run %s", run_id)
        raise HTTPException(
            status_code=500, detail=f"Failed to build merged PDF: {exc}"
        ) from exc
    try:
        from app.features.activity.emit import emit_activity

        await emit_activity(
            user_id=_user.id,
            action="PDF_DOWNLOADED",
            message=f"Downloaded merged PDF for run {run_id}",
            status="success",
            run_id=run_id,
            dedupe_key=f"merged_pdf_downloaded:{run_id}",
            metadata={"artifact_count": len(artifacts)},
        )
    except Exception:
        pass
    filename = merged_pdf_filename(now=generated_at)
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store, no-cache, must-revalidate",
        },
    )


@router.get(
    "/runs/{run_id}/download/excel/all",
    dependencies=[Depends(require_admin)],
)
async def download_merged_excel_all(
    run_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    _user: Annotated[User, Depends(require_admin)],
) -> Response:
    run = await db.get(AutomationRunModel, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    artifacts = await list_run_artifacts(db, run_id)
    generated_at = run.completed_at or run.started_at
    try:
        payload = build_merged_excel(artifacts)
    except MergedDownloadError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Merged Excel build failed for run %s", run_id)
        raise HTTPException(
            status_code=500, detail=f"Failed to build merged Excel: {exc}"
        ) from exc
    try:
        from app.features.activity.emit import emit_activity

        await emit_activity(
            user_id=_user.id,
            action="EXCEL_DOWNLOADED",
            message=f"Downloaded merged Excel for run {run_id}",
            status="success",
            run_id=run_id,
            dedupe_key=f"merged_excel_downloaded:{run_id}",
            metadata={"artifact_count": len(artifacts)},
        )
    except Exception:
        pass
    filename = merged_excel_filename(now=generated_at)
    return Response(
        content=payload,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store, no-cache, must-revalidate",
        },
    )


@router.get(
    "/cdp-runs",
    dependencies=[Depends(require_admin)],
)
async def list_cdp_runs(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    _user: Annotated[User, Depends(require_admin)],
    limit: int = 20,
) -> list[dict[str, Any]]:
    """List recent in-process CDP automation runs."""
    result = await db.execute(
        select(AutomationRunModel)
        .where(AutomationRunModel.trigger_type == "cdp_in_process")
        .order_by(AutomationRunModel.created_at.desc())
        .limit(limit)
    )
    runs = list(result.scalars().all())
    return [
        {
            "run_id": r.id,
            "status": r.status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "success_count": r.success_count,
            "failure_count": r.failure_count,
            **merged_download_urls(r.id),
        }
        for r in runs
    ]
