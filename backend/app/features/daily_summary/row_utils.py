"""Shared row parsing helpers for Daily Summary builders and aggregators."""

from __future__ import annotations

from app.automation.formatting.text_safe import normalize_report_text
from app.features.daily_summary.fields import get_field

_DIVISION_ABBREVS: dict[str, str] = {
    "secunderabad": "SC",
    "hyderabad": "HYB",
    "nanded": "NED",
    "vijayawada": "BZA",
    "guntur": "GNT",
    "guntakal": "GTL",
}


def is_total_row(row: dict[str, str], *keys: str) -> bool:
    for key in keys:
        val = (row.get(key) or "").strip().lower()
        if "total" in val:
            return True
    joined = " ".join((row.get(k) or "") for k in row).lower()
    return "total" in joined and any(
        (row.get(k) or "").strip().lower().startswith("total")
        or (row.get(k) or "").strip().lower() == "total"
        for k in (
            "Train No.",
            "Train Name",
            "Owning Zone",
            "Organisation",
            "Division",
            "Cause",
            "cause",
        )
        if k in row
    )


def top_n(rows: list[dict[str, str]], n: int) -> list[dict[str, str]]:
    data = [
        r
        for r in rows
        if not is_total_row(r, "Train No.", "Train Name", "Owning Zone", "Division", "Cause")
    ]
    return data[:n]


def division_abbrev(value: str) -> str:
    text = value.strip()
    if not text:
        return text
    if len(text) <= 4 and text.isupper():
        return text
    lowered = text.casefold()
    for pattern, abbr in _DIVISION_ABBREVS.items():
        if pattern in lowered:
            return abbr
    return text


def safe_complaint_desc(row: dict[str, str]) -> str:
    val = get_field(row, "complaint_desc", slug="scr-station")
    if val:
        return normalize_report_text(val, field_kind="text", column_name="complaint_desc")
    return ""


def station_label(row: dict[str, str]) -> str | None:
    val = get_field(row, "station", slug="scr-station")
    if val:
        return normalize_report_text(val, field_kind="text", column_name="station")
    return None


def dept_div_tag(row: dict[str, str]) -> str | None:
    dept = get_field(row, "department", slug="scr-station")
    div = get_field(row, "division", slug="scr-station")
    if dept and div:
        return f"[{dept}-{division_abbrev(div)}]"
    if dept:
        return f"[{dept}]"
    if div:
        return f"[{division_abbrev(div)}]"
    return None
