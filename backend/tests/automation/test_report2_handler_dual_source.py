"""Unit tests for Report 2 dual-source handler orchestration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.automation.handlers.report2_handler import Report2Handler
from app.automation.processing.base import ProcessingResult
from app.automation.reports import REPORT_2
from app.automation.table_extractor import ExtractionResult


@pytest.fixture
def handler() -> Report2Handler:
    return Report2Handler()


def _source_a_result(tmp_path: Path) -> ExtractionResult:
    csv_path = tmp_path / "division_comprehensive.csv"
    csv_path.write_text("S.No.,Organisation,Received\n1,Delhi Division,10\n", encoding="utf-8")
    return ExtractionResult(
        success=True,
        csv_path=csv_path,
        data=[["S.No.", "Organisation", "Received"], ["1", "Delhi Division", "10"]],
        row_count=2,
        column_count=3,
    )


def _feedback_ok(tmp_path: Path) -> ExtractionResult:
    csv_path = tmp_path / "report2_division_feedback_raw.csv"
    csv_path.write_text(
        "S.No.,Organisation,Feedback Received\n1,Delhi Division,5\n",
        encoding="utf-8",
    )
    return ExtractionResult(
        success=True,
        csv_path=csv_path,
        data=[["S.No.", "Organisation", "Feedback Received"], ["1", "Delhi Division", "5"]],
        row_count=2,
        column_count=3,
    )


@pytest.mark.asyncio
async def test_handler_fails_when_feedback_missing(
    handler: Report2Handler,
    tmp_path: Path,
):
    page = MagicMock()
    session = MagicMock()
    source_a = _source_a_result(tmp_path)

    with (
        patch.object(handler, "ensure_mis_page", new=AsyncMock(return_value=page)),
        patch.object(handler.navigation, "navigate_to_report", new=AsyncMock()),
        patch.object(
            handler,
            "_apply_filters_with_retry",
            new=AsyncMock(return_value=(MagicMock(), {}, 1)),
        ),
        patch.object(
            handler,
            "_sort_source_a_with_retry",
            new=AsyncMock(return_value=(MagicMock(), page)),
        ),
        patch(
            "app.automation.handlers.report2_handler.extract_with_retry",
            new=AsyncMock(return_value=(source_a, False, False)),
        ),
        patch.object(handler, "reject_empty_table", new=AsyncMock(return_value=False)),
        patch(
            "app.automation.handlers.report2_handler.extract_feedback_division_csv",
            new=AsyncMock(
                return_value=(
                    ExtractionResult(success=False, error="Feedback Division Wise table not found"),
                    False,
                    False,
                )
            ),
        ),
        patch.object(handler, "archive_pdf", new=AsyncMock(return_value=(True, None, None))),
        patch(
            "app.automation.handlers.report2_handler.ingest_downloaded_file",
            new=AsyncMock(return_value=True),
        ) as ingest,
        patch(
            "app.automation.handlers.report2_handler.resolve_report_dir",
            return_value=tmp_path / "division",
        ),
        patch("app.automation.handlers.report2_handler.config") as cfg,
    ):
        cfg.extracted_data_dir = str(tmp_path)
        result = await handler.execute(page, session, REPORT_2)

    assert result.status == "failed" or result.status == "partial_success"
    assert result.error
    assert "Feedback" in (result.error or "") or "Phase 8" in (result.error or "")
    # Must not process Source A alone into finals
    assert result.excel_path is None
    assert result.pdf_path is None
    # Feedback ingest should not succeed when extract failed
    assert ingest.await_count == 0 or all(
        call.args[1] != "division" for call in ingest.await_args_list
    )


@pytest.mark.asyncio
async def test_handler_dual_source_success_path(
    handler: Report2Handler,
    tmp_path: Path,
):
    page = MagicMock()
    session = MagicMock()
    source_a = _source_a_result(tmp_path)
    feedback = _feedback_ok(tmp_path)
    excel = tmp_path / "out.xlsx"
    pdf = tmp_path / "out.pdf"
    excel.write_bytes(b"xlsx")
    pdf.write_bytes(b"%PDF-1.4")

    processing = ProcessingResult(
        success=True,
        excel_path=str(excel),
        pdf_path=str(pdf),
        processor_used="report2_division_wise_processor",
        input_row_count=1,
        processed_row_count=1,
    )

    ingest_calls: list[str] = []

    async def _ingest(path, report_slug, source="html_extracted_csv"):
        ingest_calls.append(report_slug)
        return True

    with (
        patch.object(handler, "ensure_mis_page", new=AsyncMock(return_value=page)),
        patch.object(handler.navigation, "navigate_to_report", new=AsyncMock()),
        patch.object(
            handler,
            "_apply_filters_with_retry",
            new=AsyncMock(return_value=(MagicMock(), {}, 1)),
        ),
        patch.object(
            handler,
            "_sort_source_a_with_retry",
            new=AsyncMock(return_value=(MagicMock(), page)),
        ),
        patch(
            "app.automation.handlers.report2_handler.extract_with_retry",
            new=AsyncMock(return_value=(source_a, False, False)),
        ),
        patch.object(handler, "reject_empty_table", new=AsyncMock(return_value=False)),
        patch(
            "app.automation.handlers.report2_handler.extract_feedback_division_csv",
            new=AsyncMock(return_value=(feedback, False, False)),
        ),
        patch.object(handler, "archive_pdf", new=AsyncMock(return_value=(True, None, None))),
        patch(
            "app.automation.handlers.report2_handler.ingest_downloaded_file",
            new=AsyncMock(side_effect=_ingest),
        ),
        patch.object(handler, "invoke_processor", new=AsyncMock(return_value=processing)),
        patch.object(
            handler,
            "_register_report2_artifacts",
            new=AsyncMock(side_effect=lambda r: r),
        ),
        patch(
            "app.automation.handlers.report2_handler.resolve_report_dir",
            return_value=tmp_path / "division",
        ),
        patch("app.automation.handlers.report2_handler.config") as cfg,
    ):
        cfg.extracted_data_dir = str(tmp_path)
        result = await handler.execute(page, session, REPORT_2)

    assert result.status == "success"
    assert result.excel_path == str(excel)
    assert result.pdf_path == str(pdf)
    assert "division_feedback" in ingest_calls
    assert "division" in ingest_calls
    assert result.row_counts.get("feedback") == 2
    assert result.row_counts.get("comprehensive") == 2
