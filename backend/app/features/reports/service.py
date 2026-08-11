"""Manual report generation service."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.automation.processing.column_config import (
    COMPREHENSIVE_REPORT_SLUG,
    extract_comprehensive_sections_payload,
    is_columnless_manual_report,
    output_column_catalog,
    projection_labels_for_slug,
    resolve_projection_column_keys,
    sanitize_comprehensive_sections,
    sanitize_projection_keys,
    validate_column_order,
    validate_projection_selection,
)
from app.automation.processing.comprehensive_output_columns import (
    build_comprehensive_column_snapshot,
    validate_comprehensive_artifact_metadata,
    validate_comprehensive_sections,
)
from app.automation.processing.scr_output_columns import SCR_NAMESPACED_SLUGS
from app.automation.processing.topn_output_columns import TOPN_REPORT_SLUGS
from app.automation.config import config
from app.automation.service import AutomationService
from app.automation.run_registry import get_artifact, list_run_artifacts
from app.automation.schemas import MultiReportResult, ReportResult
from app.automation.utils import previous_day_report_date
from app.automation.date_range import DateRangeValidationError, ReportDateRange
from app.features.reports.config_store import (
    default_projection_keys,
    load_report_config,
    save_report_config,
)
from app.features.reports.preview import read_preview_rows
from app.features.reports.preview_projection import build_output_preview
from app.features.reports.schemas import (
    ManualGenerateRequest,
    ManualGenerateResponse,
    ManualRunStatusResponse,
    OutputPreviewRequest,
    OutputPreviewResponse,
    ReportConfigResponse,
    SaveReportConfigRequest,
    SaveReportConfigResponse,
)
from app.features.reports.scr_fresh import (
    log_manual_fresh_started,
    validate_manual_scr_column_snapshot,
)
from app.features.reports.slug_map import is_manual_report_slug, resolve_manual_slug
from app.automation.report_keys import canonicalize_report_key
from app.features.reports.status import extraction_success, map_manual_status
from app.features.reports.topn_manual import has_valid_topn_dataset, start_topn_process_only_async
from app.infrastructure.database.models import AutomationRunModel

logger = logging.getLogger(__name__)

MANUAL_TRIGGER = "manual_report"


def build_config_snapshot(
    body: ManualGenerateRequest,
    *,
    report_slug: str,
    configuration_source: str = "manual_snapshot",
    user_id: str | None = None,
) -> dict[str, Any]:
    slug = canonicalize_report_key(report_slug)
    try:
        date_range = ReportDateRange.from_iso(str(body.date_from), str(body.date_to))
    except DateRangeValidationError as exc:
        raise ValueError(str(exc)) from exc

    if slug == COMPREHENSIVE_REPORT_SLUG:
        raw_sections = body.sections or extract_comprehensive_sections_payload(body.model_dump())
        if not raw_sections:
            raise ValueError("Report 10-13 requires column selections for all four sections.")
        column_snapshot = build_comprehensive_column_snapshot(
            raw_sections,
            date_from=date_range.iso_from(),
            date_to=date_range.iso_to(),
            configuration_source=configuration_source,
        )
        snapshot: dict[str, Any] = {
            **column_snapshot,
            "export_format": body.export_format,
            "config_overrides": dict(body.config_overrides),
            "filter_conditions": list(body.filter_conditions),
            "report_date": date_range.legacy_report_date(),
            "snapshot_created_at": datetime.now(UTC).isoformat(),
        }
        snapshot.update(date_range.snapshot_fields())
        if body.requested_formats:
            snapshot["requested_formats"] = list(body.requested_formats)
        if body.force_fresh_extraction:
            snapshot["force_fresh_extraction"] = True
        return snapshot

    if is_columnless_manual_report(slug):
        snapshot = {
            "selected_column_ids": [],
            "column_order": [],
            "export_format": body.export_format,
            "config_overrides": dict(body.config_overrides),
            "filter_conditions": list(body.filter_conditions),
            "report_date": date_range.legacy_report_date(),
            "configuration_source": configuration_source,
            "snapshot_created_at": datetime.now(UTC).isoformat(),
        }
        snapshot.update(date_range.snapshot_fields())
        if body.requested_formats:
            snapshot["requested_formats"] = list(body.requested_formats)
        if body.force_fresh_extraction:
            snapshot["force_fresh_extraction"] = True
        return snapshot

    column_order = body.column_order or body.selected_column_ids
    if column_order:
        keys = sanitize_projection_keys(column_order, report_slug, user_id=user_id)
    else:
        keys, _source = resolve_projection_column_keys(
            report_slug,
            user_id=user_id,
            column_selection={
                "report_slug": report_slug,
                "selected_column_ids": body.selected_column_ids,
                "column_order": body.column_order,
                "configuration_source": configuration_source,
            },
        )
    validate_projection_selection(report_slug, keys)
    if body.selected_column_ids:
        selected = sanitize_projection_keys(body.selected_column_ids, report_slug, user_id=user_id)
        validate_column_order(report_slug, selected, keys)
    snapshot = {
        "selected_column_ids": list(keys),
        "column_order": list(keys),
        "export_format": body.export_format,
        "config_overrides": dict(body.config_overrides),
        "filter_conditions": list(body.filter_conditions),
        "report_date": date_range.legacy_report_date(),
        "configuration_source": configuration_source,
        "snapshot_created_at": datetime.now(UTC).isoformat(),
    }
    snapshot.update(date_range.snapshot_fields())
    if body.requested_formats:
        snapshot["requested_formats"] = list(body.requested_formats)
    if body.force_fresh_extraction:
        snapshot["force_fresh_extraction"] = True
    return snapshot


def _parse_manual_config(run: AutomationRunModel) -> dict[str, Any]:
    if not run.result_json:
        return {}
    try:
        payload = json.loads(run.result_json)
    except json.JSONDecodeError:
        return {}
    if isinstance(payload, dict) and "manual_config" in payload:
        return payload.get("manual_config") or {}
    return {}


def _parse_result(run: AutomationRunModel) -> MultiReportResult | None:
    if not run.result_json:
        return None
    try:
        payload = json.loads(run.result_json)
        if isinstance(payload, dict) and "manual_config" in payload and "result" in payload:
            return MultiReportResult.model_validate(payload["result"])
        return MultiReportResult.model_validate_json(run.result_json)
    except Exception:
        return None


def _find_report(result: MultiReportResult | None, slug: str) -> ReportResult | None:
    if not result:
        return None
    for report in result.reports:
        if report.slug == slug:
            return report
    return result.reports[0] if len(result.reports) == 1 else None


DUAL_ARTIFACT_SLUGS = frozenset(
    {
        "report1",
        "division",
        "scr-train",
        "scr-station",
        "train-no",
        "types",
        "report9",
        "comprehensive-10-13",
        "report14",
        "report18",
        "bottom-report",
    }
)


def _artifact_for_format(
    artifacts: list,
    *,
    slug: str,
    export_format: str,
) -> Any | None:
    want_type = "pdf" if export_format == "pdf" else "excel"
    for art in artifacts:
        if art.report_slug == slug and art.artifact_type == want_type and art.status == "ready":
            return art
    return None


def _artifacts_for_slug(
    artifacts: list,
    *,
    slug: str,
    manual_config: dict[str, Any] | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Return ready excel/pdf artifacts for a report slug, preferring matching snapshot."""
    from app.features.reports.slug_map import resolve_manual_slug

    resolved_slug = resolve_manual_slug(slug)
    expected_hash = manual_config.get("snapshot_hash") if manual_config else None

    candidates: dict[str, list[Any]] = {"excel": [], "pdf": []}
    for art in artifacts:
        if art.report_slug != resolved_slug or art.status != "ready":
            continue
        if art.artifact_type not in {"excel", "pdf"} or (art.file_size_bytes or 0) <= 0:
            continue
        candidates[art.artifact_type].append(art)

    found: dict[str, Any] = {}
    for art_type, arts in candidates.items():
        if not arts:
            continue
        preferred = None
        for art in arts:
            meta = _parse_artifact_metadata(art)
            if run_id and meta.get("run_id") and str(meta["run_id"]) != str(run_id):
                continue
            if expected_hash and meta.get("snapshot_hash") and meta["snapshot_hash"] == expected_hash:
                preferred = art
                break
        found[art_type] = preferred or arts[0]
    return found


