"""Shared PDF table layout helpers (fit width, landscape, A3/A2 fallback, text wrap)."""

from __future__ import annotations

import re
from xml.sax.saxutils import escape

from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A2, A3, A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import LongTable, Paragraph, Table, TableStyle

from app.automation.formatting.pdf_fonts import ensure_pdf_unicode_fonts, pdf_font_bold, pdf_font_regular
from app.automation.formatting.text_safe import field_kind_for_header, normalize_report_text

# Safe margins so first/last columns are not clipped by the page edge.
SAFE_MARGIN_PT = 18.0
MIN_FONT_SIZE = 8.0
MAX_FONT_SIZE = 8.0
REPORT5_MIN_FONT_SIZE = 8.5
REPORT5_MAX_FONT_SIZE = 8.5

COMPACT_HEADERS = frozenset(
    {
        "S.No.",
        "Zone Code",
        "Div Code",
        "User ID",
        "PNR/UTS No.",
        "Avg. Diff",
        "Final Status",
    }
)
MODERATE_HEADERS = frozenset(
    {
        "Complaint Ref Number",
        "Created On",
        "Train/Station",
        "Comp Type Name",
        "Sub Type Name",
        "Organisation",
        "Division",
        "Opening Balance",
        "Received",
        "% Share",
        "Closed",
        "Closing Balance",
        "% Disposal",
        "Avg. Disposal Time",
        "Avg. Rating",
        "Avg. Pendency Time",
        "Forwarded",
        "Avg. FRT",
        "Feedback Received",
        "% Feedback",
        "Excellent",
        "Satisfactory",
        "Unsatisfactory",
        "% Unsatisfactory",
    }
)
WIDE_HEADERS = frozenset(
    {"Feedback Remark", "Complaint Description", "Remarks", "Train Name For Report"}
)

_TIER_WEIGHT = {"compact": 0.6, "moderate": 1.0, "wide": 2.5}
_TIER_WIDTH_FRACTION = {"compact": 0.05, "moderate": 0.06, "wide": 0.21}
_WIDE_MEASURE_CHAR_CAP = 36


def landscape_page_candidates(*, start_index: int = 0) -> list[tuple[float, float]]:
    """Prefer A4 landscape; fall back to A3 then A2 when the table is wide."""
    pages = [landscape(A4), landscape(A3), landscape(A2)]
    return pages[start_index:] if start_index else pages


def _cell_text(value: object) -> str:
    return normalize_report_text("" if value is None else value, field_kind="text")


def _header_tier(header: str) -> str:
    if header in WIDE_HEADERS:
        return "wide"
    if header in COMPACT_HEADERS:
        return "compact"
    if header in MODERATE_HEADERS:
        return "moderate"
    return "moderate"


def _escape_paragraph_text(text: str, *, field_kind: str = "text") -> str:
    normalized = normalize_report_text(text, field_kind=field_kind)  # type: ignore[arg-type]
    if field_kind in {"id", "numeric"}:
        return escape(normalized).replace("\n", "<br/>")
    # Soft break opportunities in very long unbroken tokens (text columns only).
    normalized = re.sub(
        r"(\S{41,})",
        lambda match: " ".join(
            match.group(1)[offset : offset + 40]
            for offset in range(0, len(match.group(1)), 40)
        ),
        normalized,
    )
    return escape(normalized).replace("\n", "<br/>")


def _build_table(
    table_data: list[list[object]],
    col_widths: list[float],
    *,
    splittable: bool,
    repeat_rows: int = 1,
) -> Table | LongTable:
    if splittable:
        return LongTable(
            table_data,
            colWidths=col_widths,
            repeatRows=repeat_rows,
            splitByRow=1,
            splitInRow=1,
        )
    return Table(table_data, colWidths=col_widths, repeatRows=repeat_rows)


def _header_min_width(header: str, *, font_name: str, font_size: float, padding: float = 8.0) -> float:
    """Minimum width so header words are not split character-by-character."""
    ensure_pdf_unicode_fonts()
    words = [word for word in str(header or "").split() if word]
    if not words:
        return 24.0
    longest = max(words, key=len)
    return stringWidth(longest, font_name, font_size) + padding


def allocate_tier_column_widths(
    headers: list[str],
    usable_width: float,
    *,
    font_size: float = MIN_FONT_SIZE,
) -> list[float]:
    """Allocate proportional column widths by compact/moderate/wide tier."""
    if not headers:
        return []
    ensure_pdf_unicode_fonts()
    font_name = pdf_font_bold()
    fractions = [_TIER_WIDTH_FRACTION[_header_tier(header)] for header in headers]
    total = sum(fractions)
    if total <= 0:
        equal = usable_width / len(headers)
        return [equal] * len(headers)
    widths = [usable_width * fraction / total for fraction in fractions]
    min_widths = [
        _header_min_width(header, font_name=font_name, font_size=max(font_size, MIN_FONT_SIZE))
        for header in headers
    ]
    for idx, minimum in enumerate(min_widths):
        if widths[idx] < minimum:
            widths[idx] = minimum
    width_total = sum(widths)
    if width_total > usable_width:
        scale = usable_width / width_total
        widths = [width * scale for width in widths]
    return widths


