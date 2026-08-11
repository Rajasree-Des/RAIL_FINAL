"""Build administrative-events PDF for system log export."""

from __future__ import annotations

import io
from datetime import UTC, datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.features.system.log_export import AdminEvent

TITLE = "RailMadad Report Center — Administrative Events"

LEVEL_COLORS = {
    "Error": colors.HexColor("#DC2626"),
    "Warning": colors.HexColor("#D97706"),
    "Information": colors.HexColor("#2563EB"),
    "Success": colors.HexColor("#16A34A"),
}

NA = "N/A"


def _format_datetime(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    local = dt.astimezone(UTC)
    return local.strftime("%d/%m/%Y %I:%M:%S %p")


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _pdf_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "AdminTitle",
            parent=base["Heading1"],
            fontSize=14,
            alignment=TA_CENTER,
            spaceAfter=6,
        ),
        "meta": ParagraphStyle(
            "AdminMeta",
            parent=base["Normal"],
            fontSize=9,
            leading=12,
        ),
        "cell": ParagraphStyle(
            "AdminCell",
            parent=base["Normal"],
            fontSize=8,
            leading=10,
            alignment=TA_LEFT,
        ),
        "header": ParagraphStyle(
            "AdminHeader",
            parent=base["Normal"],
            fontSize=8,
            leading=10,
            fontName="Helvetica-Bold",
            alignment=TA_CENTER,
        ),
        "section": ParagraphStyle(
            "AdminSection",
            parent=base["Heading2"],
            fontSize=11,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "detail": ParagraphStyle(
            "AdminDetail",
            parent=base["Normal"],
            fontSize=8,
            leading=11,
        ),
    }


def _level_paragraph(level: str, styles: dict[str, ParagraphStyle]) -> Paragraph:
    color = LEVEL_COLORS.get(level, colors.black)
    html = (
        f'<font color="{color.hexval()}"><b>{_escape(level)}</b></font>'
    )
    return Paragraph(html, styles["cell"])


def _build_summary_table(
    events: list[AdminEvent],
    styles: dict[str, ParagraphStyle],
    page_width: float,
) -> Table:
    col_widths = [
        page_width * 0.09,
        page_width * 0.16,
        page_width * 0.11,
        page_width * 0.08,
        page_width * 0.14,
        page_width * 0.42,
    ]
    header = [
        Paragraph("Level", styles["header"]),
        Paragraph("Date and Time", styles["header"]),
        Paragraph("Source", styles["header"]),
        Paragraph("Event ID", styles["header"]),
        Paragraph("Task Category", styles["header"]),
        Paragraph("Message", styles["header"]),
    ]
    rows: list[list[Any]] = [header]
    for event in events:
        rows.append(
            [
                _level_paragraph(event.level, styles),
                Paragraph(_escape(_format_datetime(event.created_at)), styles["cell"]),
                Paragraph(_escape(event.source or NA), styles["cell"]),
                Paragraph(_escape(event.event_id or NA), styles["cell"]),
                Paragraph(_escape(event.task_category or NA), styles["cell"]),
                Paragraph(_escape(event.message or NA), styles["cell"]),
            ]
        )

    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _build_details_section(
    events: list[AdminEvent],
    styles: dict[str, ParagraphStyle],
) -> list[Any]:
    flowables: list[Any] = [Paragraph("Event Details", styles["section"])]
    has_details = False
    for event in events:
        if not event.details:
            continue
        has_details = True
        lines = [
            f"<b>Event { _escape(event.event_id) } — { _escape(event.source) }</b>",
        ]
        for key, value in event.details.items():
            lines.append(f"{_escape(key)}: {_escape(value or NA)}")
        flowables.append(Paragraph("<br/>".join(lines), styles["detail"]))
        flowables.append(Spacer(1, 4 * mm))

    if not has_details:
        flowables.append(Paragraph("No additional detail metadata available.", styles["detail"]))
    return flowables


def build_admin_events_pdf(
    events: list[AdminEvent],
    *,
    environment: str,
    app_version: str,
    exported_at: datetime | None = None,
) -> bytes:
    """Render administrative events PDF bytes (A4 landscape)."""
    exported = exported_at or datetime.now(UTC)
    if exported.tzinfo is None:
        exported = exported.replace(tzinfo=UTC)

    buffer = io.BytesIO()
    page_size = landscape(A4)
    margin = 12 * mm
    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=14 * mm,
        title=TITLE,
    )
    page_width = page_size[0] - 2 * margin
    styles = _pdf_styles()

    meta_lines = [
        f"<b>Number of events:</b> {len(events)}",
        f"<b>Exported:</b> {_escape(_format_datetime(exported))}",
        f"<b>Environment:</b> {_escape(environment)}",
        f"<b>App version:</b> {_escape(app_version)}",
    ]

    story: list[Any] = [
        Paragraph(TITLE, styles["title"]),
        Spacer(1, 4 * mm),
        Paragraph("<br/>".join(meta_lines), styles["meta"]),
        Spacer(1, 6 * mm),
    ]

    if events:
        story.append(_build_summary_table(events, styles, page_width))
        story.append(PageBreak())
        story.extend(_build_details_section(events, styles))
    else:
        story.append(Paragraph("No stored events found.", styles["meta"]))

    def _footer(canvas: Any, doc_ref: SimpleDocTemplate) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawRightString(
            page_size[0] - margin,
            8 * mm,
            f"Page {canvas.getPageNumber()}",
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()
