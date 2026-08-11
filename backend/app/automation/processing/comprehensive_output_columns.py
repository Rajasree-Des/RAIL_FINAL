"""Output column definitions for Report 10-13 (Comprehensive Reports).

All four sections share the same available columns from the Division Wise view.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from app.automation.comprehensive1013_filters import COMPREHENSIVE_1013_SECTION_IDS

COMPREHENSIVE_SNAPSHOT_VERSION = 1

COMPREHENSIVE_COLUMN_IDS: list[str] = [
    "sno",
    "division",
    "opening_balance",
    "received",
    "share_percent",
    "closed",
    "closing_balance",
    "disposal_percent",
    "avg_disposal_time",
    "avg_rating",
    "avg_pendency_time",
]

COMPREHENSIVE_COLUMN_LABELS: dict[str, str] = {
    "sno": "S.No.",
    "division": "Division",
    "opening_balance": "Opening Balance",
    "received": "Received",
    "share_percent": "% Share",
    "closed": "Closed",
    "closing_balance": "Closing Balance",
    "disposal_percent": "% Disposal",
    "avg_disposal_time": "Avg. Disposal Time",
    "avg_rating": "Avg. Rating",
    "avg_pendency_time": "Avg. Pendency Time",
}

COMPREHENSIVE_HEADER_ALIASES: dict[str, str] = {
    "S.No.": "sno",
    "S.No": "sno",
    "SNo": "sno",
    "Sno": "sno",
    "Sl.No.": "sno",
    "Sl No": "sno",
    "Division": "division",
    "Organisation": "division",
    "Opening Balance": "opening_balance",
    "Opening": "opening_balance",
    "Received": "received",
    "% Share": "share_percent",
    "Share %": "share_percent",
    "Closed": "closed",
    "Closing Balance": "closing_balance",
    "Closing": "closing_balance",
    "% Disposal": "disposal_percent",
    "Disposal %": "disposal_percent",
    "Avg. Disposal Time": "avg_disposal_time",
    "Avg Disposal Time": "avg_disposal_time",
    "Avg. Rating": "avg_rating",
    "Avg Rating": "avg_rating",
    "Avg. Pendency Time": "avg_pendency_time",
    "Avg Pendency Time": "avg_pendency_time",
}

_SECTION_VALIDATION_NAMES: dict[str, str] = {
    "report10_cw": "Report 10 — C&W",
    "report11_security": "Report 11 — Security",
    "report12_punctuality": "Report 12 — Punctuality",
    "report13_electrical": "Report 13 — Electrical Equipment",
}

ADDITIVE_COLUMNS: set[str] = {
    "opening_balance",
    "received",
    "closed",
    "closing_balance",
}

NON_ADDITIVE_COLUMNS: set[str] = {
    "disposal_percent",
    "avg_disposal_time",
    "avg_rating",
    "avg_pendency_time",
}

_ALLOWED_IDS = frozenset(COMPREHENSIVE_COLUMN_IDS)


def normalize_comprehensive_column_id(value: object) -> str | None:
    """Map a canonical ID or legacy label/alias to a canonical column ID."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text in _ALLOWED_IDS:
        return text
    if text in COMPREHENSIVE_HEADER_ALIASES:
        return COMPREHENSIVE_HEADER_ALIASES[text]
    lowered = text.casefold()
    for alias, col_id in COMPREHENSIVE_HEADER_ALIASES.items():
        if alias.casefold() == lowered:
            return col_id
    for col_id in COMPREHENSIVE_COLUMN_IDS:
        if col_id.casefold() == lowered:
            return col_id
    return None


def sanitize_comprehensive_section_columns(selected: Iterable[str]) -> list[str]:
    """Filter/normalize comprehensive section columns; preserve order; dedupe."""
    sanitized: list[str] = []
    seen: set[str] = set()
    for raw in selected:
        key = normalize_comprehensive_column_id(raw)
        if key and key not in seen:
            sanitized.append(key)
            seen.add(key)
    return sanitized


def sanitize_comprehensive_sections(
    sections: dict[str, Any],
) -> dict[str, dict[str, list[str]]]:
    """Sanitize per-section column selections for Report 10-13."""
    sanitized: dict[str, dict[str, list[str]]] = {}
    for section_id in COMPREHENSIVE_1013_SECTION_IDS:
        section_payload = sections.get(section_id)
        if not isinstance(section_payload, dict):
            continue
        raw_ids = section_payload.get("selected_column_ids") or []
        if not isinstance(raw_ids, list):
            raw_ids = []
        selected = sanitize_comprehensive_section_columns(raw_ids)
        if selected:
            sanitized[section_id] = {"selected_column_ids": selected}
    return sanitized


