"""Unit tests for workflow helpers used by Report 1 handler."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.automation.schemas import AutomationStartResult
from app.automation.workflow import (
    FEEDBACK_DATASET_ID,
    FEEDBACK_ZONE_FILENAME,
    attempt_feedback_extract,
    extract_feedback_zone_csv,
    ingest_downloaded_file,
)


def _feedback_table_data() -> list[list[str]]:
    return [
        [
            "Organisation",
            "Feedback Received",
            "% Feedback",
            "Excellent",
            "Satisfactory",
            "Unsatisfactory",
            "% Unsatisfactory",
        ],
        ["Northern Railway", "50", "10.5", "20", "20", "10", "20.0"],
    ]


@pytest.mark.asyncio
async def test_dual_ingestion_keys():
    """Comprehensive and Feedback use distinct dataset keys."""
    assert FEEDBACK_DATASET_ID == "report1_feedback"
    assert FEEDBACK_ZONE_FILENAME == "report1_feedback_zone_raw.csv"


@pytest.mark.asyncio
async def test_ingest_downloaded_file_success(tmp_path: Path):
    csv_path = tmp_path / "report1.csv"
    csv_path.write_text("a,b\n1,2\n", encoding="utf-8")

    with (
        patch("app.infrastructure.database.session.SessionLocal") as mock_session_local,
        patch("app.features.datasets.service.DatasetService") as mock_service_cls,
    ):
        mock_db = AsyncMock()
        mock_session_local.return_value.__aenter__.return_value = mock_db
        mock_service = AsyncMock()
        mock_service_cls.return_value = mock_service
        result = await ingest_downloaded_file(csv_path, "report1", source="html_extracted_csv")

    assert result is True
    mock_service.ingest_file.assert_awaited_once()


def test_automation_start_result_schema_still_available():
    """AutomationStartResult remains available for legacy consumers."""
    result = AutomationStartResult(
        success=True,
        connected=True,
        tab_found=True,
        feedback_extracted=True,
        feedback_csv_path="storage/extracted/report1/report1_feedback_zone_raw.csv",
    )
    assert result.feedback_extracted is True
    assert result.feedback_csv_path.endswith("report1_feedback_zone_raw.csv")


@pytest.mark.asyncio
async def test_extract_feedback_zone_csv_retries_once():
    page = MagicMock()
    extractor = MagicMock()
    navigation = MagicMock()
    filter_service = MagicMock()
    discovery = MagicMock()
    generator = MagicMock()
    session = MagicMock()
    session.verify_mis_session = AsyncMock(return_value=MagicMock(valid=True))

    fail_result = MagicMock(success=False, validation_result=None, html=None, error="fail")
    ok_result = MagicMock(success=True, row_count=2, validation_result=None)

    with patch(
        "app.automation.workflow.attempt_feedback_extract",
        AsyncMock(side_effect=[fail_result, ok_result]),
    ):
        with patch(
            "app.automation.workflow.save_failure_artifacts",
            AsyncMock(),
        ):
            result, retry_attempted, retry_succeeded = await extract_feedback_zone_csv(
                page,
                extractor,
                navigation,
                filter_service,
                discovery,
                generator,
                session,
                max_retries=1,
            )

    assert retry_attempted is True
    assert retry_succeeded is True
    assert result.success is True
