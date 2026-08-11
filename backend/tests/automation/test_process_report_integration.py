"""Integration tests: process_report completes Reports 3–6 without column_selection errors."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.automation.processing.service import process_report
from app.features.datasets.service import DatasetService

FIXTURES_R3 = Path(__file__).resolve().parent.parent / "fixtures" / "report3"


@pytest.mark.asyncio
async def test_process_report_train_no_succeeds_with_manual_column_selection_kwarg(
    test_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    csv_path = tmp_path / "train-no.csv"
    csv_path.write_text(
        (FIXTURES_R3 / "trainwise_raw.csv").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.automation.processing.report3_processor.config.output_excel_dir",
        str(tmp_path / "output" / "excel"),
    )
    monkeypatch.setattr(
        "app.automation.processing.report3_processor.config.output_pdf_dir",
        str(tmp_path / "output" / "pdf"),
    )

    service = DatasetService(test_session)
    await service.ensure_dataset_exists("train-no")
    await service.ingest_file("train-no", file_path=csv_path, source_filename=csv_path.name)

    result = await process_report(
        "train-no",
        True,
        column_selection={
            "report_slug": "train-no",
            "selected_column_ids": [],
            "column_order": [],
        },
    )
    assert result.success is True
    assert result.excel_path
    assert result.pdf_path
    assert Path(result.excel_path).stat().st_size > 0
    assert Path(result.pdf_path).read_bytes()[:5] == b"%PDF-"


@pytest.mark.asyncio
async def test_process_report_types_succeeds_with_column_selection_kwarg(
    test_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    run_dir = tmp_path / "extracted" / "types" / "run-test"
    run_dir.mkdir(parents=True)
    security_csv = run_dir / "report4_security_raw.csv"
    security_csv.write_text(
        "S.No.,Train No.,Train Name,Owning Zone,Owning Division,Received\n"
        "1,12345,Test Train,South Central Railway,SC,50\n",
        encoding="utf-8",
    )
    index_path = run_dir / "types_combined_index.csv"
    index_path.write_text(
        "type_name,status,csv_path,row_count,error\n"
        f"Security,success,{security_csv},1,\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.automation.processing.report4_processor.config.output_excel_dir",
        str(tmp_path / "output" / "excel"),
    )
    monkeypatch.setattr(
        "app.automation.processing.report4_processor.config.output_pdf_dir",
        str(tmp_path / "output" / "pdf"),
    )

    service = DatasetService(test_session)
    await service.ensure_dataset_exists("types")
    await service.ingest_file("types", file_path=index_path, source_filename=index_path.name)

    result = await process_report("types", True, column_selection={"report_slug": "types"})
    assert result.success is True
    assert result.excel_path and result.pdf_path


@pytest.mark.asyncio
async def test_process_report_scr_station_empty_state_succeeds(
    test_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    csv_path = tmp_path / "scr-station.csv"
    csv_path.write_text("Ref. No.,Mode\n", encoding="utf-8")
    monkeypatch.setattr(
        "app.automation.processing.report6_processor.config.output_excel_dir",
        str(tmp_path / "output" / "excel"),
    )
    monkeypatch.setattr(
        "app.automation.processing.report6_processor.config.output_pdf_dir",
        str(tmp_path / "output" / "pdf"),
    )

    service = DatasetService(test_session)
    await service.ensure_dataset_exists("scr-station")
    await service.ingest_file("scr-station", file_path=csv_path, source_filename=csv_path.name)

    result = await process_report(
        "scr-station",
        True,
        column_selection={"report_slug": "scr-station"},
    )
    assert result.success is True
    assert result.excel_path and result.pdf_path
