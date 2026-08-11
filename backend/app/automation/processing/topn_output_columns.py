"""Namespaced output column catalog and projection for Reports 3 and 4."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

TOPN_REPORT_SLUGS = frozenset({"train-no", "types", "report3", "report4"})

TOPN_GROUP = "metrics"


@dataclass(frozen=True)
class TopnOutputColumn:
    id: str
    group: str
    label: str
    field: str
    aliases: tuple[str, ...]
    computed: bool = False


def _topn_col(
    prefix: str,
    field_id: str,
    label: str,
    field: str,
    *aliases: str,
    computed: bool = False,
) -> TopnOutputColumn:
    alias_set = (field, label, *aliases)
    return TopnOutputColumn(
        id=f"{prefix}.{field_id}",
        group=TOPN_GROUP,
        label=label,
        field=field,
        aliases=tuple(dict.fromkeys(alias_set)),
        computed=computed,
    )


def _build_topn_catalog(
    prefix: str,
    *,
    train_no_after_sno: bool = False,
) -> tuple[TopnOutputColumn, ...]:
    """Build Top-N column catalog.

    Report 3 (train-no): Train No. immediately after S.No.
    Report 5 / types: keep Train No. after Owning Division (unchanged).
    """
    sno = _topn_col(prefix, "sno", "S.No.", "serialNo", "S.No", "Sl No", computed=True)
    train_no = _topn_col(prefix, "train_no", "Train No.", "trainNo", "Train No", "Train No.")
    train_name = _topn_col(prefix, "train_name", "Train Name", "trainName", "Train Name")
    owning_zone = _topn_col(prefix, "owning_zone", "Owning Zone", "owningZone", "Owning Zone")
    owning_division = _topn_col(
        prefix,
        "owning_division",
        "Owning Division",
        "owningDivision",
        "Owning Division",
    )
    rest = (
        _topn_col(prefix, "received", "Received", "received", "Received"),
        _topn_col(
            prefix,
            "percent_share",
            "% Share",
            "percentShare",
            "Percentage Share",
        ),
        _topn_col(prefix, "closed", "Closed", "closed", "Closed"),
        _topn_col(
            prefix,
            "percent_closed",
            "% Closed",
            "percentClosed",
            "Percentage Closed",
        ),
        _topn_col(prefix, "pending", "Pending", "pending", "Pending"),
        _topn_col(
            prefix,
            "average_rating",
            "Average Rating",
            "averageRating",
            "Avg. Rating",
        ),
    )
    if train_no_after_sno:
        return (sno, train_no, train_name, owning_zone, owning_division, *rest)
    return (sno, train_name, owning_zone, owning_division, train_no, *rest)


TRAIN_NO_COLUMNS: tuple[TopnOutputColumn, ...] = _build_topn_catalog(
    "train-no",
    train_no_after_sno=True,
)
TYPES_COLUMNS: tuple[TopnOutputColumn, ...] = _build_topn_catalog("types")

TRAIN_NO_IDS: frozenset[str] = frozenset(c.id for c in TRAIN_NO_COLUMNS)
TYPES_IDS: frozenset[str] = frozenset(c.id for c in TYPES_COLUMNS)

DEFAULT_TOPN_IDS: list[str] = [
    "train-no.sno",
    "train-no.train_no",
    "train-no.train_name",
    "train-no.owning_zone",
    "train-no.owning_division",
    "train-no.received",
    "train-no.percent_share",
    "train-no.closed",
    "train-no.percent_closed",
    "train-no.pending",
    "train-no.average_rating",
]

DEFAULT_TYPES_IDS: list[str] = [
    "types.sno",
    "types.train_name",
    "types.owning_zone",
    "types.owning_division",
    "types.train_no",
    "types.received",
    "types.percent_share",
    "types.closed",
    "types.percent_closed",
    "types.pending",
    "types.average_rating",
]

# Legacy flat labels / camelCase → namespaced ID
TOPN_LEGACY_TO_NAMESPACED: dict[str, dict[str, str]] = {
    "train-no": {
        "serialNo": "train-no.sno",
        "S.No.": "train-no.sno",
        "S.No": "train-no.sno",
        "trainName": "train-no.train_name",
        "Train Name": "train-no.train_name",
        "owningZone": "train-no.owning_zone",
        "Owning Zone": "train-no.owning_zone",
        "owningDivision": "train-no.owning_division",
        "Owning Division": "train-no.owning_division",
        "trainNo": "train-no.train_no",
        "Train No.": "train-no.train_no",
        "Train No": "train-no.train_no",
        "received": "train-no.received",
        "Received": "train-no.received",
        "percentShare": "train-no.percent_share",
        "% Share": "train-no.percent_share",
        "closed": "train-no.closed",
        "Closed": "train-no.closed",
        "percentClosed": "train-no.percent_closed",
        "% Closed": "train-no.percent_closed",
        "pending": "train-no.pending",
        "Pending": "train-no.pending",
        "averageRating": "train-no.average_rating",
        "Average Rating": "train-no.average_rating",
    },
    "types": {
        "serialNo": "types.sno",
        "S.No.": "types.sno",
        "S.No": "types.sno",
        "trainName": "types.train_name",
        "Train Name": "types.train_name",
        "owningZone": "types.owning_zone",
        "Owning Zone": "types.owning_zone",
        "owningDivision": "types.owning_division",
        "Owning Division": "types.owning_division",
        "trainNo": "types.train_no",
        "Train No.": "types.train_no",
        "Train No": "types.train_no",
        "received": "types.received",
        "Received": "types.received",
        "percentShare": "types.percent_share",
        "% Share": "types.percent_share",
        "closed": "types.closed",
        "Closed": "types.closed",
        "percentClosed": "types.percent_closed",
        "% Closed": "types.percent_closed",
        "pending": "types.pending",
        "Pending": "types.pending",
        "averageRating": "types.average_rating",
        "Average Rating": "types.average_rating",
    },
}


def _canonical_topn_slug(report_slug: str) -> str:
    from app.automation.report_keys import canonicalize_report_key

    slug = canonicalize_report_key(report_slug)
    if slug in {"report3", "train-no"}:
        return "train-no"
    if slug in {"report4", "types"}:
        return "types"
    return slug


def topn_catalog_for_slug(report_slug: str) -> tuple[TopnOutputColumn, ...]:
    slug = _canonical_topn_slug(report_slug)
    if slug == "types":
        return TYPES_COLUMNS
    return TRAIN_NO_COLUMNS


def topn_default_ids(report_slug: str) -> list[str]:
    slug = _canonical_topn_slug(report_slug)
    if slug == "types":
        return list(DEFAULT_TYPES_IDS)
    return list(DEFAULT_TOPN_IDS)


def topn_allowed_ids(report_slug: str) -> frozenset[str]:
    slug = _canonical_topn_slug(report_slug)
    if slug == "types":
        return TYPES_IDS
    return TRAIN_NO_IDS


def migrate_topn_to_namespaced_ids(report_slug: str, selected: Iterable[str]) -> list[str]:
    slug = _canonical_topn_slug(report_slug)
    if slug not in TOPN_LEGACY_TO_NAMESPACED:
        return []
    mapping = TOPN_LEGACY_TO_NAMESPACED[slug]
    allowed = topn_allowed_ids(slug)
    prefix = slug

    migrated: list[str] = []
    seen: set[str] = set()
    for raw in selected:
        text = str(raw or "").strip()
        if not text:
            continue
        if text.startswith(f"{prefix}."):
            key = text
        elif text.startswith("train-no.") and slug == "types":
            continue
        elif text.startswith("types.") and slug == "train-no":
            continue
        else:
            key = mapping.get(text, text)
        if key in allowed and key not in seen:
            migrated.append(key)
            seen.add(key)
    return migrated


def ensure_report3_train_no_after_sno(selected_ids: Iterable[str], report_slug: str) -> list[str]:
    """Report 3 only: place Train No. immediately after S.No. when both are selected."""
    keys = list(selected_ids)
    if _canonical_topn_slug(report_slug) != "train-no":
        return keys
    sno_id = "train-no.sno"
    train_no_id = "train-no.train_no"
    if sno_id not in keys or train_no_id not in keys:
        return keys
    without_train_no = [key for key in keys if key != train_no_id]
    sno_index = without_train_no.index(sno_id)
    return (
        without_train_no[: sno_index + 1]
        + [train_no_id]
        + without_train_no[sno_index + 1 :]
    )


def topn_labels(selected_ids: Iterable[str], report_slug: str) -> list[str]:
    catalog = {col.id: col for col in topn_catalog_for_slug(report_slug)}
    ordered = ensure_report3_train_no_after_sno(selected_ids, report_slug)
    return [catalog[col_id].label for col_id in ordered if col_id in catalog]


def resolve_topn_row_value(row: dict[str, str], column: TopnOutputColumn) -> str:
    for alias in column.aliases:
        value = row.get(alias)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return ""


def build_canonical_topn_row(row: dict[str, str], *, serial: int | None = None) -> dict[str, str]:
    """Map source CSV dict to canonical internal field keys."""
    catalog = TRAIN_NO_COLUMNS
    canonical: dict[str, str] = {}
    for column in catalog:
        if column.computed:
            if serial is not None:
                canonical[column.field] = str(serial)
            continue
        canonical[column.field] = resolve_topn_row_value(row, column)
    return canonical


def validate_selected_topn_fields(
    rows: list[dict[str, str]],
    selected_ids: list[str],
    report_slug: str,
) -> list[str]:
    if not rows:
        return []
    catalog = {col.id: col for col in topn_catalog_for_slug(report_slug)}
    header_keys: set[str] = set()
    for row in rows:
        header_keys.update(row.keys())
    unavailable: list[str] = []
    for col_id in selected_ids:
        column = catalog.get(col_id)
        if column is None or column.computed:
            continue
        if any(alias in header_keys for alias in column.aliases):
            continue
        if any(column.field in row for row in rows):
            continue
        unavailable.append(col_id)
    return unavailable


def project_topn_dict_rows(
    rows: list[dict[str, str]],
    selected_ids: Iterable[str],
    report_slug: str,
) -> tuple[list[str], list[list[str]]]:
    catalog = {col.id: col for col in topn_catalog_for_slug(report_slug)}
    key_list = ensure_report3_train_no_after_sno(selected_ids, report_slug)
    out_headers: list[str] = []
    columns: list[TopnOutputColumn] = []
    for col_id in key_list:
        column = catalog.get(col_id)
        if column is None:
            raise ValueError(f"Report {report_slug} unknown output column id: {col_id}")
        out_headers.append(column.label)
        columns.append(column)

    out_rows: list[list[str]] = []
    for index, row in enumerate(rows, start=1):
        values: list[str] = []
        for column in columns:
            if column.field == "serialNo":
                values.append(str(index))
            else:
                values.append(resolve_topn_row_value(row, column))
        out_rows.append(values)
    return out_headers, out_rows


def project_topn_canonical_rows(
    canonical_rows: list[dict[str, str]],
    selected_ids: Iterable[str],
    report_slug: str,
) -> tuple[list[str], list[list[str]]]:
    """Project from canonical internal dict rows (field keys like trainNo, trainName)."""
    catalog = {col.id: col for col in topn_catalog_for_slug(report_slug)}
    key_list = ensure_report3_train_no_after_sno(selected_ids, report_slug)
    out_headers: list[str] = []
    columns: list[TopnOutputColumn] = []
    for col_id in key_list:
        column = catalog.get(col_id)
        if column is None:
            raise ValueError(f"Report {report_slug} unknown output column id: {col_id}")
        out_headers.append(column.label)
        columns.append(column)

    out_rows: list[list[str]] = []
    for index, row in enumerate(canonical_rows, start=1):
        values: list[str] = []
        for column in columns:
            if column.field == "serialNo":
                values.append(str(index))
            else:
                values.append(str(row.get(column.field, "")).strip())
        out_rows.append(values)
    return out_headers, out_rows


def topn_catalog_entries(report_slug: str) -> list[dict[str, object]]:
    defaults = set(topn_default_ids(report_slug))
    return [
        {
            "id": column.id,
            "label": column.label,
            "group": column.group,
            "group_title": "Output Columns",
            "required": False,
            "default_visible": column.id in defaults,
        }
        for column in topn_catalog_for_slug(report_slug)
    ]
