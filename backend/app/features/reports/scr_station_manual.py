"""Process-only manual generation for SCR Station (scr-station).

Reuses the same ingested CSV and projection path as reactive preview — no CDP extraction
when a valid dataset already exists.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from app.automation.formatting.scr import mode_matches
from app.automation.processing.column_config import project_scr_for_output
from app.automation.processing.report6_processor import Report6Processor
from app.automation.run_registry import (
    build_dual_artifact_metadata,
    create_cdp_run,
    finalize_cdp_run,
    register_artifact,
)
from app.automation.schemas import MultiReportResult, ReportResult
from app.automation.scr_field_map import canonicalize_scr_rows
from app.features.reports.preview_projection import ScrDatasetRef, resolve_scr_dataset
from app.infrastructure.database.session import SessionLocal

logger = logging.getLogger(__name__)

REPORT_SLUG = "scr-station"
MANUAL_TRIGGER = "manual_report"


def _load_station_rows(source_path: Path) -> tuple[list[dict[str, str]], int]:
    processor = Report6Processor()
    rows, _headers = processor._read_csv(source_path)
    rows = canonicalize_scr_rows(rows)
    station_rows = [
        row
        for row in rows
        if mode_matches(
            "Station",
            row.get("complaintMode", "") or row.get("mode", "") or row.get("Mode", ""),
        )
    ]
    return station_rows, len(rows)


async def preflight_scr_station_manual(config_snapshot: dict[str, object]) -> ScrDatasetRef:
    """Validate ingested source and column selection before creating a run."""
    logger.info(
        "report6_valid_dataset_lookup_started report_slug=%s report_date=%s",
        REPORT_SLUG,
        config_snapshot.get("report_date"),
    )
    dataset = await resolve_scr_dataset(REPORT_SLUG)
    if dataset is None:
        raise ValueError(
            "REPORT6_VALID_DATASET_NOT_FOUND: No ingested Report 6 station dataset available"
        )

    keys = list(
        config_snapshot.get("column_order")
        or config_snapshot.get("selected_column_ids")
        or []
    )
    if not keys:
        raise ValueError("INVALID_SELECTED_COLUMNS: No columns selected")

    station_rows, _total = _load_station_rows(dataset.path)

    logger.info(
        "report6_valid_dataset_found report_slug=%s dataset_id=%s dataset_path=%s "
        "dataset_rows=%d station_row_count=%d",
        REPORT_SLUG,
        dataset.dataset_id,
        dataset.path,
        dataset.row_count,
        len(station_rows),
    )
    logger.info(
        "report6_filter_payload_received report_slug=%s selected_column_ids=%s "
        "selected_column_count=%d configuration_source=%s",
        REPORT_SLUG,
        keys,
        len(keys),
        config_snapshot.get("configuration_source"),
    )

    try:
        project_scr_for_output(
            REPORT_SLUG,
            station_rows,
            selected_keys=keys,
            config_source="manual_snapshot",
        )
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    logger.info(
        "report6_source_loaded report_slug=%s dataset_id=%s source_path=%s "
        "station_row_count=%d columns_received_from_frontend=%s columns_resolved_for_processing=%s",
        REPORT_SLUG,
        dataset.dataset_id,
        dataset.path,
        len(station_rows),
        keys,
        keys,
    )
    return dataset


async def start_scr_station_process_only_async(
    *,
    user_id: str | None,
    manual_config: dict[str, object],
    dataset: ScrDatasetRef,
) -> tuple[str, str]:
    """Create a manual run and process ingested data in a background thread."""
    manual_config = dict(manual_config)
    manual_config["dataset_id"] = dataset.dataset_id
    manual_config["dataset_path"] = str(dataset.path)

    async with SessionLocal() as db:
        run = await create_cdp_run(
            db,
            user_id=user_id,
            trigger_type=MANUAL_TRIGGER,
            manual_config=manual_config,
        )
        run_id = run.id

    logger.info(
        "report6_filter_snapshot_saved run_id=%s report_slug=%s dataset_id=%s "
        "selected_column_ids=%s selected_column_count=%d configuration_source=%s",
        run_id,
        REPORT_SLUG,
        dataset.dataset_id,
        manual_config.get("selected_column_ids"),
        len(manual_config.get("selected_column_ids") or []),
        manual_config.get("configuration_source"),
    )
    logger.info(
        "report6_generation_mode_selected run_id=%s mode=process_only dataset_id=%s",
        run_id,
        dataset.dataset_id,
    )

    def _worker() -> None:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        asyncio.run(
            _run_scr_station_process_only_worker(
                run_id,
                user_id=user_id,
                manual_config=manual_config,
                dataset=dataset,
            )
        )

    thread = threading.Thread(
        target=_worker,
        name=f"scr-station-manual-{run_id[:8]}",
        daemon=True,
    )
    thread.start()
    return run_id, "running"


async def _run_scr_station_process_only_worker(
    run_id: str,
    *,
    user_id: str | None,
    manual_config: dict[str, object],
    dataset: ScrDatasetRef,
) -> None:
    from app.infrastructure.database.session import dispose_current_loop_engine

    started = time.monotonic()
    source_path = dataset.path

    try:
        logger.info(
            "report6_manual_generation_started run_id=%s report_slug=%s dataset_id=%s source_path=%s",
            run_id,
            REPORT_SLUG,
            dataset.dataset_id,
            source_path,
        )

        station_rows, total_rows = _load_station_rows(source_path)

        keys = list(
            manual_config.get("column_order")
            or manual_config.get("selected_column_ids")
            or []
        )

        output_headers, output_rows, visible_columns, resolved_keys, config_source = (
            project_scr_for_output(
                REPORT_SLUG,
                station_rows,
                selected_keys=keys,
                config_source="manual_snapshot",
            )
        )
        logger.info(
            "report6_projection_completed run_id=%s dataset_id=%s projected_headers=%s "
            "projected_row_count=%d columns_resolved_for_processing=%s duration_seconds=%.3f",
            run_id,
            dataset.dataset_id,
            output_headers,
            len(output_rows),
            resolved_keys,
            time.monotonic() - started,
        )

        processing_result = Report6Processor().process(
            source_a_path=source_path,
            report_slug=REPORT_SLUG,
            column_selection=manual_config,
        )

        if not processing_result.success:
            error = processing_result.error or "REPORT6_EXCEL_GENERATION_FAILED"
            logger.error(
                "report6_manual_generation_failed run_id=%s stage=processing error=%s duration_seconds=%.3f",
                run_id,
                error,
                time.monotonic() - started,
            )
            report_result = ReportResult(
                slug=REPORT_SLUG,
                dataset_key=REPORT_SLUG,
                status="failed",
                error=error,
                ingestion_success=True,
                processing_attempted=True,
                processing_success=False,
                source_csv_path=str(source_path),
                source_row_count=total_rows,
                processed_row_count=0,
                visible_columns=visible_columns,
                selected_column_ids=resolved_keys,
                column_order=list(resolved_keys),
                configuration_source=config_source,
            )
            result = MultiReportResult(
                success=False,
                connected=True,
                tab_found=True,
                reports=[report_result],
                run_id=run_id,
                reports_successful=0,
                reports_failed=1,
                error=error,
            )
            async with SessionLocal() as db:
                await finalize_cdp_run(db, run_id, result, user_id=user_id)
            return

        logger.info(
            "report6_excel_generated run_id=%s excel_path=%s duration_seconds=%.3f",
            run_id,
            processing_result.excel_path,
            time.monotonic() - started,
        )
        logger.info(
            "report6_pdf_generated run_id=%s pdf_path=%s duration_seconds=%.3f",
            run_id,
            processing_result.pdf_path,
            time.monotonic() - started,
        )

        artifact_metadata = build_dual_artifact_metadata(
            selected_column_ids=processing_result.selected_column_ids,
            column_order=processing_result.column_order,
            configuration_source=processing_result.configuration_source or "manual_snapshot",
            run_id=run_id,
            report_slug=REPORT_SLUG,
        )
        artifact_metadata["dataset_id"] = dataset.dataset_id
        artifact_metadata["dataset_path"] = str(source_path)

        excel_art_id: str | None = None
        pdf_art_id: str | None = None
        try:
            async with SessionLocal() as db:
                if processing_result.excel_path:
                    excel_art = await register_artifact(
                        db,
                        run_id=run_id,
                        report_slug=REPORT_SLUG,
                        report_name=REPORT_SLUG,
                        file_type="excel",
                        file_path=processing_result.excel_path,
                        metadata=artifact_metadata,
                    )
                    if excel_art and excel_art.status == "ready" and (excel_art.file_size_bytes or 0) > 0:
                        excel_art_id = excel_art.id
                if processing_result.pdf_path:
                    pdf_art = await register_artifact(
                        db,
                        run_id=run_id,
                        report_slug=REPORT_SLUG,
                        report_name=REPORT_SLUG,
                        file_type="pdf",
                        file_path=processing_result.pdf_path,
                        metadata=artifact_metadata,
                    )
                    if pdf_art and pdf_art.status == "ready" and (pdf_art.file_size_bytes or 0) > 0:
                        pdf_art_id = pdf_art.id
        except Exception as exc:
            error = f"REPORT6_ARTIFACT_REGISTRATION_FAILED: {exc}"
            logger.exception(
                "report6_manual_generation_failed run_id=%s stage=artifact_registration error=%s",
                run_id,
                error,
            )
            report_result = ReportResult(
                slug=REPORT_SLUG,
                dataset_key=REPORT_SLUG,
                status="failed",
                error=error,
                ingestion_success=True,
                processing_attempted=True,
                processing_success=False,
                source_csv_path=str(source_path),
                source_row_count=total_rows,
                excel_path=processing_result.excel_path,
                pdf_path=processing_result.pdf_path,
                visible_columns=processing_result.visible_columns,
                selected_column_ids=processing_result.selected_column_ids,
                column_order=processing_result.column_order,
                configuration_source=processing_result.configuration_source,
            )
            result = MultiReportResult(
                success=False,
                connected=True,
                tab_found=True,
                reports=[report_result],
                run_id=run_id,
                reports_successful=0,
                reports_failed=1,
                error=error,
            )
            async with SessionLocal() as db:
                await finalize_cdp_run(db, run_id, result, user_id=user_id)
            return

        if not excel_art_id or not pdf_art_id:
            missing = []
            if not excel_art_id:
                missing.append("excel")
            if not pdf_art_id:
                missing.append("pdf")
            error = (
                "REPORT6_ARTIFACT_REGISTRATION_FAILED: "
                f"Missing ready artifacts: {', '.join(missing)}"
            )
            logger.error(
                "report6_manual_generation_failed run_id=%s stage=artifact_registration error=%s",
                run_id,
                error,
            )
            report_result = ReportResult(
                slug=REPORT_SLUG,
                dataset_key=REPORT_SLUG,
                status="failed",
                error=error,
                ingestion_success=True,
                processing_attempted=True,
                processing_success=True,
                source_csv_path=str(source_path),
                source_row_count=total_rows,
                processed_row_count=processing_result.processed_row_count,
                excel_path=processing_result.excel_path,
                pdf_path=processing_result.pdf_path,
                visible_columns=processing_result.visible_columns,
                selected_column_ids=processing_result.selected_column_ids,
                column_order=processing_result.column_order,
                configuration_source=processing_result.configuration_source,
            )
            result = MultiReportResult(
                success=False,
                connected=True,
                tab_found=True,
                reports=[report_result],
                run_id=run_id,
                reports_successful=0,
                reports_failed=1,
                error=error,
            )
            async with SessionLocal() as db:
                await finalize_cdp_run(db, run_id, result, user_id=user_id)
            return

        logger.info(
            "report6_artifacts_registered run_id=%s excel_artifact_id=%s pdf_artifact_id=%s "
            "duration_seconds=%.3f",
            run_id,
            excel_art_id,
            pdf_art_id,
            time.monotonic() - started,
        )

        report_result = ReportResult(
            slug=REPORT_SLUG,
            dataset_key=REPORT_SLUG,
            status="success",
            ingestion_success=True,
            processing_attempted=True,
            processing_success=True,
            source_csv_path=str(source_path),
            source_row_count=total_rows,
            processed_row_count=processing_result.processed_row_count,
            excel_path=processing_result.excel_path,
            pdf_path=processing_result.pdf_path,
            excel_download_url=f"/api/v1/automation/artifacts/{excel_art_id}/download",
            pdf_download_url=f"/api/v1/automation/artifacts/{pdf_art_id}/download",
            pdf_preview_url=f"/api/v1/automation/artifacts/{pdf_art_id}/preview",
            visible_columns=processing_result.visible_columns,
            selected_column_ids=processing_result.selected_column_ids,
            column_order=processing_result.column_order,
            configuration_source=processing_result.configuration_source,
            completed_at=datetime.now(UTC).isoformat(),
        )
        result = MultiReportResult(
            success=True,
            connected=True,
            tab_found=True,
            reports=[report_result],
            run_id=run_id,
            reports_successful=1,
            reports_failed=0,
        )
        async with SessionLocal() as db:
            await finalize_cdp_run(db, run_id, result, user_id=user_id)

        logger.info(
            "report6_manual_generation_completed run_id=%s dataset_id=%s processed_row_count=%d "
            "selected_column_count=%d duration_seconds=%.3f",
            run_id,
            dataset.dataset_id,
            processing_result.processed_row_count,
            len(resolved_keys),
            time.monotonic() - started,
        )

    except Exception as exc:
        error = str(exc) or "REPORT6_MANUAL_GENERATION_FAILED"
        logger.exception(
            "report6_manual_generation_failed run_id=%s stage=unexpected error=%s duration_seconds=%.3f",
            run_id,
            error,
            time.monotonic() - started,
        )
        report_result = ReportResult(
            slug=REPORT_SLUG,
            dataset_key=REPORT_SLUG,
            status="failed",
            error=error,
            ingestion_success=True,
            processing_attempted=True,
            processing_success=False,
            source_csv_path=str(source_path),
        )
        result = MultiReportResult(
            success=False,
            connected=True,
            tab_found=True,
            reports=[report_result],
            run_id=run_id,
            reports_successful=0,
            reports_failed=1,
            error=error,
        )
        async with SessionLocal() as db:
            await finalize_cdp_run(db, run_id, result, user_id=user_id)
    finally:
        await dispose_current_loop_engine()
