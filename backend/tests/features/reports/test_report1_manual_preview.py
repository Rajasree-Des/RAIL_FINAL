"""Report 1 manual-run preview must prefer processed Excel over raw Source A CSV."""

from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import Workbook

from app.features.reports.preview import read_preview_rows


def _write_processed_excel(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Rail Madad Report No 1"])
    sheet.append(["Organisation", "Received", "Feedback Received"])
    sheet.append(["South Central Railway", 232, 180])
    sheet.append(["Total", 9321, 1800])
    workbook.save(path)
    workbook.close()


def _write_raw_comprehensive_csv(path: Path) -> None:
    path.write_text(
        "S.No.,Organisation,Received\n"
        "17,South Central Railway,232\n"
        "20,Total,9321\n",
        encoding="utf-8",
    )


def test_read_preview_rows_skips_csv_when_fallback_disabled(tmp_path: Path):
    excel_path = tmp_path / "processed.xlsx"
    csv_path = tmp_path / "raw_comprehensive.csv"
    _write_processed_excel(excel_path)
    _write_raw_comprehensive_csv(csv_path)

    rows = read_preview_rows(
        excel_path=str(excel_path),
        csv_path=str(csv_path),
        visible_columns=["Organisation", "Received", "Feedback Received"],
        allow_csv_fallback=False,
    )
    assert len(rows) >= 1
    assert "Feedback Received" in rows[0]
    assert rows[0]["Organisation"] == "South Central Railway"


def test_read_preview_rows_uses_csv_when_fallback_allowed(tmp_path: Path):
    csv_path = tmp_path / "raw_comprehensive.csv"
    _write_raw_comprehensive_csv(csv_path)

    rows = read_preview_rows(
        excel_path=None,
        csv_path=str(csv_path),
        visible_columns=["Organisation", "Received"],
        allow_csv_fallback=True,
    )
    assert rows[0]["Organisation"] == "South Central Railway"
    assert "Feedback Received" not in rows[0]


def test_read_preview_rows_empty_when_excel_missing_and_no_csv_fallback(tmp_path: Path):
    csv_path = tmp_path / "raw_comprehensive.csv"
    _write_raw_comprehensive_csv(csv_path)

    rows = read_preview_rows(
        excel_path=None,
        csv_path=str(csv_path),
        visible_columns=["Organisation", "Received"],
        allow_csv_fallback=False,
    )
    assert rows == []
