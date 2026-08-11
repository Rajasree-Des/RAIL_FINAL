"""Output column catalog for Report 14 Watering Complaints (merged layout)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Report14Column:
    id: str
    label: str
    required: bool = False
    default_visible: bool = True
    group: str = "shared"
    group_title: str = "Shared"


REPORT14_OUTPUT_COLUMNS: tuple[Report14Column, ...] = (
    Report14Column("sno", "S.No.", required=True, group="shared", group_title="Shared"),
    Report14Column(
        "division",
        "Division",
        required=True,
        group="shared",
        group_title="Shared",
    ),
    Report14Column(
        "prev_received",
        "Previous Received",
        required=True,
        group="previous",
        group_title="W.r.to Previous Watering Point",
    ),
    Report14Column(
        "prev_pct_share",
        "Previous % Share",
        group="previous",
        group_title="W.r.to Previous Watering Point",
    ),
    Report14Column(
        "prev_avg_rating",
        "Previous Average Rating",
        group="previous",
        group_title="W.r.to Previous Watering Point",
    ),
    Report14Column(
        "up_received",
        "Upcoming Received",
        required=True,
        group="upcoming",
        group_title="W.r.to Upcoming Watering Point",
    ),
    Report14Column(
        "up_pct_share",
        "Upcoming % Share",
        group="upcoming",
        group_title="W.r.to Upcoming Watering Point",
    ),
    Report14Column(
        "up_avg_rating",
        "Upcoming Average Rating",
        group="upcoming",
        group_title="W.r.to Upcoming Watering Point",
    ),
)

REPORT14_COLUMN_BY_ID: dict[str, Report14Column] = {
    c.id: c for c in REPORT14_OUTPUT_COLUMNS
}
REPORT14_LABEL_BY_ID: dict[str, str] = {c.id: c.label for c in REPORT14_OUTPUT_COLUMNS}
REPORT14_ID_BY_LABEL: dict[str, str] = {c.label: c.id for c in REPORT14_OUTPUT_COLUMNS}

# Sub-column headers under each grouped section (official Railway layout).
REPORT14_SUB_HEADERS = ("Received", "% Share", "Average Rating")
REPORT14_PREV_GROUP_TITLE = "W.r.to Previous Watering Point"
REPORT14_UP_GROUP_TITLE = "W.r.to Upcoming Watering Point"


def report14_default_ids() -> list[str]:
    return [c.id for c in REPORT14_OUTPUT_COLUMNS if c.default_visible]


def report14_allowed_ids() -> frozenset[str]:
    return frozenset(REPORT14_COLUMN_BY_ID.keys())


def report14_catalog_entries() -> list[dict[str, object]]:
    return [
        {
            "id": c.id,
            "label": c.label,
            "required": c.required,
            "default_visible": c.default_visible,
            "group": c.group,
            "group_title": c.group_title,
        }
        for c in REPORT14_OUTPUT_COLUMNS
    ]


def report14_labels(ids: Iterable[str]) -> list[str]:
    return [REPORT14_LABEL_BY_ID[i] for i in ids if i in REPORT14_LABEL_BY_ID]


def validate_selected_report14_fields(selected: Iterable[str]) -> list[str]:
    allowed = report14_allowed_ids()
    ordered: list[str] = []
    seen: set[str] = set()
    for item in selected:
        key = str(item).strip()
        if not key or key in seen or key not in allowed:
            continue
        seen.add(key)
        ordered.append(key)
    for col in REPORT14_OUTPUT_COLUMNS:
        if col.required and col.id not in seen:
            ordered.insert(0 if col.id == "sno" else len(ordered), col.id)
            seen.add(col.id)
    fixed: list[str] = []
    if "sno" in seen:
        fixed.append("sno")
    if "division" in seen:
        fixed.append("division")
    for key in ordered:
        if key not in fixed:
            fixed.append(key)
    return fixed if fixed else report14_default_ids()
