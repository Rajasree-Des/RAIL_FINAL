"""Constants for Daily Summary source mapping and display ordering."""

from __future__ import annotations

SUMMARY_SOURCES: dict[str, str] = {
    "bottom_20": "train-no",
    "cause_wise_bottom_10": "types",
    "territorial": "bottom-report",
    "unsatisfactory_train": "scr-train",
    "station_feedback": "scr-station",
}

CORE_SOURCE_SLUGS: tuple[str, ...] = tuple(SUMMARY_SOURCES.values())

TERRITORIAL_CAUSE_ORDER: tuple[str, ...] = (
    "punctuality",
    "security",
    "electrical_equipment",
    "water_availability",
)

TERRITORIAL_CAUSE_LABELS: dict[str, str] = {
    "punctuality": "Punctuality",
    "security": "Security",
    "electrical_equipment": "Electrical Equipment",
    "water_availability": "Water Availability",
}

DIVISION_DISPLAY_ORDER: tuple[str, ...] = ("SC", "HYB", "NED")

UNSATISFACTORY_CAUSE_ORDER: tuple[str, ...] = (
    "Coach - Cleanliness",
    "Coach - Maintenance",
    "Miscellaneous",
    "Punctuality",
    "Security",
    "Water Availability",
)

CAUSE_WISE_HEADER = (
    "In cause wise train wise in bottom 10 trains "
    "[w.r.to Report 10: Zone wise train wise]"
)

REPORT6_REFERENCE = (
    "All concerned for information & N.A. w.r.to unsatisfactory feedback "
    "in REPORT No.6 on case to case basis."
)

GREETING = "Good morning Sir/Ma'am ,"