def _artifact_is_ready(art: Any | None) -> bool:
    return art is not None and art.status == "ready" and (art.file_size_bytes or 0) > 0


def _parse_artifact_metadata(art: Any | None) -> dict[str, Any]:
    if art is None:
        return {}
    raw = getattr(art, "metadata_json", None)
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _column_snapshot(metadata: dict[str, Any]) -> list[str] | None:
    if not metadata:
        return None
    order = metadata.get("column_order") or metadata.get("selected_column_ids")
    if order is None:
        return None
    return list(order)


def _dual_artifacts_metadata_consistent(
    excel_art: Any | None,
    pdf_art: Any | None,
    manual_config: dict[str, Any],
    *,
    run_id: str | None = None,
    report_slug: str | None = None,
) -> tuple[bool, str | None]:
    from app.features.reports.slug_map import resolve_manual_slug

    excel_meta = _parse_artifact_metadata(excel_art)
    pdf_meta = _parse_artifact_metadata(pdf_art)

    if report_slug and resolve_manual_slug(report_slug) == COMPREHENSIVE_REPORT_SLUG:
        if excel_art is None or pdf_art is None:
            return False, "Report 10–13: Excel or PDF artifact missing."
        for art, meta in ((excel_art, excel_meta), (pdf_art, pdf_meta)):
            path = Path(getattr(art, "file_path", "") or "")
            if not path.is_file() or path.stat().st_size <= 0:
                return False, "Report 10–13: generated artifact file is missing or empty."
        ok, err = validate_comprehensive_artifact_metadata(
            excel_meta,
            pdf_meta,
            manual_config,
            run_id=run_id,
        )
        return ok, err

    expected = manual_config.get("column_order") or manual_config.get("selected_column_ids")
    expected_list = list(expected) if expected else None

    excel_snap = _column_snapshot(excel_meta)
    pdf_snap = _column_snapshot(pdf_meta)

    if excel_snap is not None or pdf_snap is not None:
        if excel_snap is None or pdf_snap is None or excel_snap != pdf_snap:
            return False, "Artifact column snapshot mismatch"
        if expected_list is not None and excel_snap != expected_list:
            return False, "Artifact column snapshot mismatch"

    for art, meta in ((excel_art, excel_meta), (pdf_art, pdf_meta)):
        if art is None:
            continue
        path = Path(getattr(art, "file_path", "") or "")
        if not path.is_file() or path.stat().st_size <= 0:
            return False, "Artifact column snapshot mismatch"
        art_slug = getattr(art, "report_slug", None) or meta.get("report_slug")
        if report_slug and art_slug:
            if resolve_manual_slug(str(art_slug)) != resolve_manual_slug(report_slug):
                return False, "Artifact column snapshot mismatch"
        if run_id and meta.get("run_id") and str(meta["run_id"]) != str(run_id):
            return False, "Artifact column snapshot mismatch"

    return True, None


