"""SCR Report 5/6 template Excel path must pass header validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.automation.processing import report5_processor, report6_processor
from app.automation.processing.report5_processor import Report5Processor
from app.automation.processing.report6_processor import Report6Processor

FIXTURES_R5 = Path(__file__).resolve().parent.parent / "fixtures" / "report5"
FIXTURES_R6 = Path(__file__).resolve().parent.parent / "fixtures" / "report6"


@pytest.fixture
def output_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(report5_processor.config, "output_excel_dir", str(tmp_path / "excel"))
    monkeypatch.setattr(report5_processor.config, "output_pdf_dir", str(tmp_path / "pdf"))
    monkeypatch.setattr(report6_processor.config, "output_excel_dir", str(tmp_path / "excel"))
    monkeypatch.setattr(report6_processor.config, "output_pdf_dir", str(tmp_path / "pdf"))


def test_report5_template_excel_path_reaches_success(
    tmp_path: Path,
    output_dirs: None,
) -> None:
    csv_path = tmp_path / "scr-train_complaints_raw.csv"
    csv_path.write_text(
        (FIXTURES_R5 / "train_complaints_raw.csv").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    result = Report5Processor().process(source_a_path=csv_path, report_slug="scr-train")

    assert result.success is True, result.error
    assert result.excel_path is not None
    assert result.pdf_path is not None
    assert Path(result.excel_path).stat().st_size > 0
    assert Path(result.pdf_path).read_bytes()[:4] == b"%PDF"


def test_report6_template_excel_path_reaches_success(
    tmp_path: Path,
    output_dirs: None,
) -> None:
    csv_path = tmp_path / "scr-station_complaints_raw.csv"
    csv_path.write_text(
        (FIXTURES_R6 / "station_complaints_raw.csv").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    result = Report6Processor().process(source_a_path=csv_path, report_slug="scr-station")

    assert result.success is True, result.error
    assert result.excel_path is not None
    assert result.pdf_path is not None
    assert Path(result.excel_path).stat().st_size > 0
    assert Path(result.pdf_path).read_bytes()[:4] == b"%PDF"