def preferred_column_widths(
    table_data: list[list[object]],
    *,
    font_name: str | None = None,
    font_size: float = 8.0,
    padding: float = 6.0,
    headers: list[str] | None = None,
) -> list[float]:
    """Estimate natural column widths from header + body content."""
    ensure_pdf_unicode_fonts()
    effective_font = font_name or pdf_font_regular()
    if not table_data:
        return []
    col_count = max(len(row) for row in table_data)
    if headers is None and table_data:
        headers = [_cell_text(h) for h in table_data[0]]
    elif headers is None:
        headers = []
    char_width = stringWidth("M", effective_font, font_size)
    widths = [0.0] * col_count
    for row in table_data:
        for idx in range(col_count):
            text = _cell_text(row[idx] if idx < len(row) else "")
            header = headers[idx] if idx < len(headers) else ""
            tier = _header_tier(header)
            if tier == "wide":
                cap = char_width * _WIDE_MEASURE_CHAR_CAP
                measured = min(stringWidth(text, effective_font, font_size), cap) + padding
            else:
                measured = stringWidth(text, effective_font, font_size) + padding
            weight = _TIER_WEIGHT[tier]
            weighted = measured * weight
            if weighted > widths[idx]:
                widths[idx] = weighted
    return [max(w, 22.0) for w in widths]


def fit_column_widths(
    preferred: list[float],
    usable_width: float,
) -> list[float]:
    """Scale column widths to fit usable page width without cropping."""
    if not preferred:
        return []
    total = sum(preferred)
    if total <= 0:
        equal = usable_width / len(preferred)
        return [equal] * len(preferred)
    if total <= usable_width:
        return list(preferred)
    scale = usable_width / total
    return [w * scale for w in preferred]


def choose_landscape_layout(
    table_data: list[list[object]],
    *,
    margin: float = SAFE_MARGIN_PT,
    headers: list[str] | None = None,
    use_tier_widths: bool = False,
    min_font_size: float = MIN_FONT_SIZE,
    max_font_size: float = MAX_FONT_SIZE,
    landscape_start_index: int = 0,
) -> tuple[tuple[float, float], list[float], float, float]:
    """
    Pick landscape page size + colWidths + font size so the table fits one page width.

    Returns (pagesize, col_widths, font_size, margin).
    """
    if headers is None and table_data:
        headers = [_cell_text(h) for h in table_data[0]]
    elif headers is None:
        headers = []

    for pagesize in landscape_page_candidates(start_index=landscape_start_index):
        usable = pagesize[0] - (2 * margin)
        font_size = max_font_size
        if use_tier_widths and headers:
            col_widths = allocate_tier_column_widths(
                headers,
                usable,
                font_size=font_size,
            )
            return pagesize, col_widths, font_size, margin

        while font_size >= min_font_size - 1e-9:
            preferred = preferred_column_widths(
                table_data,
                font_size=font_size,
                headers=headers,
            )
            if sum(preferred) <= usable + 0.5:
                return pagesize, preferred, font_size, margin
            font_size -= 0.5

    pagesize = landscape_page_candidates(start_index=landscape_start_index)[-1]
    usable = pagesize[0] - (2 * margin)
    if use_tier_widths and headers:
        return (
            pagesize,
            allocate_tier_column_widths(headers, usable, font_size=min_font_size),
            min_font_size,
            margin,
        )

    preferred = preferred_column_widths(
        table_data,
        font_size=min_font_size,
        headers=headers,
    )
    return pagesize, fit_column_widths(preferred, usable), min_font_size, margin


def _table_style_commands(
    style_commands: list[tuple],
    font_size: float,
    *,
    valign: str = "MIDDLE",
    bold_row_indices: frozenset[int] | None = None,
    force_center: bool = False,
) -> list[tuple]:
    commands = list(style_commands)
    commands.extend(
        [
            ("FONTSIZE", (0, 0), (-1, -1), font_size),
            ("FONTSIZE", (0, 0), (-1, 0), max(font_size, MIN_FONT_SIZE)),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("VALIGN", (0, 0), (-1, -1), valign),
            ("FONTNAME", (0, 1), (-1, -1), pdf_font_regular()),
            ("FONTNAME", (0, 0), (-1, 0), pdf_font_bold()),
        ]
    )
    if bold_row_indices:
        for row_idx in sorted(bold_row_indices):
            commands.append(("FONTNAME", (0, row_idx), (-1, row_idx), pdf_font_bold()))
    if force_center:
        # Final override: every cell (headers, sub-headers, S.No., names, numbers,
        # percentages, totals, blank merged cells) is centered both ways. Placed
        # last so it wins over any earlier per-column ALIGN/VALIGN commands from
        # callers — fonts, borders, colors, and fills are untouched by this.
        commands.append(("ALIGN", (0, 0), (-1, -1), "CENTER"))
        commands.append(("VALIGN", (0, 0), (-1, -1), "MIDDLE"))
    return commands


