"""Prepare normalized tabular output for all report renderers."""

from __future__ import annotations

from app.automation.formatting.text_safe import (
    UnsupportedTextRenderingError,
    contains_non_latin1,
    contains_rendering_risk_markers,
    field_kind_for_header,
    normalize_report_text,
    row_identifier_from_values,
)
from app.automation.formatting.pdf_fonts import unicode_font_embedded


def normalize_report_title(title: str, *, report_slug: str = "") -> str:
    return normalize_report_text(
        title,
        field_kind="header",
        report_slug=report_slug,
        column_name="title",
    )


def prepare_output_for_rendering(
    report_slug: str,
    headers: list[str],
    rows: list[list[str]],
) -> tuple[list[str], list[list[str]]]:
    """Apply shared text normalization to headers and body rows before Excel/PDF."""
    norm_headers = [
        normalize_report_text(
            header,
            field_kind="header",
            report_slug=report_slug,
            column_name=header,
        )
        for header in headers
    ]
    kinds = [field_kind_for_header(header) for header in headers]
    normalized_rows: list[list[str]] = []
    for row in rows:
        row_id = row_identifier_from_values(row)
        normalized_rows.append(
            [
                normalize_report_text(
                    row[col_idx] if col_idx < len(row) else "",
                    field_kind=kinds[col_idx],
                    report_slug=report_slug,
                    column_name=headers[col_idx],
                    row_identifier=row_id,
                )
                for col_idx in range(len(headers))
            ]
        )
    return norm_headers, normalized_rows


def verify_text_rendering(
    *,
    report_slug: str,
    headers: list[str],
    rows: list[list[str]],
    pdf_path: str | None = None,
) -> None:
    """Raise UnsupportedTextRenderingError when rendered output still has risk markers."""
    has_unicode = False
    for row in rows:
        for col_idx, value in enumerate(row):
            if contains_rendering_risk_markers(value):
                column = headers[col_idx] if col_idx < len(headers) else str(col_idx)
                raise UnsupportedTextRenderingError(
                    f"UNSUPPORTED_TEXT_RENDERING: Report {report_slug} row {row!r} "
                    f"column {column!r} contains replacement/black-square markers after normalization"
                )
            if contains_non_latin1(value):
                has_unicode = True

    for header in headers:
        if contains_rendering_risk_markers(header):
            raise UnsupportedTextRenderingError(
                f"UNSUPPORTED_TEXT_RENDERING: Report {report_slug} header {header!r} "
                "contains replacement/black-square markers"
            )
        if contains_non_latin1(header):
            has_unicode = True

    if has_unicode and pdf_path is not None and not unicode_font_embedded():
        from pathlib import Path

        pdf = Path(pdf_path)
        if pdf.is_file():
            raw = pdf.read_bytes()
            if b"/Subtype /Type0" not in raw and b"DejaVu" not in raw and b"Noto" not in raw:
                raise UnsupportedTextRenderingError(
                    f"UNSUPPORTED_TEXT_RENDERING: Report {report_slug} contains Unicode text "
                    "but PDF was generated without an embedded Unicode font"
                )