def validate_comprehensive_sections(sections: dict[str, Any]) -> None:
    """Require all four sections with at least one selected column each."""
    if not sections:
        raise ValueError("Report 10-13 requires column selections for all four sections.")

    for section_id in COMPREHENSIVE_1013_SECTION_IDS:
        section_name = _SECTION_VALIDATION_NAMES.get(section_id, section_id)
        section_payload = sections.get(section_id)
        if not isinstance(section_payload, dict):
            raise ValueError(f"Select at least one column for {section_name}.")
        raw_ids = section_payload.get("selected_column_ids") or []
        if not isinstance(raw_ids, list) or len(raw_ids) < 1:
            raise ValueError(f"Select at least one column for {section_name}.")
        selected = sanitize_comprehensive_section_columns(raw_ids)
        if len(selected) < 1:
            raise ValueError(f"Select at least one column for {section_name}.")
        invalid = [
            key
            for key in raw_ids
            if normalize_comprehensive_column_id(key) is None
        ]
        if invalid:
            raise ValueError(
                f"{section_name} selected columns must belong to the approved allowlist. "
                f"invalid={sorted({str(item) for item in invalid})}"
            )
        if len(selected) != len(set(selected)):
            raise ValueError(f"{section_name} selected columns contain duplicates.")


def comprehensive_union_column_keys(
    sections: dict[str, dict[str, list[str]]],
) -> list[str]:
    """Union of all section column IDs in stable catalog order."""
    seen: set[str] = set()
    for section_id in COMPREHENSIVE_1013_SECTION_IDS:
        section_payload = sections.get(section_id) or {}
        for key in section_payload.get("selected_column_ids") or []:
            if key in _ALLOWED_IDS:
                seen.add(key)
    return [key for key in COMPREHENSIVE_COLUMN_IDS if key in seen]


