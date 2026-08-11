"""Tests for SCR PDF full-cell wrapping without horizontal overflow."""

from __future__ import annotations

from pathlib import Path

import pytest
from reportlab.lib import colors
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.automation.formatting.pdf_fonts import pdf_title_style
from app.automation.formatting.pdf_table import (
    MIN_FONT_SIZE,
    allocate_tier_column_widths,
    build_wrapped_fitted_table,
    prepare_wrapped_table_data,
)
from app.automation.formatting.pdf_verify import verify_report_output


def _scr_headers() -> list[str]:
    return [
        "S.No.",
        "Complaint Ref Number",
        "Created On",
        "Train/Station",
        "Comp Type Name",
        "Sub Type Name",
        "Zone Code",
        "Div Code",
        "Feedback Remark",
        "Train Name For Report",
        "Complaint Description",
        "Remarks",
        "User ID",
    ]


def _scr_row(*, long_text: str) -> list[str]:
    return [
        "1",
        "2026071503196",
        "15-07-26 19:13",
        "12759",
        "Coach - Maintenance",
        "Jerks/Abnormal Sound",
        "SC",
        "SC",
        long_text,
        "TBM-HYB CHARMINAR EXP [SUPERFAST]",
        long_text,
        long_text,
        "cnw_sc_sc",
    ]


def test_scr_pdf_wraps_all_cells_and_fits_width():
    headers = _scr_headers()
    long_text = (
        "There are no rail neer bottles available. They are selling 750ml bottles at 20rs. "
        "No option for 14rs bottles on the irctc stalls and the vendor refused to provide a receipt."
    )
    table_data = [headers, _scr_row(long_text=long_text)]
    style_commands = [("GRID", (0, 0), (-1, -1), 0.5, colors.black)]

    table, pagesize, margin = build_wrapped_fitted_table(table_data, style_commands)
    usable = pagesize[0] - (2 * margin)
    wrapped_w, _ = table.wrap(usable, pagesize[1])
    assert wrapped_w <= usable + 1.0

    wrapped = prepare_wrapped_table_data(
        table_data,
        headers,
        set(),
        MIN_FONT_SIZE,
        wrap_all=True,
    )
    assert all(hasattr(wrapped[0][idx], "text") for idx in range(len(headers)))
    assert all(hasattr(wrapped[1][idx], "text") for idx in range(len(headers)))


def test_scr_pdf_tall_row_splits_across_pages_without_layout_error(tmp_path: Path):
    headers = _scr_headers()
    long_text = "Word " * 500
    rows = [_scr_row(long_text=long_text)]
    table_data = [headers, *rows]
    style_commands = [("GRID", (0, 0), (-1, -1), 0.5, colors.black)]

    table, pagesize, margin = build_wrapped_fitted_table(table_data, style_commands)
    pdf_path = tmp_path / "scr_tall_row.pdf"
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=pagesize,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
    )
    story = [
        Paragraph("Report 5 layout test", pdf_title_style("Report5TallRowTest")),
        Spacer(1, 12),
        table,
    ]
    doc.build(story)

    assert pdf_path.is_file()
    assert pdf_path.read_bytes()[:5] == b"%PDF-"
    assert pdf_path.stat().st_size > 0

    verify_report_output(
        report_slug="scr-train",
        headers=headers,
        rows=rows,
        pdf_path=pdf_path,
    )


def test_scr_pdf_preserves_all_rows_and_columns(tmp_path: Path):
    headers = _scr_headers()
    rows = [
        _scr_row(long_text="Short remark one"),
        [
            "2",
            "2026071503197",
            "15-07-26 20:13",
            "12760",
            "Coach - Maintenance",
            "Cleanliness",
            "SC",
            "SC",
            "Word " * 400,
            "TBM-HYB CHARMINAR EXP [SUPERFAST]",
            "Word " * 400,
            "Word " * 400,
            "cnw_sc_sc",
        ],
    ]
    table_data = [headers, *rows]
    style_commands = [("GRID", (0, 0), (-1, -1), 0.5, colors.black)]
    table, pagesize, margin = build_wrapped_fitted_table(table_data, style_commands)
    pdf_path = tmp_path / "scr_multi_row.pdf"
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=pagesize,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
    )
    doc.build(
        [
            Paragraph("Report 5 rows preserved", pdf_title_style("Report5RowsTest")),
            Spacer(1, 12),
            table,
        ]
    )
    verify_report_output(
        report_slug="scr-train",
        headers=headers,
        rows=rows,
        pdf_path=pdf_path,
    )
    assert len(rows) == 2
    assert len(headers) == 13


def test_allocate_tier_widths_no_department_gap():
    headers = [
        "S.No.",
        "Complaint Ref Number",
        "Created On",
        "Train/Station",
        "Comp Type Name",
        "Sub Type Name",
        "Zone Code",
        "Div Code",
        "Feedback Remark",
        "Train Name For Report",
        "Complaint Description",
        "Remarks",
        "User ID",
    ]
    assert "Department" not in headers
    assert "Status" not in headers
    widths = allocate_tier_column_widths(headers, 800.0)
    assert len(widths) == 13
    assert abs(sum(widths) - 800.0) < 0.01
    wide_indices = [headers.index("Feedback Remark"), headers.index("Complaint Description"), headers.index("Remarks")]
    compact_indices = [headers.index("S.No."), headers.index("Zone Code")]
    assert widths[wide_indices[0]] > widths[compact_indices[0]]
