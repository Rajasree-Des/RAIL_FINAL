"""Map automation run progress to manual-generation UI statuses."""

from __future__ import annotations

from app.automation.schemas import ReportResult
from app.features.reports.schemas import ManualUiStatus


def extraction_success(report: ReportResult | None) -> bool:
    if report is None:
        return False
    if report.source_row_count and report.source_row_count > 0:
        return True
    if report.source_csv_path:
        return True
    if report.row_counts:
        return any(v and v > 0 for v in report.row_counts.values() if isinstance(v, (int, float)))
    return False


def map_manual_status(
    *,
    run_status: str,
    report: ReportResult | None,
    artifact_ready: bool,
) -> ManualUiStatus:
    if run_status in {"failed", "stopped", "cancelled"}:
        return "Failed"
    if report and report.status == "failed":
        return "Failed"
    if (
        run_status == "completed"
        and report
        and report.error
        and not report.processing_success
    ):
        return "Failed"

    if report and report.status == "success":
        if (
            extraction_success(report)
            and report.ingestion_success
            and report.processing_success
            and artifact_ready
        ):
            return "Completed"
        if report.processing_success and not artifact_ready:
            return "Generating Excel/PDF"

    if report:
        if report.processing_attempted and not report.processing_success:
            return "Processing"
        if report.ingestion_success and not report.processing_success:
            return "Processing"
        if extraction_success(report) and not report.ingestion_success:
            return "Ingesting"
        if extraction_success(report):
            return "Ingesting"

    if run_status == "running":
        return "Extracting"
    if run_status == "completed" and report and report.status == "success" and artifact_ready:
        return "Completed"
    if run_status == "completed" and report and report.status == "failed":
        return "Failed"

    return "Waiting"
