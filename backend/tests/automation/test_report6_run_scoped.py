"""Report 6 run-scoped source, ingestion count, and processor row guards."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.automation.processing.report6_processor import Report6Processor
from app.automation.scr_field_map import canonicalize_scr_rows
from app.automation.workflow import ingest_downloaded_file


@pytest.mark.asyncio
async def test_ingest_rejects_report6_row_count_mismatch(tmp_path: Path):
    csv_path = tmp_path / "scr-station_complaints_raw.csv"
    csv_path.write_text("complaintRefNo,complaintMode\nA,S\nB,S\n", encoding="utf-8")

    mock_meta = MagicMock(row_count=2)
    mock_service = AsyncMock()
    mock_service.ensure_dataset_exists = AsyncMock()
    mock_service.ingest_file = AsyncMock(return_value=mock_meta)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("app.infrastructure.database.session.SessionLocal", return_value=mock_session),
        patch("app.features.datasets.service.DatasetService", return_value=mock_service),
    ):
        ok = await ingest_downloaded_file(
            csv_path,
            "scr-station",
            "test",
            expected_row_count=6,
        )

    assert ok is False


def test_processor_rejects_duplicate_complaint_refs(tmp_path: Path):
    processor = Report6Processor()
    csv_path = tmp_path / "dup.csv"
    csv_path.write_text(
        "complaintRefNo,complaintMode,zoneCode\n"
        "2026071910399,S,SC\n"
        "2026071910399,S,SC\n",
        encoding="utf-8",
    )
    result = processor.process(source_a_path=csv_path, report_slug="scr-station")
    assert result.success is False
    assert "REPORT6_ROW_MULTIPLICATION_DETECTED" in (result.error or "")


def test_processor_six_rows_stay_six(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    processor = Report6Processor()
    rows = []
    for idx in range(6):
        rows.append(
            {
                "Ref. No.": f"202607190{idx:04d}",
                "Mode": "Station",
                "Zone": "SC",
                "Div": "SC",
                "Dept": "ENG",
                "Status": "Closed",
                "Train/Station": f"STN{idx}",
                "Comp Type Name": "Security",
                "Sub Type Name": "Others",
                "User ID": "gm_sc",
                "Feedback Remark": "ok",
                "Complaint Description": "desc",
                "Remarks": "remark",
            }
        )
    canonical = canonicalize_scr_rows(rows)
    csv_path = tmp_path / "six.csv"
    import csv

    headers = sorted({k for row in canonical for k in row})
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for row in canonical:
            writer.writerow(row)

    monkeypatch.setattr(
        "app.automation.processing.report6_processor.config.output_excel_dir",
        str(tmp_path / "excel"),
    )
    monkeypatch.setattr(
        "app.automation.processing.report6_processor.config.output_pdf_dir",
        str(tmp_path / "pdf"),
    )
    monkeypatch.setattr(processor, "_find_template", lambda: None)

    result = processor.process(
        source_a_path=csv_path,
        report_slug="scr-station",
        column_selection={
            "configuration_source": "manual_snapshot",
            "selected_column_ids": [
                "scr-station.complaint_ref_no",
                "scr-station.train_station",
            ],
            "column_order": [
                "scr-station.complaint_ref_no",
                "scr-station.train_station",
            ],
        },
    )
    assert result.success is True
    assert result.processed_row_count == 6
