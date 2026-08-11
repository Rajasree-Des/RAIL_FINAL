"""Post-generation verification for report Excel/PDF outputs."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.automation.formatting.pdf_fonts import pdf_title_style
from app.automation.formatting.pdf_table import (
    build_fitted_table,
    build_wrapped_fitted_table,
)
from app.automation.formatting.text_pipeline import normalize_report_title, verify_text_rendering
from app.automation.processing.output_columns import (
    NAMESPACED_REPORT_SLUGS,
    REMOVED_OUTPUT_LABELS,
    REPORT5_VISIBLE_LABELS,
    REPORT6_VISIBLE_LABELS,
)
from app.automation.report_keys import canonicalize_report_key

_SLUG_EXPECTED_HEADERS: dict[str, list[str]] = {
    "scr-train": REPORT5_VISIBLE_LABELS,
    "report5": REPORT5_VISIBLE_LABELS,
    "scr-station": REPORT6_VISIBLE_LABELS,
    "report6_station": REPORT6_VISIBLE_LABELS,
}

_SCR_SLUGS = frozenset({"scr-train", "report5", "scr-station", "report6_station"})


def _verify_pdf_table_layout(
    *,
    report_slug: str,
    table_data: list[list[str]],
    table,
    pagesize: tuple[float, float],
    margin: float,
) -> None:
    """Build into memory to catch ReportLab LayoutError before artifact registration."""
    buffer = BytesIO()
    title_slug = "scr-train" if report_slug in {"scr-train", "report5"} else "scr-station"
    doc = SimpleDocTemplate(
        buffer,
        pagesize=pagesize,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
    )
    story = [
        Paragraph(
            normalize_report_title(
                f"Rail Madad Report layout verification on date 01-01-2026",
                report_slug=title_slug,
            ),
            pdf_title_style("PdfVerifyTitle"),
        ),
        Spacer(1, 12),
        table,
    ]
    doc.build(story)
    payload = buffer.getvalue()
    if not payload.startswith(b"%PDF-"):
        raise ValueError(f"PDF layout verification did not produce a valid PDF for {report_slug}")


def _raise_unapproved_output_column(report_slug: str, labels: set[str]) -> None:
    raise ValueError(
        f"UNAPPROVED_OUTPUT_COLUMN: Report {report_slug} contains unapproved columns: "
        f"{sorted(labels)}"
    )


def verify_report_output(
    *,
    report_slug: str,
    headers: list[str],
    rows: list[list[str]],
    pdf_path: str | Path,
    excel_path: str | Path | None = None,
) -> None:
    """Raise ValueError when final output fails column or PDF layout checks."""
    slug = canonicalize_report_key(report_slug)
    if slug not in NAMESPACED_REPORT_SLUGS and slug not in _SCR_SLUGS:
        raise ValueError(f"Unknown report slug for output verification: {slug}")

    removed = REMOVED_OUTPUT_LABELS & set(headers)
    if removed and slug not in _SCR_SLUGS:
        _raise_unapproved_output_column(slug, removed)

    if slug in NAMESPACED_REPORT_SLUGS:
        if len(headers) < 1:
            raise ValueError(f"Report {slug} requires at least one output column")
        if rows:
            id_headers = {"Organisation", "Division", "Feedback Organisation"}
            total_found = False
            for row in rows[-1:]:
                for value in row:
                    if "total" in str(value or "").lower():
                        total_found = True
                        break
                if any(header in id_headers for header in headers):
                    for header in ("Organisation", "Division", "Feedback Organisation"):
                        if header in headers:
                            idx = headers.index(header)
                            if "total" in str(rows[-1][idx] or "").lower():
                                total_found = True
            if not total_found and any(h in headers for h in ("Organisation", "Division")):
                pass  # identifier hidden — total may appear under numeric cols only
    elif slug in _SCR_SLUGS:
        if len(headers) < 1:
            raise ValueError(f"Report {slug} requires at least one output column")
        # Dynamic SCR projection: only block globally removed legacy labels.
        # User-selected catalog columns (e.g. Created On on Report 6) must be allowed.

    pdf = Path(pdf_path)
    if not pdf.is_file() or pdf.stat().st_size <= 0:
        raise ValueError(f"PDF missing or empty: {pdf}")
    if pdf.read_bytes()[:5] != b"%PDF-":
        raise ValueError(f"Invalid PDF header: {pdf}")

    if excel_path is not None:
        excel = Path(excel_path)
        if not excel.is_file() or excel.stat().st_size <= 0:
            raise ValueError(f"Excel missing or empty: {excel}")

    verify_text_rendering(
        report_slug=slug,
        headers=headers,
        rows=rows,
        pdf_path=pdf_path,
    )

    table_data: list[list[str]] = [headers, *rows]
    style_commands = [("GRID", (0, 0), (-1, -1), 0.5, colors.black)]
    if slug in _SCR_SLUGS:
        table, pagesize, margin = build_wrapped_fitted_table(
            table_data,
            style_commands,
        )
    else:
        table, pagesize, margin = build_fitted_table(table_data, style_commands)

    usable = pagesize[0] - (2 * margin)
    wrapped_w, _ = table.wrap(usable, pagesize[1])
    if wrapped_w > usable + 1.0:
        raise ValueError(
            f"Report {slug} PDF table width {wrapped_w:.1f} exceeds usable {usable:.1f}"
        )
    if slug in _SCR_SLUGS:
        _verify_pdf_table_layout(
            report_slug=slug,
            table_data=table_data,
            table=table,
            pagesize=pagesize,
            margin=margin,
        )
