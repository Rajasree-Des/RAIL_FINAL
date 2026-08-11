"""Canonical field resolution for Daily Summary builders."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")

CANONICAL_ALIASES: dict[str, tuple[str, ...]] = {
    "complaint_type": (
        "Type",
        "complaintTypeName",
        "Complaint Type",
        "Comp Type Name",
        "comp_type_name",
        "Cause",
        "cause",
    ),
    "division": (
        "Div",
        "divCode",
        "ownDivCode",
        "Owning Div",
        "Owning Division",
        "Division",
        "Organisation",
        "organisation",
    ),
    "zone": (
        "Zone",
        "zoneCode",
        "ownZoneCode",
        "Owning Zone",
        "owning zone",
    ),
    "station": (
        "Train/Station",
        "trainStation",
        "trainNameForReport/Station Name",
        "trainNameForReport",
        "Station",
        "Station Name",
    ),
    "train_number": (
        "Train No.",
        "Train No",
        "Train Number",
        "trainNo",
        "train_number",
    ),
    "train_name": (
        "Train Name",
        "trainName",
        "train_name",
        "trainNameForReport",
    ),
    "department": (
        "Dept",
        "deptCode",
        "Department",
        "department",
    ),
    "complaint_desc": (
        "complaintDesc",
        "Complaint Description",
        "complaint_desc",
        "Remarks",
        "feedbackRemark",
    ),
    "received": (
        "Received",
        "received",
        "Feedback Received",
    ),
    "closed": (
        "Closed",
        "closed",
    ),
    "opening_balance": (
        "Opening Balance",
        "opening_balance",
        "OpeningBalance",
    ),
    "closing_balance": (
        "Closing Balance",
        "closing_balance",
        "ClosingBalance",
    ),
    "rank": (
        "Rank",
        "rank",
        "S.No.",
        "S.No",
    ),
    "organisation": (
        "Organisation",
        "Organisation Name",
        "Zone Name",
        "organisation",
    ),
    "share_percent": (
        "% Share",
        "%Share",
        "Share",
        "share_percent",
    ),
}


def normalize_header_key(key: str) -> str:
    """Normalize a CSV header for alias lookup."""
    return _NORMALIZE_RE.sub("", (key or "").strip().casefold())


def _row_index(row: dict[str, str]) -> dict[str, str]:
    return {normalize_header_key(k): k for k in row}


def get_field(
    row: dict[str, str],
    canonical: str,
    *,
    slug: str | None = None,
    run_id: str | None = None,
) -> str | None:
    """Return a trimmed field value or None when absent. Never returns 'Unknown'."""
    aliases = CANONICAL_ALIASES.get(canonical)
    if not aliases:
        return None
    index = _row_index(row)
    for alias in aliases:
        original = index.get(normalize_header_key(alias))
        if original is None:
            continue
        value = (row.get(original) or "").strip()
        if value:
            return value
    logger.warning(
        "daily_summary_field_missing canonical=%s slug=%s run_id=%s keys=%s",
        canonical,
        slug,
        run_id,
        list(row.keys())[:12],
    )
    return None
