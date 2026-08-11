"""Canonical field mapping for Report 5/6 SCR complaint modal extraction."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Normalized portal header -> canonical key (verified against live modal DOM)
PORTAL_HEADER_ALIASES: dict[str, str] = {
    "s no": "portalSlNo",
    "s. no.": "portalSlNo",
    "ref no": "complaintRefNo",
    "ref. no.": "complaintRefNo",
    "reference no": "complaintRefNo",
    "reference number": "complaintRefNo",
    "refer number": "complaintRefNo",
    "complaint ref no": "complaintRefNo",
    "complaint ref number": "complaintRefNo",
    "registration date": "createdOn",
    "complaint date": "createdOn",
    "created on": "createdOn",
    "date": "createdOn",
    "closing date": "modifiedOn",
    "modified on": "modifiedOn",
    "final status": "finalStatus",
    "finalstatus": "finalStatus",
    "status": "status",
    "avgcdiff": "avgCliff",
    "avg cliff": "avgCliff",
    "avg. diff": "diff",
    "avg diff": "diff",
    "avgcliff": "avgCliff",
    "disposal time": "diff",
    "diff": "diff",
    "mode": "complaintMode",
    "complaint mode": "complaintMode",
    "train/station": "trainStation",
    "train": "trainStation",
    "station": "trainStation",
    "primary depot": "primaryDepot",
    "channel": "channelType",
    "channel type": "channelType",
    "type": "complaintTypeName",
    "complaint type": "complaintTypeName",
    "comp type name": "complaintTypeName",
    "sub type": "subTypeName",
    "subtype": "subTypeName",
    "sub type name": "subTypeName",
    "zone": "zoneCode",
    "zone code": "zoneCode",
    "owning zone": "ownZoneCode",
    "div": "divCode",
    "div code": "divCode",
    "owning div": "ownDivCode",
    "department": "deptCode",
    "dept": "deptCode",
    "dept code": "deptCode",
    "deptcode": "deptCode",
    "rating": "rating",
    "commodity": "commodity",
    "forwarded": "forwarded",
    "pnrutsno": "pnrUtsNo",
    "pnr/uts no": "pnrUtsNo",
    "pnr/uts no.": "pnrUtsNo",
    "coach type": "coachType",
    "coachtype": "coachType",
    "physical coach no": "physicalCoachNo",
    "physicalcoachno": "physicalCoachNo",
    "feedback remark": "feedbackRemark",
    "feedback remarks": "feedbackRemark",
    "feedbackremark": "feedbackRemark",
    "next station": "nextStation",
    "nextstation": "nextStation",
    "contact id": "contactId",
    "contactid": "contactId",
    "train name for report": "trainNameForReport",
    "trainnameforreport/station name": "trainNameForReport",
    "trainnameforreport": "trainNameForReport",
    "complaint description": "complaintDesc",
    "complaint desc": "complaintDesc",
    "complaintdesc": "complaintDesc",
    "remarks": "remarks",
    "user id": "userId",
    "user id.": "userId",
    "userid": "userId",
    "user mobile": "userMobile",
    "usermobile": "userMobile",
    "coach owning railway": "coachOwningRailway",
}

# All verified canonical fields persisted in raw CSV (complete ingestion)
SCR_FULL_CANONICAL_HEADERS: list[str] = [
    "complaintRefNo",
    "createdOn",
    "modifiedOn",
    "finalStatus",
    "status",
    "avgCliff",
    "diff",
    "complaintMode",
    "trainStation",
    "primaryDepot",
    "channelType",
    "complaintTypeName",
    "subTypeName",
    "zoneCode",
    "divCode",
    "ownZoneCode",
    "ownDivCode",
    "deptCode",
    "rating",
    "commodity",
    "forwarded",
    "pnrUtsNo",
    "coachType",
    "physicalCoachNo",
    "feedbackRemark",
    "nextStation",
    "contactId",
    "trainNameForReport",
    "complaintDesc",
    "remarks",
    "userId",
    "userMobile",
    "coachOwningRailway",
    "mode",
]

REPORT5_CANONICAL_CSV_HEADERS: list[str] = list(SCR_FULL_CANONICAL_HEADERS)
REPORT6_CANONICAL_CSV_HEADERS: list[str] = list(SCR_FULL_CANONICAL_HEADERS)

REPORT5_REQUIRED_CANONICAL: frozenset[str] = frozenset(
    {
        "complaintRefNo",
        "createdOn",
        "trainStation",
        "complaintTypeName",
        "subTypeName",
        "deptCode",
        "status",
        "zoneCode",
        "divCode",
        "feedbackRemark",
        "trainNameForReport",
        "complaintDesc",
        "remarks",
        "userId",
    }
)

REPORT6_REQUIRED_CANONICAL: frozenset[str] = frozenset(
    {
        "complaintRefNo",
        "trainStation",
        "complaintTypeName",
        "subTypeName",
        "deptCode",
        "status",
        "zoneCode",
        "divCode",
        "feedbackRemark",
        "complaintDesc",
        "remarks",
        "userId",
    }
)

_ALL_CANONICAL_KEYS = frozenset(SCR_FULL_CANONICAL_HEADERS) | {"portalSlNo", "department"}


def normalize_header(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "").strip().lower())
    return cleaned


def portal_header_to_canonical(header: str) -> str | None:
    normalized = normalize_header(header)
    if not normalized:
        return None
    if normalized in PORTAL_HEADER_ALIASES:
        return PORTAL_HEADER_ALIASES[normalized]
    compact = normalized.replace(".", "")
    for alias, canonical in PORTAL_HEADER_ALIASES.items():
        if alias.replace(".", "") == compact:
            return canonical
    return None


def canonicalize_scr_row(row: dict[str, str]) -> dict[str, str]:
    """Map portal-key row to canonical keys (header alias based, never positional)."""
    canonical: dict[str, str] = {}
    unrecognized: list[str] = []
    for portal_key, value in row.items():
        key = portal_header_to_canonical(portal_key)
        if key is None and portal_key in _ALL_CANONICAL_KEYS:
            key = portal_key
        if key is None:
            if str(portal_key or "").strip():
                unrecognized.append(str(portal_key))
            continue
        text = str(value or "").strip()
        if text.lower() == "null":
            text = ""
        if key == "complaintMode":
            canonical["complaintMode"] = text
            if text and not canonical.get("mode"):
                canonical["mode"] = text
            continue
        if key == "deptCode" and "department" not in canonical:
            canonical["department"] = text
        if key not in canonical or (text and not canonical[key]):
            canonical[key] = text
    if unrecognized:
        logger.debug("scr_unrecognized_portal_headers: %s", sorted(set(unrecognized)))
    if canonical.get("complaintMode") and not canonical.get("mode"):
        canonical["mode"] = canonical["complaintMode"]
    elif canonical.get("mode") and not canonical.get("complaintMode"):
        canonical["complaintMode"] = canonical["mode"]
    return canonical


def canonicalize_scr_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [canonicalize_scr_row(row) for row in rows]


def build_csv_fieldnames(rows: list[dict[str, str]]) -> list[str]:
    """Return ordered CSV headers: full canonical list plus any extra mapped keys."""
    present: set[str] = set(SCR_FULL_CANONICAL_HEADERS)
    for row in rows:
        present.update(canonicalize_scr_row(row).keys())
    ordered = [h for h in SCR_FULL_CANONICAL_HEADERS if h in present]
    extras = sorted(present - set(ordered) - {"portalSlNo", "department"})
    return ordered + extras


@dataclass
class ScrVerificationResult:
    ok: bool
    source_headers: list[str] = field(default_factory=list)
    canonical_fields_mapped: list[str] = field(default_factory=list)
    missing_required_fields: list[str] = field(default_factory=list)
    empty_required_fields: list[str] = field(default_factory=list)
    non_empty_counts: dict[str, int] = field(default_factory=dict)
    sample_values: dict[str, str] = field(default_factory=dict)
    row_count: int = 0


def verify_scr_csv(
    rows: list[dict[str, str]],
    *,
    report_num: int,
    report_slug: str = "",
    source_csv_path: str = "",
) -> ScrVerificationResult:
    required = REPORT5_REQUIRED_CANONICAL if report_num == 5 else REPORT6_REQUIRED_CANONICAL
    if not rows:
        return ScrVerificationResult(
            ok=False,
            missing_required_fields=sorted(required),
            row_count=0,
        )

    canonical_rows = canonicalize_scr_rows(rows)
    source_headers = sorted({k for row in rows for k in row})

    header_mapped: set[str] = set()
    for portal_key in source_headers:
        canonical_key = portal_header_to_canonical(portal_key)
        if canonical_key and canonical_key != "portalSlNo":
            header_mapped.add(canonical_key)
        elif portal_key in required:
            header_mapped.add(portal_key)

    non_empty_counts: dict[str, int] = {}
    populated: set[str] = set()
    for row in canonical_rows:
        for key, value in row.items():
            if str(value).strip():
                populated.add(key)
                non_empty_counts[key] = non_empty_counts.get(key, 0) + 1

    missing = sorted(required - header_mapped)
    empty_required: list[str] = sorted(
        field_name
        for field_name in required
        if field_name in header_mapped and field_name not in populated
    )
    samples: dict[str, str] = {}
    for field_name in required:
        sample = next(
            (str(r.get(field_name, "") or "").strip() for r in canonical_rows if r.get(field_name)),
            "",
        )
        if sample:
            samples[field_name] = sample[:80]

    ok = not missing
    logger.info(
        "scr_source_validation report_slug=%s source_csv_path=%s source_headers=%s "
        "canonical_fields_mapped=%s source_row_count=%d non_empty_counts=%s "
        "missing_required=%s empty_required=%s",
        report_slug,
        source_csv_path,
        source_headers,
        sorted(header_mapped | populated),
        len(rows),
        non_empty_counts,
        missing,
        empty_required,
    )
    return ScrVerificationResult(
        ok=ok,
        source_headers=source_headers,
        canonical_fields_mapped=sorted(header_mapped | populated),
        missing_required_fields=missing,
        empty_required_fields=empty_required,
        non_empty_counts=non_empty_counts,
        sample_values=samples,
        row_count=len(rows),
    )