def _rescale_if_overflow(
    table_data: list[list[object]],
    table: Table | LongTable,
    col_widths: list[float],
    commands: list[tuple],
    pagesize: tuple[float, float],
    used_margin: float,
    *,
    splittable: bool = False,
) -> Table | LongTable:
    usable = pagesize[0] - (2 * used_margin)
    wrapped_w, _ = table.wrap(usable, pagesize[1])
    if wrapped_w > usable + 1.0:
        scale = usable / wrapped_w
        table = _build_table(
            table_data,
            [w * scale for w in col_widths],
            splittable=splittable,
            repeat_rows=1,
        )
        table.setStyle(TableStyle(commands))
    return table


def build_fitted_table(
    table_data: list[list[object]],
    style_commands: list[tuple],
    *,
    margin: float = SAFE_MARGIN_PT,
    bold_row_indices: frozenset[int] | None = None,
) -> tuple[Table, tuple[float, float], float]:
    """
    Build a Table that fits landscape A4 or A3 without horizontal clipping.

    Returns (table, pagesize, margin).
    """
    pagesize, col_widths, font_size, used_margin = choose_landscape_layout(
        table_data,
        margin=margin,
    )
    table = _build_table(table_data, col_widths, splittable=False, repeat_rows=1)
    commands = _table_style_commands(
        style_commands,
        font_size,
        valign="MIDDLE",
        bold_row_indices=bold_row_indices,
        force_center=True,
    )
    table.setStyle(TableStyle(commands))
    table = _rescale_if_overflow(
        table_data, table, col_widths, commands, pagesize, used_margin, splittable=False
    )
    return table, pagesize, used_margin


def prepare_wrapped_table_data(
    table_data: list[list[object]],
    headers: list[str],
    wrap_headers: set[str],
    font_size: float,
    *,
    wrap_all: bool = False,
    paragraph_alignment: int = TA_LEFT,
) -> list[list[object]]:
    """Convert designated columns to Paragraph objects for in-cell wrapping.

    ``paragraph_alignment`` defaults to left (legacy behaviour for callers that
    don't request centering, e.g. Report 5/6). Callers that must center every
    cell (e.g. Report 4's Top-N table) pass ``TA_CENTER`` explicitly.
    """
    ensure_pdf_unicode_fonts()
    body_style = ParagraphStyle(
        name="PdfCell",
        fontName=pdf_font_regular(),
        fontSize=font_size,
        leading=font_size + 1.5,
        wordWrap="CJK",
        alignment=paragraph_alignment,
    )
    header_style = ParagraphStyle(
        name="PdfHeader",
        fontName=pdf_font_bold(),
        fontSize=max(font_size, MIN_FONT_SIZE),
        leading=max(font_size, MIN_FONT_SIZE) + 1.5,
        wordWrap="CJK",
        alignment=paragraph_alignment,
    )
    wrapped: list[list[object]] = []
    header_kinds = [field_kind_for_header(header) for header in headers]
    for row_idx, row in enumerate(table_data):
        new_row: list[object] = []
        for col_idx, cell in enumerate(row):
            header = headers[col_idx] if col_idx < len(headers) else ""
            kind = header_kinds[col_idx] if col_idx < len(header_kinds) else "text"
            text = _cell_text(cell)
            should_wrap = wrap_all or header in wrap_headers
            if should_wrap:
                style = header_style if row_idx == 0 else body_style
                new_row.append(
                    Paragraph(_escape_paragraph_text(text, field_kind=kind), style)
                )
            else:
                new_row.append(text)
        wrapped.append(new_row)
    return wrapped


def build_wrapped_fitted_table(
    table_data: list[list[object]],
    style_commands: list[tuple],
    *,
    wrap_headers: set[str] | None = None,
    wrap_all: bool = True,
    margin: float = SAFE_MARGIN_PT,
    min_font_size: float = MIN_FONT_SIZE,
    max_font_size: float = MAX_FONT_SIZE,
    landscape_start_index: int = 0,
) -> tuple[Table, tuple[float, float], float]:
    """
    Build a width-fitted table with Paragraph wrapping for long-text columns.

    Returns (table, pagesize, margin).
    """
    if not table_data:
        raise ValueError("table_data must not be empty")
    headers = [_cell_text(h) for h in table_data[0]]
    wrap_set = wrap_headers if wrap_headers is not None else set(WIDE_HEADERS)

    pagesize, col_widths, font_size, used_margin = choose_landscape_layout(
        table_data,
        margin=margin,
        headers=headers,
        use_tier_widths=True,
        min_font_size=min_font_size,
        max_font_size=max_font_size,
        landscape_start_index=landscape_start_index,
    )
    wrapped_data = prepare_wrapped_table_data(
        table_data,
        headers,
        wrap_set,
        font_size,
        wrap_all=wrap_all,
    )
    table = _build_table(wrapped_data, col_widths, splittable=True, repeat_rows=1)
    commands = _table_style_commands(style_commands, font_size, valign="TOP")
    table.setStyle(TableStyle(commands))
    table = _rescale_if_overflow(
        wrapped_data,
        table,
        col_widths,
        commands,
        pagesize,
        used_margin,
        splittable=True,
    )
    return table, pagesize, used_margin