def compute_comprehensive_snapshot_hash(
    sections: dict[str, dict[str, list[str]]],
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    version: int = COMPREHENSIVE_SNAPSHOT_VERSION,
) -> str:
    """Stable hash for artifact identity / stale detection."""
    payload = {
        "version": version,
        "date_from": date_from or "",
        "date_to": date_to or "",
        "sections": {
            section_id: list((sections.get(section_id) or {}).get("selected_column_ids") or [])
            for section_id in COMPREHENSIVE_1013_SECTION_IDS
        },
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def build_comprehensive_column_snapshot(
    sections: dict[str, Any],
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    run_id: str | None = None,
    configuration_source: str = "manual_snapshot",
) -> dict[str, Any]:
    """Build immutable comprehensive column snapshot shared by API, processor, artifacts."""
    validate_comprehensive_sections(sections)
    sanitized = sanitize_comprehensive_sections(sections)
    validate_comprehensive_sections(sanitized)
    union_keys = comprehensive_union_column_keys(sanitized)
    if len(union_keys) < 1:
        raise ValueError("Report 10-13 requires at least one selected column across all sections.")

    snapshot: dict[str, Any] = {
        "version": COMPREHENSIVE_SNAPSHOT_VERSION,
        "sections": sanitized,
        "selected_column_ids": list(union_keys),
        "column_order": list(union_keys),
        "configuration_source": configuration_source,
    }
    if date_from:
        snapshot["date_from"] = date_from
    if date_to:
        snapshot["date_to"] = date_to
    if run_id:
        snapshot["run_id"] = run_id
    snapshot["snapshot_hash"] = compute_comprehensive_snapshot_hash(
        sanitized,
        date_from=date_from,
        date_to=date_to,
    )
    return snapshot


def build_comprehensive_artifact_metadata(
    snapshot: dict[str, Any],
    *,
    run_id: str | None = None,
    report_slug: str = "comprehensive-10-13",
) -> dict[str, Any]:
    """Metadata written to Excel/PDF artifacts for Report 10-13."""
    sections_raw = snapshot.get("sections") or {}
    sections = {
        section_id: {
            "selected_column_ids": list(
                (sections_raw.get(section_id) or {}).get("selected_column_ids") or []
            )
        }
        for section_id in COMPREHENSIVE_1013_SECTION_IDS
        if section_id in sections_raw
    }
    union = snapshot.get("column_order") or snapshot.get("selected_column_ids") or []
    metadata: dict[str, Any] = {
        "version": snapshot.get("version", COMPREHENSIVE_SNAPSHOT_VERSION),
        "sections": sections,
        "selected_column_ids": list(union),
        "column_order": list(union),
        "snapshot_hash": snapshot.get("snapshot_hash")
        or compute_comprehensive_snapshot_hash(
            sections,
            date_from=snapshot.get("date_from"),
            date_to=snapshot.get("date_to"),
        ),
        "report_slug": report_slug,
    }
    if snapshot.get("date_from"):
        metadata["date_from"] = snapshot["date_from"]
    if snapshot.get("date_to"):
        metadata["date_to"] = snapshot["date_to"]
    if snapshot.get("configuration_source"):
        metadata["configuration_source"] = snapshot["configuration_source"]
    if run_id:
        metadata["run_id"] = run_id
    return metadata


def section_column_ids_from_snapshot(snapshot: dict[str, Any], section_id: str) -> list[str]:
    """Return normalized column IDs for one section from a snapshot dict."""
    sections = snapshot.get("sections") or {}
    payload = sections.get(section_id) or {}
    raw = payload.get("selected_column_ids") or []
    return sanitize_comprehensive_section_columns(raw)


def compare_comprehensive_section_columns(
    expected: list[str],
    actual: list[str],
) -> tuple[bool, list[str], list[str], bool]:
    """Return (match, missing, unexpected, reordered)."""
    exp = list(expected)
    act = list(actual)
    if exp == act:
        return True, [], [], False
    missing = [key for key in exp if key not in act]
    unexpected = [key for key in act if key not in exp]
    reordered = not missing and not unexpected and set(exp) == set(act)
    return False, missing, unexpected, reordered


def validate_comprehensive_artifact_metadata(
    excel_meta: dict[str, Any],
    pdf_meta: dict[str, Any],
    manual_config: dict[str, Any],
    *,
    run_id: str | None = None,
) -> tuple[bool, str | None]:
    """Validate comprehensive Excel/PDF metadata against run manual_config."""
    expected_sections = manual_config.get("sections") or {}
    expected_hash = manual_config.get("snapshot_hash")
    if not expected_hash and expected_sections:
        expected_hash = compute_comprehensive_snapshot_hash(
            expected_sections,
            date_from=manual_config.get("date_from"),
            date_to=manual_config.get("date_to"),
        )

    for label, meta in (("Excel", excel_meta), ("PDF", pdf_meta)):
        if run_id and meta.get("run_id") and str(meta["run_id"]) != str(run_id):
            return False, f"Report 10–13: {label} artifact belongs to a different run."
        if expected_hash and meta.get("snapshot_hash") and meta["snapshot_hash"] != expected_hash:
            return False, (
                "Report 10–13: artifact column snapshot does not match the current run configuration."
            )

    excel_sections = excel_meta.get("sections") or {}
    pdf_sections = pdf_meta.get("sections") or {}

    for section_id in COMPREHENSIVE_1013_SECTION_IDS:
        section_name = _SECTION_VALIDATION_NAMES.get(section_id, section_id)
        expected = section_column_ids_from_snapshot(manual_config, section_id)
        excel_cols = section_column_ids_from_snapshot({"sections": excel_sections}, section_id)
        pdf_cols = section_column_ids_from_snapshot({"sections": pdf_sections}, section_id)

        if excel_cols != pdf_cols:
            return False, f"{section_name}: Excel and PDF column snapshots differ."

        ok, missing, unexpected, reordered = compare_comprehensive_section_columns(
            expected, excel_cols
        )
        if not ok:
            if missing:
                return False, f'{section_name}: renderer omitted column(s) {", ".join(missing)}.'
            if unexpected:
                return False, (
                    f'{section_name}: renderer included unexpected column(s) '
                    f'{", ".join(unexpected)}.'
                )
            if reordered:
                return False, f"{section_name}: renderer column order does not match snapshot."

    return True, None


def normalize_header_to_column_id(header: str) -> str | None:
    """Map a raw header string to a canonical column ID."""
    return normalize_comprehensive_column_id(header)


def default_column_ids() -> list[str]:
    """Return the default column IDs for comprehensive reports."""
    return list(COMPREHENSIVE_COLUMN_IDS)


def column_labels(column_ids: list[str]) -> list[str]:
    """Return display labels for given column IDs."""
    return [COMPREHENSIVE_COLUMN_LABELS.get(cid, cid) for cid in column_ids]
