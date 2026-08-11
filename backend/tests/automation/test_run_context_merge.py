"""RunContext.merge_result / store_partial deferred success+pending behavior."""

from __future__ import annotations

from app.automation.run_context import RunContext
from app.automation.schemas import ReportResult
from app.automation.timing import RunTiming


PENDING = "Extracted; ingest/process pending"


def _ctx() -> RunContext:
    return RunContext(run_id="merge-test", timing=RunTiming(run_id="merge-test"))


def test_merge_success_clears_pending_error():
    ctx = _ctx()
    ctx.store_partial(
        ReportResult(
            slug="train-no",
            dataset_key="train-no",
            status="partial_success",
            error=PENDING,
        )
    )
    ctx.merge_result(
        ReportResult(
            slug="train-no",
            dataset_key="train-no",
            status="success",
            ingestion_success=True,
            processing_success=True,
            excel_path="/tmp/a.xlsx",
            pdf_path="/tmp/a.pdf",
            pdf_download_url="/api/v1/automation/artifacts/p/download",
            pdf_preview_url="/api/v1/automation/artifacts/p/preview",
            excel_download_url="/api/v1/automation/artifacts/e/download",
        )
    )
    merged = ctx.get_results()[0]
    assert merged.status == "success"
    assert merged.error is None
    assert merged.pdf_download_url


def test_store_partial_pending_does_not_downgrade_success():
    ctx = _ctx()
    ctx.merge_result(
        ReportResult(
            slug="scr-train",
            dataset_key="scr-train",
            status="success",
            ingestion_success=True,
            processing_success=True,
        )
    )
    ctx.store_partial(
        ReportResult(
            slug="scr-train",
            dataset_key="scr-train",
            status="partial_success",
            error=PENDING,
        )
    )
    merged = ctx.get_results()[0]
    assert merged.status == "success"
    assert merged.error is None


def test_merge_pending_does_not_downgrade_success():
    ctx = _ctx()
    ctx.store_partial(
        ReportResult(slug="scr-station", dataset_key="scr-station", status="success")
    )
    ctx.merge_result(
        ReportResult(
            slug="scr-station",
            dataset_key="scr-station",
            status="partial_success",
            error=PENDING,
        )
    )
    merged = ctx.get_results()[0]
    assert merged.status == "success"
    assert merged.error is None


def test_merge_failed_clears_pending_and_keeps_error():
    ctx = _ctx()
    ctx.store_partial(
        ReportResult(
            slug="train-no",
            dataset_key="train-no",
            status="partial_success",
            error=PENDING,
        )
    )
    ctx.merge_result(
        ReportResult(
            slug="train-no",
            dataset_key="train-no",
            status="failed",
            error="Ingestion failed",
        )
    )
    merged = ctx.get_results()[0]
    assert merged.status == "failed"
    assert merged.error == "Ingestion failed"


def test_processing_failure_merges_as_failed_not_success():
    """Terminal ingest/process failures must not remain success."""
    ctx = _ctx()
    ctx.store_partial(
        ReportResult(
            slug="scr-train",
            dataset_key="scr-train",
            status="partial_success",
            error=PENDING,
            source_csv_path="/tmp/x.csv",
        )
    )
    ctx.merge_result(
        ReportResult(
            slug="scr-train",
            dataset_key="scr-train",
            status="failed",
            error="REPORT5_EXCEL_VALIDATION_FAILED: header mismatch",
            ingestion_success=True,
            processing_success=False,
        )
    )
    merged = ctx.get_results()[0]
    assert merged.status == "failed"
    assert merged.processing_success is False
    assert "EXCEL_VALIDATION_FAILED" in (merged.error or "")
