"""Output column catalog for Report 9 (Cause Wise Grievances)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Report9Column:
    id: str
    label: str
    required: bool = False
    default_visible: bool = True
    index: int = 0


REPORT9_OUTPUT_COLUMNS: tuple[Report9Column, ...] = (
    Report9Column("sno", "S.No.", required=True, index=0),
    Report9Column("cause", "Cause", required=True, index=1),
    Report9Column("received", "Received", required=True, index=2),
    Report9Column("share_percent", "% Share", index=3),
)

REPORT9_COLUMN_BY_ID: dict[str, Report9Column] = {c.id: c for c in REPORT9_OUTPUT_COLUMNS}
REPORT9_LABEL_BY_ID: dict[str, str] = {c.id: c.label for c in REPORT9_OUTPUT_COLUMNS}


def report9_default_ids() -> list[str]:
    return [c.id for c in REPORT9_OUTPUT_COLUMNS if c.default_visible]


def report9_allowed_ids() -> frozenset[str]:
    return frozenset(REPORT9_COLUMN_BY_ID.keys())


def report9_catalog_entries() -> list[dict[str, object]]:
    return [
        {
            "id": c.id,
            "label": c.label,
            "required": c.required,
            "default_visible": c.default_visible,
            "group": "cause_wise",
            "group_title": "Cause Wise Columns",
        }
        for c in REPORT9_OUTPUT_COLUMNS
    ]


def report9_labels(ids: Iterable[str]) -> list[str]:
    return [REPORT9_LABEL_BY_ID[i] for i in ids if i in REPORT9_LABEL_BY_ID]


def validate_selected_report9_fields(selected: Iterable[str]) -> list[str]:
    allowed = report9_allowed_ids()
    ordered: list[str] = []
    seen: set[str] = set()
    for item in selected:
        key = str(item).strip()
        if not key or key in seen or key not in allowed:
            continue
        seen.add(key)
        ordered.append(key)
    for col in REPORT9_OUTPUT_COLUMNS:
        if col.required and col.id not in seen:
            ordered.insert(0 if col.id == "sno" else len(ordered), col.id)
            seen.add(col.id)
    # Keep stable catalog order for selected ids.
    return [c.id for c in REPORT9_OUTPUT_COLUMNS if c.id in seen] or report9_default_ids()


def project_report9_row(row: list[str], selected_ids: list[str]) -> list[str]:
    indexes = [
        REPORT9_COLUMN_BY_ID[cid].index
        for cid in selected_ids
        if cid in REPORT9_COLUMN_BY_ID
    ]
    return [row[i] if i < len(row) else "" for i in indexes]
