"""Canonical slug mapping for Report Configuration pages."""

from __future__ import annotations

from app.automation.report_keys import canonicalize_report_key

MANUAL_REPORT_SLUGS: frozenset[str] = frozenset(
    {
        "report1",
        "division",
        "train-no",
        "types",
        "scr-train",
        "scr-station",
        "report9",
        "comprehensive-10-13",
        "report14",
        "report18",
        "bottom-report",
    }
)

# UI page ids (sidebar / report-config) → automation handler slug
PAGE_ID_TO_SLUG: dict[str, str] = {
    "zone": "report1",
    "merging": "report1",
    "report1": "report1",
    "division": "division",
    "report2": "division",
    "train-no": "train-no",
    "report3": "train-no",
    "types": "types",
    "report4": "types",
    "scr-train": "scr-train",
    "report5": "scr-train",
    "scr-station": "scr-station",
    "report6_station": "scr-station",
    "report9": "report9",
    "comprehensive-10-13": "comprehensive-10-13",
    "report14": "report14",
    "report18": "report18",
    "bottom-report": "bottom-report",
}


def resolve_manual_slug(slug_or_page_id: str) -> str:
    """Resolve URL slug or page id to canonical automation slug."""
    key = slug_or_page_id.strip()
    mapped = PAGE_ID_TO_SLUG.get(key, key)
    return canonicalize_report_key(mapped)


def is_manual_report_slug(slug_or_page_id: str) -> bool:
    return resolve_manual_slug(slug_or_page_id) in MANUAL_REPORT_SLUGS
