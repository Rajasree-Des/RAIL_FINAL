"""Phase 8 orchestration for post-ingestion report processing."""

from __future__ import annotations

import inspect
import logging
from pathlib import Path

from sqlalchemy import select

from app.automation.processing.base import ProcessingResult
from app.automation.processing.registry import PROCESSORS
from app.automation.processing.scr_output_columns import SCR_NAMESPACED_SLUGS
from app.automation.report_keys import canonicalize_report_key
from app.automation.utils import log_automation_event
from app.features.reports.scr_fresh import is_scr_manual_fresh, verify_current_run_source
from app.infrastructure.database.session import SessionLocal

logger = logging.getLogger(__name__)

FEEDBACK_DATASET_ID = "report1_feedback"
DIVISION_FEEDBACK_DATASET_ID = "division_feedback"


async def process_report(
    report_slug: str,
    ingestion_success: bool,
    *,
    column_selection: dict | None = None,
) -> ProcessingResult:
    """Run Phase 8 processing when ingestion succeeded."""
    if not ingestion_success:
        return ProcessingResult(attempted=False, success=False)

    canonical = canonicalize_report_key(report_slug)
    processor = PROCESSORS.get(canonical)
    if processor is None:
        return ProcessingResult(
            attempted=True,
            success=False,
            error=f"No processor registered for report slug: {report_slug}",
        )

    log_automation_event(
        logger,
        "phase8_started",
        report_slug=canonical,
        processor=processor.processor_name,
    )

    try:
        from app.automation.run_context import get_run_context

        ctx = get_run_context()
        async with SessionLocal() as session:
            from app.features.datasets.service import DatasetService
            from app.infrastructure.database.models import ReportDatasetModel

            dataset_service = DatasetService(session)
            await dataset_service.ensure_dataset_exists(canonical)

            result = await session.execute(
                select(ReportDatasetModel)
                .where(ReportDatasetModel.report_id == canonical)
                .limit(1)
            )
            model = result.scalar_one_or_none()
            if model is None or not model.source_file_path:
                return ProcessingResult(
                    attempted=True,
                    success=False,
                    processor_used=processor.processor_name,
                    error=f"Dataset missing for report: {canonical}",
                )

            source_a_path = Path(model.source_file_path)
            if ctx is not None and canonical in SCR_NAMESPACED_SLUGS:
                run_source = ctx.current_run_sources.get(canonical)
                if run_source:
                    source_a_path = Path(run_source)
                if canonical == "scr-station" or is_scr_manual_fresh(ctx.manual_config):
                    try:
                        verify_current_run_source(
                            source_a_path,
                            run_id=ctx.run_id,
                            report_slug=canonical,
                            run_started_at=ctx.run_started_at,
                        )
                    except ValueError as exc:
                        return ProcessingResult(
                            attempted=True,
                            success=False,
                            processor_used=processor.processor_name,
                            error=str(exc),
                            source_a_path=str(source_a_path),
                        )

            if source_a_path.suffix.lower() == ".pdf":
                return ProcessingResult(
                    attempted=True,
                    success=False,
                    processor_used=processor.processor_name,
                    error="PDF cannot be used as processing input",
                    source_a_path=str(source_a_path),
                )

            source_b_path: Path | None = None
            if canonical == "report1":
                feedback_result = await session.execute(
                    select(ReportDatasetModel)
                    .where(ReportDatasetModel.report_id == FEEDBACK_DATASET_ID)
                    .limit(1)
                )
                feedback_model = feedback_result.scalar_one_or_none()
                log_automation_event(
                    logger,
                    "report1_source_b_lookup",
                    dataset_id=FEEDBACK_DATASET_ID,
                    feedback_model_found=feedback_model is not None,
                    source_file_path=feedback_model.source_file_path if feedback_model else None,
                    row_count=feedback_model.row_count if feedback_model else None,
                )
                if feedback_model and feedback_model.source_file_path:
                    candidate = Path(feedback_model.source_file_path)
                    if candidate.exists() and candidate.suffix.lower() != ".pdf":
                        source_b_path = candidate
            elif canonical == "division":
                feedback_result = await session.execute(
                    select(ReportDatasetModel)
                    .where(ReportDatasetModel.report_id == DIVISION_FEEDBACK_DATASET_ID)
                    .limit(1)
                )
                feedback_model = feedback_result.scalar_one_or_none()
                log_automation_event(
                    logger,
                    "report2_source_b_lookup",
                    dataset_id=DIVISION_FEEDBACK_DATASET_ID,
                    feedback_model_found=feedback_model is not None,
                    source_file_path=feedback_model.source_file_path if feedback_model else None,
                    row_count=feedback_model.row_count if feedback_model else None,
                )
                if feedback_model and feedback_model.source_file_path:
                    candidate = Path(feedback_model.source_file_path)
                    candidate_exists = candidate.exists()
                    candidate_suffix = candidate.suffix.lower()
                    log_automation_event(
                        logger,
                        "report2_source_b_candidate",
                        candidate_path=str(candidate),
                        exists=candidate_exists,
                        suffix=candidate_suffix,
                        size=candidate.stat().st_size if candidate_exists else 0,
                        mtime=candidate.stat().st_mtime if candidate_exists else None,
                    )
                    if candidate_exists and candidate_suffix != ".pdf":
                        source_b_path = candidate

            log_automation_event(
                logger,
                "phase8_processor_inputs",
                canonical=canonical,
                source_a_path=str(source_a_path),
                source_a_exists=source_a_path.exists(),
                source_a_size=source_a_path.stat().st_size if source_a_path.exists() else 0,
                source_a_mtime=source_a_path.stat().st_mtime if source_a_path.exists() else None,
                source_b_path=str(source_b_path) if source_b_path else None,
                source_b_exists=source_b_path.exists() if source_b_path else False,
                source_b_size=source_b_path.stat().st_size if source_b_path and source_b_path.exists() else 0,
                source_b_mtime=source_b_path.stat().st_mtime if source_b_path and source_b_path.exists() else None,
            )

            # Report 1 MUST have Feedback Source B from current-run ingest
            if canonical == "report1":
                if source_b_path is None or not source_b_path.exists():
                    log_automation_event(
                        logger,
                        "report1_source_b_required_missing",
                        source_b_path=str(source_b_path) if source_b_path else None,
                    )
                    return ProcessingResult(
                        attempted=True,
                        success=False,
                        processor_used=processor.processor_name,
                        source_a_path=str(source_a_path),
                        source_b_path=str(source_b_path) if source_b_path else None,
                        error="Report 1 requires both Comprehensive and Feedback Zone Wise sources. "
                              "Source B (report1_feedback) missing or not ingested for this run.",
                    )

            # Report 2 (division) MUST have Source B - fail closed, no fallback
            if canonical == "division":
                if source_b_path is None:
                    log_automation_event(
                        logger,
                        "report2_source_b_required_missing",
                        error="Report 2 requires Feedback Division Wise (Source B) dataset",
                    )
                    return ProcessingResult(
                        attempted=True,
                        success=False,
                        processor_used=processor.processor_name,
                        source_a_path=str(source_a_path),
                        error="Report 2 requires both Comprehensive and Feedback Division Wise sources. "
                              "Source B (division_feedback) dataset not found in database.",
                    )
                if not source_b_path.exists():
                    log_automation_event(
                        logger,
                        "report2_source_b_file_missing",
                        source_b_path=str(source_b_path),
                        error="Source B file does not exist on disk",
                    )
                    return ProcessingResult(
                        attempted=True,
                        success=False,
                        processor_used=processor.processor_name,
                        source_a_path=str(source_a_path),
                        source_b_path=str(source_b_path),
                        error=f"Report 2 Source B file missing: {source_b_path}",
                    )

            process_kwargs: dict = {
                "source_a_path": source_a_path,
                "report_slug": canonical,
                "source_b_path": source_b_path,
            }
            if "column_selection" in inspect.signature(processor.process).parameters:
                process_kwargs["column_selection"] = column_selection

            processing_result = processor.process(**process_kwargs)
            processing_result.attempted = True
            processing_result.processor_used = processor.processor_name

            if processing_result.success:
                log_automation_event(
                    logger,
                    "phase8_completed",
                    excel_path=processing_result.excel_path,
                    pdf_path=processing_result.pdf_path,
                    processed_row_count=processing_result.processed_row_count,
                    source_a_path=processing_result.source_a_path,
                    source_b_path=processing_result.source_b_path,
                    source_a_rows=processing_result.source_a_rows,
                    source_b_rows=processing_result.source_b_rows,
                )
            else:
                log_automation_event(
                    logger,
                    "phase8_failed",
                    error=processing_result.error,
                )

            return processing_result

    except Exception as exc:
        logger.exception("Phase 8 processing failed")
        log_automation_event(logger, "phase8_error", error=str(exc))
        return ProcessingResult(
            attempted=True,
            success=False,
            processor_used=processor.processor_name if processor else None,
            error=str(exc),
        )