class ManualReportService:
    async def get_report_config(
        self,
        slug_or_page_id: str,
        *,
        user_id: str | None = None,
    ) -> ReportConfigResponse:
        slug = resolve_manual_slug(slug_or_page_id)
        if not is_manual_report_slug(slug):
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "INVALID_REPORT_SLUG",
                    "message": f"Unknown report slug: {slug_or_page_id}",
                },
            )

        catalog = await self.get_output_columns(slug)
        available_columns = catalog["columns"]
        default_ids = list(catalog["default_column_ids"])
        saved = load_report_config(slug, user_id=user_id)
        has_saved = saved is not None

        # Only non-empty when the user has explicitly saved default filters.
        saved_default_ids = sanitize_projection_keys(
            list((saved or {}).get("default_selected_column_ids") or []),
            slug,
            user_id=user_id,
        )
        effective_defaults = saved_default_ids or default_ids

        if saved:
            # New runs prefer user-saved defaults; otherwise keep last selection / catalog.
            order = (
                saved_default_ids
                or saved.get("column_order")
                or saved.get("selected_column_ids")
                or effective_defaults
            )
            selected = (
                saved_default_ids
                or saved.get("selected_column_ids")
                or order
            )
            keys = sanitize_projection_keys(order, slug, user_id=user_id)
            if not keys:
                keys = list(effective_defaults)
            selected_keys = sanitize_projection_keys(selected, slug, user_id=user_id) or keys
        else:
            keys = default_projection_keys(slug) or default_ids
            selected_keys = list(keys)

        saved_sections = dict((saved or {}).get("sections") or {})
        if slug == COMPREHENSIVE_REPORT_SLUG and not saved_sections:
            legacy = extract_comprehensive_sections_payload(saved or {})
            if legacy:
                saved_sections = sanitize_comprehensive_sections(legacy)

        saved_default_sections: dict[str, Any] = {}
        if slug == COMPREHENSIVE_REPORT_SLUG:
            raw_defaults = dict((saved or {}).get("default_sections") or {})
            if raw_defaults:
                try:
                    saved_default_sections = sanitize_comprehensive_sections(raw_defaults)
                except Exception:
                    saved_default_sections = {}
            # Prefer explicit default section filters for new-run initialization.
            if saved_default_sections:
                saved_sections = dict(saved_default_sections)

        return ReportConfigResponse(
            report_slug=slug,
            available_columns=available_columns,
            selected_column_ids=selected_keys,
            column_order=keys,
            default_column_ids=default_ids,
            default_selected_column_ids=list(saved_default_ids),
            default_sections=saved_default_sections,
            has_saved_configuration=has_saved,
            export_format=str((saved or {}).get("export_format") or "xlsx"),  # type: ignore[arg-type]
            config_overrides=dict((saved or {}).get("config_overrides") or {}),
            filter_conditions=list((saved or {}).get("filter_conditions") or []),
            sections=saved_sections,
            date_from=(saved or {}).get("date_from"),
            date_to=(saved or {}).get("date_to"),
        )

    async def get_output_columns(self, slug_or_page_id: str) -> dict[str, Any]:
        slug = resolve_manual_slug(slug_or_page_id)
        if not is_manual_report_slug(slug):
            raise HTTPException(status_code=404, detail=f"Unknown report slug: {slug_or_page_id}")
        columns = output_column_catalog(slug)
        default_ids = [str(c["id"]) for c in columns if c.get("default_visible", True)]
        if slug in {"train-no", "report3"}:
            logger.info("report3_available_columns_loaded count=%d", len(columns))
        elif slug in {"types", "report4"}:
            logger.info("report4_available_columns_loaded count=%d", len(columns))
        return {
            "report_slug": slug,
            "columns": columns,
            "default_column_ids": default_ids,
        }

    async def generate(
        self,
        slug_or_page_id: str,
        body: ManualGenerateRequest,
        *,
        user_id: str | None,
    ) -> ManualGenerateResponse:
        slug = resolve_manual_slug(slug_or_page_id)
        if not is_manual_report_slug(slug):
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "INVALID_REPORT_SLUG",
                    "message": f"Unknown report slug: {slug_or_page_id}",
                },
            )

        try:
            config_snapshot = build_config_snapshot(
                body,
                report_slug=slug,
                user_id=user_id,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "INVALID_COLUMN_SELECTION",
                    "message": str(exc),
                },
            ) from exc

        config_snapshot["report_slug"] = slug
        report_date = config_snapshot["report_date"]
        initial_status = "Extracting"

        logger.info(
            "manual_report_generate_payload slug=%s selected_column_ids=%s column_order=%s "
            "configuration_source=%s requested_formats=%s",
            slug,
            body.selected_column_ids,
            body.column_order,
            body.configuration_source,
            body.requested_formats,
        )

        try:
            run_id = await self.run_manual_report(
                slug,
                config_snapshot,
                user_id=user_id,
            )
        except HTTPException:
            raise
        except Exception as exc:
            from app.automation.service import AutomationLockBusyError

            if isinstance(exc, AutomationLockBusyError):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "AUTOMATION_ALREADY_RUNNING",
                        "message": str(exc),
                        "active_run_id": exc.active_run_id,
                        "active_report_slug": exc.active_report_slug,
                    },
                ) from exc
            logger.exception(
                "manual_report_generate_failed slug=%s user_id=%s",
                slug,
                user_id,
            )
            raise HTTPException(
                status_code=500,
                detail={
                    "code": "MANUAL_AUTOMATION_FAILED",
                    "message": str(exc) or "Manual report generation failed to start",
                },
            ) from exc

        logger.info(
            "manual_report_generate_started run_id=%s slug=%s report_date=%s "
            "columns_received_from_frontend=%s selected_column_count=%d configuration_source=%s snapshot_saved=true",
            run_id,
            slug,
            report_date,
            config_snapshot.get("selected_column_ids"),
            len(config_snapshot.get("selected_column_ids") or []),
            config_snapshot.get("configuration_source"),
        )
        if slug == "division":
            logger.info(
                "report2_config_snapshot_saved run_id=%s selected_column_ids=%s "
                "selected_column_count=%d configuration_source=%s",
                run_id,
                config_snapshot.get("selected_column_ids"),
                len(config_snapshot.get("selected_column_ids") or []),
                config_snapshot.get("configuration_source"),
            )

        return ManualGenerateResponse(
            run_id=run_id,
            report_slug=slug,
            report_date=report_date,
            status=initial_status,  # type: ignore[assignment]
            message="Manual report generation started",
        )

    async def run_manual_report(
        self,
        slug: str,
        config_snapshot: dict[str, Any],
        *,
        user_id: str | None,
    ) -> str:
        """Dispatch a single manual report run for the resolved canonical slug."""
        from app.automation.automation_lock import automation_lock_status
        from app.automation.handlers.registry import HANDLER_REGISTRY
        from app.automation.service import AutomationLockBusyError
        from app.automation.report_keys import canonicalize_report_key

        if canonicalize_report_key(slug) not in HANDLER_REGISTRY:
            raise HTTPException(
                status_code=500,
                detail={
                    "code": "HANDLER_NOT_REGISTERED",
                    "message": f"No handler registered for report slug: {slug}",
                },
            )

        report_date = config_snapshot["report_date"]
        lock_status = automation_lock_status()
        if lock_status.locked:
            raise AutomationLockBusyError(
                active_run_id=lock_status.run_id,
                active_report_slug=lock_status.report_slug,
            )

        if slug in {"scr-train", "scr-station"}:
            config_snapshot["force_fresh_extraction"] = True
            config_snapshot["generation_mode"] = "fresh_extraction"
            try:
                await validate_manual_scr_column_snapshot(slug, config_snapshot)
            except ValueError as exc:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "INVALID_COLUMN_SELECTION",
                        "message": str(exc),
                    },
                ) from exc
            automation_service = AutomationService()
            run_id, _status = await automation_service.start_manual_async(
                user_id=user_id,
                report_slugs=[slug],
                manual_config=config_snapshot,
            )
            log_manual_fresh_started(
                run_id=run_id,
                report_slug=slug,
                config_snapshot=config_snapshot,
            )
            return run_id

        if slug == "report9":
            config_snapshot["force_fresh_extraction"] = True
            config_snapshot["generation_mode"] = "fresh_extraction"
            automation_service = AutomationService()
            run_id, _status = await automation_service.start_manual_async(
                user_id=user_id,
                report_slugs=["report9"],
                manual_config=config_snapshot,
            )
            return run_id

        if slug in TOPN_REPORT_SLUGS:
            if await has_valid_topn_dataset(slug, report_date=report_date):
                config_snapshot["generation_mode"] = "process_only"
                run_id, _status = await start_topn_process_only_async(
                    report_slug=slug,
                    user_id=user_id,
                    manual_config=config_snapshot,
                )
                return run_id
            automation_service = AutomationService()
            run_id, _status = await automation_service.start_manual_async(
                user_id=user_id,
                report_slugs=[slug],
                manual_config=config_snapshot,
            )
            return run_id

        automation_service = AutomationService()
        run_id, _status = await automation_service.start_manual_async(
            user_id=user_id,
            report_slugs=[slug],
            manual_config=config_snapshot,
        )
        return run_id

    async def get_run_status(
        self,
        db: AsyncSession,
        run_id: str,
        *,
        expected_slug: str | None = None,
    ) -> ManualRunStatusResponse:
        run = await db.get(AutomationRunModel, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        manual_config = _parse_manual_config(run)
        if not manual_config and run.trigger_type != MANUAL_TRIGGER:
            raise HTTPException(status_code=404, detail="Not a manual report run")

        export_format = str(manual_config.get("export_format") or "xlsx")
        result = _parse_result(run)
        slug = (
            resolve_manual_slug(expected_slug)
            if expected_slug
            else resolve_manual_slug(str(manual_config.get("report_slug") or ""))
        )
        report = _find_report(result, slug)
        if report is None and result and result.reports:
            report = result.reports[0]
            slug = report.slug

        artifacts = await list_run_artifacts(db, run_id)
        dual_mode = slug in DUAL_ARTIFACT_SLUGS

        excel_artifact_id = None
        excel_download_url = None
        excel_filename = None
        excel_file_size = None
        pdf_artifact_id = None
        pdf_download_url = None
        pdf_preview_url = None
        pdf_filename = None
        pdf_file_size = None

        if dual_mode:
            dual_arts = _artifacts_for_slug(
                artifacts,
                slug=slug,
                manual_config=manual_config,
                run_id=run_id,
            )
            excel_art = dual_arts.get("excel")
            pdf_art = dual_arts.get("pdf")
            if excel_art:
                excel_artifact_id = excel_art.id
                excel_download_url = f"/api/v1/automation/artifacts/{excel_art.id}/download"
                excel_filename = Path(excel_art.file_path).name
                excel_file_size = excel_art.file_size_bytes
            elif report and report.excel_download_url:
                excel_download_url = report.excel_download_url
                if report.excel_path:
                    excel_filename = Path(report.excel_path).name
            if pdf_art:
                pdf_artifact_id = pdf_art.id
                pdf_download_url = f"/api/v1/automation/artifacts/{pdf_art.id}/download"
                pdf_preview_url = f"/api/v1/automation/artifacts/{pdf_art.id}/preview"
                pdf_filename = Path(pdf_art.file_path).name
                pdf_file_size = pdf_art.file_size_bytes
            elif report and report.pdf_download_url:
                pdf_download_url = report.pdf_download_url
                pdf_preview_url = report.pdf_preview_url
                if report.pdf_path:
                    pdf_filename = Path(report.pdf_path).name

            excel_ready = _artifact_is_ready(excel_art)
            pdf_ready = _artifact_is_ready(pdf_art)
            metadata_consistent, metadata_error = _dual_artifacts_metadata_consistent(
                excel_art,
                pdf_art,
                manual_config,
                run_id=run_id,
                report_slug=slug,
            )
            artifact_ready = excel_ready and pdf_ready and metadata_consistent

            artifact_id = excel_artifact_id
            download_url = excel_download_url
            preview_url = pdf_preview_url
            output_filename = excel_filename
            output_file_size = excel_file_size
        else:
            artifact = _artifact_for_format(artifacts, slug=slug, export_format=export_format)
            artifact_ready = _artifact_is_ready(artifact)
            artifact_id = None
            download_url = None
            preview_url = None
            output_filename = None
            output_file_size = None
            if artifact and artifact_ready:
                artifact_id = artifact.id
                download_url = f"/api/v1/automation/artifacts/{artifact.id}/download"
                if artifact.artifact_type == "pdf":
                    preview_url = f"/api/v1/automation/artifacts/{artifact.id}/preview"
                output_filename = Path(artifact.file_path).name
                output_file_size = artifact.file_size_bytes

        if run.status == "running" and manual_config.get("generation_mode") == "process_only":
            ui_status = "Processing"
        else:
            ui_status = map_manual_status(
                run_status=run.status,
                report=report,
                artifact_ready=artifact_ready,
            )

        stale_error: str | None = None
        if run.status == "running" and run.started_at is not None:
            from app.automation.automation_lock import automation_lock_status

            lock_status = automation_lock_status()
            started_at = run.started_at
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=UTC)
            age_seconds = (datetime.now(UTC) - started_at).total_seconds()
            stale_after = float(config.timeout) + 120.0
            worker_active = lock_status.locked and lock_status.run_id == run_id
            if age_seconds > stale_after and not worker_active:
                ui_status = "Failed"
                stale_error = (
                    "Report generation timed out or was interrupted. "
                    "Generate again to start a fresh run."
                )
                logger.warning(
                    "manual_run_stale_detected run_id=%s slug=%s age_seconds=%.1f",
                    run_id,
                    slug,
                    age_seconds,
                )

        visible_columns = list(report.visible_columns or []) if report else []
        if not visible_columns:
            snapshot_keys = manual_config.get("column_order") or manual_config.get(
                "selected_column_ids"
            )
            if snapshot_keys:
                visible_columns = projection_labels_for_slug(slug, snapshot_keys)
            else:
                from app.automation.processing.column_config import resolve_projection_column_keys

                keys, _source = resolve_projection_column_keys(slug, user_id=run.created_by)
                visible_columns = projection_labels_for_slug(slug, keys)

        try:
            preview_rows = read_preview_rows(
                excel_path=report.excel_path if report else None,
                csv_path=report.source_csv_path if report else None,
                visible_columns=visible_columns or None,
                allow_csv_fallback=not (
                    slug in ("report1", "division")
                    and manual_config
                    and (
                        artifact_ready
                        or bool(report and report.processing_success)
                        or bool(report and report.excel_path)
                    )
                ),
            )
        except Exception as exc:
            logger.warning(
                "manual_run_status_preview_read_failed run_id=%s slug=%s error=%s",
                run_id,
                slug,
                exc,
            )
            preview_rows = []

        error = stale_error
        if not error and report and report.error:
            error = report.error
        elif not error and run.error_message:
            error = run.error_message
        if dual_mode and report and report.processing_success and not artifact_ready:
            if excel_ready and pdf_ready and not metadata_consistent:
                if ui_status != "Failed":
                    ui_status = "Failed"
                error = error or metadata_error or "Artifact column snapshot mismatch"
            elif excel_ready and not pdf_ready:
                if ui_status != "Failed":
                    ui_status = "Generating Excel/PDF"
                if report and not report.pdf_path:
                    error = error or "PDF generation failed"
            elif not excel_ready and pdf_ready:
                if ui_status != "Failed":
                    ui_status = "Generating Excel/PDF"
                error = error or "Excel generation failed"
        if ui_status == "Failed" and not error:
            error = run.error_message or "Report generation failed"

        return ManualRunStatusResponse(
            run_id=run_id,
            report_slug=slug,
            report_date=manual_config.get("report_date") or previous_day_report_date(),
            status=ui_status,
            run_status=run.status,
            source_row_count=report.source_row_count if report else None,
            processed_row_count=report.processed_row_count if report else None,
            row_counts=report.row_counts if report else {},
            extraction_success=extraction_success(report),
            ingestion_success=bool(report and report.ingestion_success),
            processing_success=bool(report and report.processing_success),
            artifact_id=artifact_id,
            preview_url=preview_url,
            download_url=download_url,
            export_format=export_format,
            excel_artifact_id=excel_artifact_id,
            excel_download_url=excel_download_url,
            excel_filename=excel_filename,
            excel_file_size=excel_file_size,
            pdf_artifact_id=pdf_artifact_id,
            pdf_download_url=pdf_download_url,
            pdf_preview_url=pdf_preview_url,
            pdf_filename=pdf_filename,
            pdf_file_size=pdf_file_size,
            visible_columns=visible_columns,
            preview_rows=preview_rows,
            output_filename=output_filename,
            output_file_size=output_file_size,
            generated_at=run.completed_at.isoformat() if run.completed_at else None,
            error=error,
        )

    async def save_config(
        self,
        slug_or_page_id: str,
        body: SaveReportConfigRequest,
        *,
        user_id: str | None = None,
    ) -> SaveReportConfigResponse:
        slug = resolve_manual_slug(slug_or_page_id)
        if not is_manual_report_slug(slug):
            raise HTTPException(status_code=404, detail=f"Unknown report slug: {slug_or_page_id}")

        existing = load_report_config(slug, user_id=user_id) or {}

        if slug == COMPREHENSIVE_REPORT_SLUG:
            raw_sections = body.sections or extract_comprehensive_sections_payload(body.model_dump())
            if not raw_sections:
                raise HTTPException(
                    status_code=422,
                    detail="Report 10-13 requires column selections for all four sections.",
                )
            try:
                column_snapshot = build_comprehensive_column_snapshot(
                    raw_sections,
                    date_from=body.date_from,
                    date_to=body.date_to,
                )
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

            payload: dict[str, Any] = {
                **existing,
                **column_snapshot,
                "export_format": body.export_format,
                "config_overrides": dict(body.config_overrides),
                "filter_conditions": list(body.filter_conditions),
            }
            if body.date_from:
                payload["date_from"] = body.date_from
            if body.date_to:
                payload["date_to"] = body.date_to
            if body.default_selected_column_ids is not None:
                try:
                    default_keys = sanitize_projection_keys(
                        body.default_selected_column_ids,
                        slug,
                        user_id=user_id,
                    )
                    validate_projection_selection(slug, default_keys)
                except ValueError as exc:
                    raise HTTPException(status_code=422, detail=str(exc)) from exc
                payload["default_selected_column_ids"] = list(default_keys)
            if body.default_sections is not None:
                try:
                    default_sections = sanitize_comprehensive_sections(body.default_sections)
                    validate_comprehensive_sections(default_sections)
                except ValueError as exc:
                    raise HTTPException(status_code=422, detail=str(exc)) from exc
                payload["default_sections"] = default_sections
            save_report_config(slug, payload, user_id=user_id)
            return SaveReportConfigResponse(report_slug=slug)

        if is_columnless_manual_report(slug):
            payload = {
                **existing,
                "selected_column_ids": [],
                "column_order": [],
                "export_format": body.export_format,
                "config_overrides": dict(body.config_overrides),
                "filter_conditions": list(body.filter_conditions),
            }
            save_report_config(slug, payload, user_id=user_id)
            return SaveReportConfigResponse(report_slug=slug)

        column_order = body.column_order or body.selected_column_ids
        if not column_order:
            column_order = list(
                existing.get("column_order")
                or existing.get("selected_column_ids")
                or existing.get("default_selected_column_ids")
                or []
            )
        try:
            keys = sanitize_projection_keys(column_order, slug, user_id=user_id)
            if not keys and body.default_selected_column_ids is not None:
                keys = sanitize_projection_keys(
                    body.default_selected_column_ids,
                    slug,
                    user_id=user_id,
                )
            validate_projection_selection(slug, keys)
            validate_column_order(slug, keys, list(column_order) if column_order else list(keys))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        payload: dict[str, Any] = {
            **existing,
            "selected_column_ids": list(keys),
            "column_order": list(keys),
            "export_format": body.export_format,
            "config_overrides": dict(body.config_overrides),
            "filter_conditions": list(body.filter_conditions),
        }
        if body.default_selected_column_ids is not None:
            try:
                default_keys = sanitize_projection_keys(
                    body.default_selected_column_ids,
                    slug,
                    user_id=user_id,
                )
                validate_projection_selection(slug, default_keys)
                validate_column_order(slug, default_keys, list(default_keys))
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            payload["default_selected_column_ids"] = list(default_keys)
        save_report_config(slug, payload, user_id=user_id)
        return SaveReportConfigResponse(report_slug=slug)

    async def get_saved_config(
        self,
        slug_or_page_id: str,
        *,
        user_id: str | None = None,
    ) -> dict[str, Any] | None:
        slug = resolve_manual_slug(slug_or_page_id)
        return load_report_config(slug, user_id=user_id)

    async def output_preview(
        self,
        slug_or_page_id: str,
        body: OutputPreviewRequest,
    ) -> OutputPreviewResponse:
        slug = resolve_manual_slug(slug_or_page_id)
        if (
            slug not in NAMESPACED_REPORT_SLUGS
            and slug not in SCR_NAMESPACED_SLUGS
            and slug not in TOPN_REPORT_SLUGS
        ):
            raise HTTPException(status_code=404, detail=f"Output preview not supported for: {slug}")
        order = body.column_order or body.selected_column_ids
        keys = sanitize_projection_keys(order, slug)
        try:
            validate_projection_selection(slug, keys)
            if body.selected_column_ids:
                selected = sanitize_projection_keys(body.selected_column_ids, slug)
                validate_column_order(slug, selected, keys)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        try:
            payload = await build_output_preview(
                slug,
                selected_column_ids=body.selected_column_ids,
                column_order=order,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return OutputPreviewResponse.model_validate(payload)
