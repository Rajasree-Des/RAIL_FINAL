"""Process-only manual generation for Report 3 (train-no) and Report 4 (types)."""

from __future__ import annotations

import asyncio
import csv
import logging
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path

from app.automation.processing.service import process_report
from app.automation.run_registry import (
    build_dual_artifact_metadata,
    create_cdp_run,
    finalize_cdp_run,
    register_artifact,
)
from app.automation.schemas import MultiReportResult, ReportResult
from app.automation.utils import previous_day_report_date
from app.features.reports.preview_projection import resolve_topn_dataset
from app.infrastructure.database.session import SessionLocal

logger = logging.getLogger(__name__)

MANUAL_TRIGGER = "manual_report"

REQUIRED_SOURCE_HEADERS = {
    "Train Name",
    "Owning Zone",
    "Owning Division",
    "Train No.",
    "Received",
    "% Share",
    "Closed",
    "% Closed",
    "Pending",
    "Average Rating",
}


def _csv_headers(path: Path) -> set[str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return set(reader.fieldnames or [])


def _has_required_headers(path: Path) -> bool:
    headers = _csv_headers(path)
    if not headers:
        return False
    train_no_ok = "Train No." in headers or "Train No" in headers
    required = REQUIRED_SOURCE_HEADERS - {"Train No."}
    return train_no_ok and required.issubset(headers)


async def resolve_valid_topn_dataset(
    report_slug: str,
    *,
    report_date: str | None = None,
) -> Path | None:
    """Return ingested dataset path when valid for process-only regeneration."""
    path = await resolve_topn_dataset(report_slug)
    if path is None:
        return None
    expected_date = report_date or previous_day_report_date()
    path_text = str(path).replace("_", "-")
    if expected_date.replace("/", "-") not in path_text and expected_date not in path_text:
        # Allow when filename lacks date but file is the canonical ingested dataset.
        if not _has_required_headers(path):
            return None
    elif not _has_required_headers(path):
        return None
    return path


async def has_valid_topn_dataset(report_slug: str, *, report_date: str | None = None) -> bool:
    return await resolve_valid_topn_dataset(report_slug, report_date=report_date) is not None


async def start_topn_process_only_async(
    *,
    report_slug: str,
    user_id: str | None,
    manual_config: dict[str, object],
) -> tuple[str, str]:
    async with SessionLocal() as db:
        snapshot = dict(manual_config)
        snapshot["report_slug"] = report_slug
        snapshot["generation_mode"] = "process_only"
        run = await create_cdp_run(
            db,
            user_id=user_id,
            trigger_type=MANUAL_TRIGGER,
            manual_config=snapshot,
        )
        run_id = run.id

    log_event = "report3_snapshot_saved" if report_slug in {"train-no", "report3"} else "report4_snapshot_saved"
    logger.info(
        "%s run_id=%s report_slug=%s selected_column_ids=%s selected_column_count=%d",
        log_event,
        run_id,
        report_slug,
        manual_config.get("selected_column_ids"),
        len(manual_config.get("selected_column_ids") or []),
    )

    def _worker() -> None:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        asyncio.run(
            _run_topn_process_only_worker(
                run_id,
                report_slug=report_slug,
                user_id=user_id,
                manual_config=manual_config,
            )
        )

    thread = threading.Thread(
        target=_worker,
        name=f"{report_slug}-manual-{run_id[:8]}",
        daemon=True,
    )
    thread.start()
    return run_id, "running"


async def _run_topn_process_only_worker(
    run_id: str,
    *,
    report_slug: str,
    user_id: str | None,
    manual_config: dict[str, object],
) -> None:
    from app.infrastructure.database.session import dispose_current_loop_engine

    try:
        source_path = await resolve_valid_topn_dataset(
            report_slug,
            report_date=str(manual_config.get("report_date") or previous_day_report_date()),
        )
        if source_path is None:
            raise ValueError("STALE_SOURCE_REJECTED: No valid current-run ingested dataset")

        selection = dict(manual_config)
        selection["run_id"] = run_id
        processing_result = await process_report(
            report_slug,
            True,
            column_selection=selection,
        )
        if not processing_result.success:
            raise ValueError(processing_result.error or "Processing failed")

        artifact_metadata = None
        if processing_result.selected_column_ids:
            artifact_metadata = build_dual_artifact_metadata(
                selected_column_ids=processing_result.selected_column_ids,
                column_order=processing_result.column_order,
                run_id=run_id,
                report_slug=report_slug,
            )

        artifact_ids: dict[str, str] = {}
        async with SessionLocal() as session:
            if processing_result.excel_path:
                art = await register_artifact(
                    session,
                    run_id=run_id,
                    report_slug=report_slug,
                    report_name=report_slug,
                    file_type="excel",
                    file_path=processing_result.excel_path,
                    metadata=artifact_metadata,
                )
                if art:
                    artifact_ids["excel"] = art.id
            if processing_result.pdf_path:
                art = await register_artifact(
                    session,
                    run_id=run_id,
                    report_slug=report_slug,
                    report_name=report_slug,
                    file_type="pdf",
                    file_path=processing_result.pdf_path,
                    metadata=artifact_metadata,
                )
                if art:
                    artifact_ids["pdf"] = art.id

        report_result = ReportResult(
            slug=report_slug,
            dataset_key=report_slug,
            status="success",
            ingestion_success=True,
            processing_success=True,
            processing_attempted=True,
            excel_path=processing_result.excel_path,
            pdf_path=processing_result.pdf_path,
            processed_row_count=processing_result.processed_row_count,
            source_row_count=processing_result.source_a_rows,
            row_count=processing_result.source_a_rows,
            output_columns=processing_result.output_columns,
            visible_columns=processing_result.visible_columns,
            selected_column_ids=processing_result.selected_column_ids,
            column_order=processing_result.column_order,
            configuration_source=processing_result.configuration_source,
            completed_at=datetime.now(UTC).isoformat(),
        )
        if artifact_ids.get("excel"):
            report_result.excel_download_url = (
                f"/api/v1/automation/artifacts/{artifact_ids['excel']}/download"
            )
        if artifact_ids.get("pdf"):
            report_result.pdf_download_url = (
                f"/api/v1/automation/artifacts/{artifact_ids['pdf']}/download"
            )
            report_result.pdf_preview_url = (
                f"/api/v1/automation/artifacts/{artifact_ids['pdf']}/preview"
            )

        multi = MultiReportResult(
            success=True,
            connected=True,
            tab_found=True,
            reports=[report_result],
            run_id=run_id,
            reports_successful=1,
            reports_failed=0,
        )
        async with SessionLocal() as session:
            await finalize_cdp_run(session, run_id, multi, user_id=user_id)
    except Exception as exc:
        logger.exception("Top-N process-only failed run_id=%s slug=%s", run_id, report_slug)
        failed = ReportResult(
            slug=report_slug,
            dataset_key=report_slug,
            status="failed",
            error=str(exc),
            processing_attempted=True,
            processing_success=False,
        )
        multi = MultiReportResult(
            success=False,
            connected=True,
            tab_found=True,
            reports=[failed],
            run_id=run_id,
            error=str(exc),
            reports_successful=0,
            reports_failed=1,
        )
        async with SessionLocal() as session:
            await finalize_cdp_run(session, run_id, multi, user_id=user_id)
    finally:
        await dispose_current_loop_engine()
