"""Tests for post-generation PDF/Excel output verification."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.automation.formatting.pdf_verify import verify_report_output
from app.automation.processing.output_columns import (
    REPORT1_VISIBLE_LABELS,
    REPORT5_VISIBLE_LABELS,
)


def test_verify_report_output_accepts_valid_r1_headers(tmp_path: Path):
    pdf = tmp_path / "out.pdf"
    pdf.write_bytes(b"%PDF-1.4\n% minimal")
    excel = tmp_path / "out.xlsx"
    excel.write_bytes(b"PK\x03\x04")
    rows = [["1", "Org", "10", "1", "9", "1", "90", "5", "50", "1", "2", "1", "20"]]
    rows.append([""] + ["Total"] + [""] * (len(REPORT1_VISIBLE_LABELS) - 2))
    verify_report_output(
        report_slug="report1",
        headers=REPORT1_VISIBLE_LABELS,
        rows=rows,
        pdf_path=pdf,
        excel_path=excel,
    )


def test_verify_report_output_rejects_wrong_column_count(tmp_path: Path):
    pdf = tmp_path / "out.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    with pytest.raises(ValueError, match="column mismatch"):
        verify_report_output(
            report_slug="report5",
            headers=["S.No.", "Complaint Ref Number"],
            rows=[],
            pdf_path=pdf,
        )


def test_verify_report_output_rejects_invalid_pdf_header(tmp_path: Path):
    pdf = tmp_path / "bad.pdf"
    pdf.write_text("not a pdf")
    with pytest.raises(ValueError, match="Invalid PDF"):
        verify_report_output(
            report_slug="report5",
            headers=REPORT5_VISIBLE_LABELS,
            rows=[],
            pdf_path=pdf,
        )


def test_verify_report_output_rejects_removed_labels(tmp_path: Path):
    pdf = tmp_path / "out.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    bad_headers = list(REPORT5_VISIBLE_LABELS)
    bad_headers[1] = "Ref. No."
    with pytest.raises(ValueError, match="UNAPPROVED_OUTPUT_COLUMN"):
        verify_report_output(
            report_slug="report5",
            headers=bad_headers,
            rows=[],
            pdf_path=pdf,
        )


def test_verify_report_output_rejects_department_in_report5(tmp_path: Path):
    pdf = tmp_path / "out.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    bad_headers = list(REPORT5_VISIBLE_LABELS)
    bad_headers.insert(8, "Department")
    with pytest.raises(ValueError, match="UNAPPROVED_OUTPUT_COLUMN"):
        verify_report_output(
            report_slug="report5",
            headers=bad_headers,
            rows=[],
            pdf_path=pdf,
        )
