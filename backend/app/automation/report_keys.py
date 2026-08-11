"""Canonical report keys for automation, ingestion, and storage.

Single source of truth. Aliases exist only for backward compatibility and
must resolve to a canonical key — never create duplicate datasets.
"""

from __future__ import annotations

CANONICAL_KEYS: frozenset[str] = frozenset(
    {
        "report1",
        "division",
        "division_feedback",
        "train-no",
        "types",
        "scr-train",
        "scr-station",
        "report1_feedback",
        "merging",
        "report9",
        "comprehensive-10-13",
        "report10_cw",
        "report11_security",
        "report12_punctuality",
        "report13_electrical",
        "report14",
        "report18",
        "bottom-report",
    }
)

# Legacy automation slugs → canonical dataset / catalog keys
ALIASES: dict[str, str] = {
    "report2": "division",
    "report3": "train-no",
    "report4": "types",
    "report5": "scr-train",
    "report5_train": "scr-train",
    "report6_station": "scr-station",
}

# Template workbooks used when ensuring a dataset row exists
DATASET_TEMPLATES: dict[str, str] = {
    "report1": "zone_wise_original.xlsx",
    "merging": "zone_wise_original.xlsx",
    "division": "division_original.xlsx",
    "train-no": "train_original.xlsx",
    "types": "cause_wise_original.xlsx",
    "scr-train": "scr_train_original.xlsx",
    "scr-station": "scr_station_original.xlsx",
}

PDF_DOWNLOAD_URL_TEMPLATE = "/api/v1/automation/reports/{report_key}/pdf"


def canonicalize_report_key(key: str) -> str:
    """Resolve aliases to the canonical report/dataset key."""
    if not key:
        raise ValueError("Report key must be non-empty")
    return ALIASES.get(key, key)


def is_supported_report_key(key: str) -> bool:
    """Return True if the key (or its alias) is a known report id."""
    canonical = canonicalize_report_key(key)
    return canonical in CANONICAL_KEYS or canonical in {
        "report1",
        "division",
        "division_feedback",
        "train-no",
        "types",
        "scr-train",
        "scr-station",
        "report1_feedback",
        "merging",
        "report9",
        "comprehensive-10-13",
        "report10_cw",
        "report11_security",
        "report12_punctuality",
        "report13_electrical",
        "report14",
        "report18",
    }


def pdf_download_url(report_key: str) -> str:
    """Build the secure PDF download URL for a canonical report key."""
    return PDF_DOWNLOAD_URL_TEMPLATE.format(report_key=canonicalize_report_key(report_key))
