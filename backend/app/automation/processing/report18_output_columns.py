"""Output column catalog for Report Vande Bharat (Report 18) detailed complaints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.automation.report18_detail_extract import (
    REPORT18_FINAL_HEADERS,
    REPORT18_LEGACY_HEADER_ALIASES,
)


@dataclass(frozen=True)
class Report18Column:
    id: str
    label: str
    required: bool = False
    default_visible: bool = True
    group: str = "detail"
    group_title: str = "Vande Bharat Complaint Columns"


# ids match final CSV headers (stable for UI selection / projection).
REPORT18_OUTPUT_COLUMNS: tuple[Report18Column, ...] = tuple(
    Report18Column(
        id=header,
        label=header,
        required=header
        in {
            "Sl No",
            "complaintRefNo",
            "createdOn",
            "trainStation",
            "compTypeName",
            "status",
            "trainNameForReport",
        },
    )
    for header in REPORT18_FINAL_HEADERS
)

REPORT18_COLUMN_BY_ID: dict[str, Report18Column] = {
    c.id: c for c in REPORT18_OUTPUT_COLUMNS
}
REPORT18_LABEL_BY_ID: dict[str, str] = {c.id: c.label for c in REPORT18_OUTPUT_COLUMNS}


def report18_default_ids() -> list[str]:
    return [c.id for c in REPORT18_OUTPUT_COLUMNS if c.default_visible]


def report18_allowed_ids() -> frozenset[str]:
    return frozenset(REPORT18_COLUMN_BY_ID.keys())


def report18_catalog_entries() -> list[dict[str, object]]:
    return [
        {
            "id": c.id,
            "label": c.label,
            "required": c.required,
            "default_visible": c.default_visible,
            "group": c.group,
            "group_title": c.group_title,
        }
        for c in REPORT18_OUTPUT_COLUMNS
    ]


def report18_labels(ids: Iterable[str]) -> list[str]:
    return [REPORT18_LABEL_BY_ID[i] for i in ids if i in REPORT18_LABEL_BY_ID]


def validate_selected_report18_fields(selected: Iterable[str]) -> list[str]:
    allowed = report18_allowed_ids()
    ordered: list[str] = []
    seen: set[str] = set()
    for item in selected:
        key = REPORT18_LEGACY_HEADER_ALIASES.get(str(item).strip(), str(item).strip())
        if not key or key in seen or key not in allowed:
            continue
        seen.add(key)
        ordered.append(key)
    for col in REPORT18_OUTPUT_COLUMNS:
        if col.required and col.id not in seen:
            ordered.append(col.id)
            seen.add(col.id)
    return [c.id for c in REPORT18_OUTPUT_COLUMNS if c.id in seen] or report18_default_ids()


def resolve_report18_header_indexes(
    headers: list[str],
    selected_ids: list[str],
) -> tuple[list[str], list[int]]:
    """Map selected final-header ids to CSV header indexes."""
    header_by_norm = {str(h).strip().lower(): idx for idx, h in enumerate(headers)}
    visible: list[str] = []
    indexes: list[int] = []
    for cid in selected_ids:
        idx = header_by_norm.get(str(cid).strip().lower())
        if idx is None:
            continue
        visible.append(headers[idx])
        indexes.append(idx)
    if not indexes:
        return list(headers), list(range(len(headers)))
    return visible, indexes
