"""Canonical artifact titles for PDF/Excel output, keyed by report slug."""

from __future__ import annotations

from app.automation.date_range import ReportDateRange

ARTIFACT_DISPLAY_TITLES: dict[str, str] = {
    "types": "Report 5: Cause Wise Analysis",
    "scr-train": "Report 6: SCR Train Report",
    "scr-station": "Report 7: SCR Station Report",
    "report9": "Report 9: All Zones Train/Station Cause Wise on Date",
    "report14": "Report 14: Watering Complaints",
    "report18": "VB RAILMADAD REPORT - SCR",
    "bottom-report": "Bottom Performed Trains Report",
}


def get_artifact_base_title(report_slug: str) -> str:
    """Return the standardized title without date suffix."""
    title = ARTIFACT_DISPLAY_TITLES.get(report_slug)
    if title is None:
        raise KeyError(f"No artifact title mapping for report slug {report_slug!r}")
    return title


def is_artifact_title_row(cells: list[str]) -> bool:
    """True when the first worksheet row is a report main title, not column headers."""
    first = (cells[0] if cells else "").strip()
    if not first:
        return False
    if "Rail Madad Report" in first:
        return True
    if first.startswith("Report Vande Bharat"):
        return True
    if first.startswith("VB RAILMADAD REPORT"):
        return True
    return first.startswith("Report ") and ":" in first


def build_artifact_main_title(report_slug: str, date_range: ReportDateRange) -> str:
    """Build the full PDF/Excel main heading including the selected date or range."""
    base = get_artifact_base_title(report_slug)
    if report_slug == "report9":
        if date_range.date_from == date_range.date_to:
            return f"{base} — {date_range.display_from()}"
        return f"{base} — {date_range.display_from()} to {date_range.display_to()}"
    return f"{base} {date_range.title_suffix()}"
