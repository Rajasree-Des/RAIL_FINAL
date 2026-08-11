"""Canonical output column definitions for Reports 1, 2, 5, and 6."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.automation.formatting.serial import apply_serial_number

logger = logging.getLogger(__name__)

# Report 1 / 2 — columns hidden in Excel/PDF (1-based indices into merged header row)
REPORT1_HIDDEN_COLUMNS = {3, 10, 11, 12, 13, 14, 15}
REPORT2_HIDDEN_COLUMNS = {3, 7, 10, 11, 12, 13, 14, 15}

SOURCE_B_DATA_COLUMNS = [
    "Feedback Received",
    "% Feedback",
    "Excellent",
    "Satisfactory",
    "Unsatisfactory",
    "% Unsatisfactory",
]

REPORT1_OUTPUT_TOTAL_SIDECAR_FILENAME = "report1_output_total_row.json"

# Report 2 total row: copy these column totals from Report 1 when both schemas include them.
REPORT2_TOTALS_FROM_REPORT1_COLUMNS = frozenset(
    {
        "Received",
        "% Share",
        "Closed",
        "Avg. Disposal Time",
        "Feedback Received",
        "% Feedback",
        "Excellent",
        "Satisfactory",
        "Unsatisfactory",
        "% Unsatisfactory",
    }
)

# --- Report 1 / 2 namespaced output column IDs (Source A + Source B) ---

SOURCE_A_FIELD_ORDER: tuple[str, ...] = (
    "sno",
    "identifier",
    "opening_balance",
    "received",
    "percent_share",
    "closed",
    "closing_balance",
    "percent_disposal",
    "avg_disposal_time",
    "avg_rating",
    "avg_pendency_time",
    "forwarded",
    "avg_frt",
)

SOURCE_A_HEADER_BY_FIELD: dict[str, str] = {
    "sno": "S.No.",
    "identifier": "Organisation",
    "opening_balance": "Opening Balance",
    "received": "Received",
    "percent_share": "% Share",
    "closed": "Closed",
    "closing_balance": "Closing Balance",
    "percent_disposal": "% Disposal",
    "avg_disposal_time": "Avg. Disposal Time",
    "avg_rating": "Avg. Rating",
    "avg_pendency_time": "Avg. Pendency Time",
    "forwarded": "Forwarded",
    "avg_frt": "Avg. FRT",
}

SOURCE_B_FIELD_ORDER: tuple[str, ...] = (
    "sno",
    "organisation",
    "feedback_received",
    "percent_feedback",
    "excellent",
    "satisfactory",
    "unsatisfactory",
    "percent_unsatisfactory",
)

SOURCE_B_HEADER_BY_FIELD: dict[str, str] = {
    "sno": "S.No.",
    "organisation": "Organisation",
    "feedback_received": "Feedback Received",
    "percent_feedback": "% Feedback",
    "excellent": "Excellent",
    "satisfactory": "Satisfactory",
    "unsatisfactory": "Unsatisfactory",
    "percent_unsatisfactory": "% Unsatisfactory",
}

SOURCE_B_DATA_FIELD_ORDER: tuple[str, ...] = SOURCE_B_FIELD_ORDER[2:]

SOURCE_B_DATA_HEADER_BY_FIELD: dict[str, str] = {
    key: SOURCE_B_HEADER_BY_FIELD[key] for key in SOURCE_B_DATA_FIELD_ORDER
}


@dataclass(frozen=True)
class NamespacedOutputColumn:
    id: str
    group: str  # source_a | source_b
    label: str
    field: str


def _build_namespaced_catalog(
    prefix: str,
    *,
    source_a_identifier_field: str,
    source_a_identifier_label: str,
) -> tuple[NamespacedOutputColumn, ...]:
    columns: list[NamespacedOutputColumn] = []
    for field in SOURCE_A_FIELD_ORDER:
        if field == "identifier":
            columns.append(
                NamespacedOutputColumn(
                    id=f"{prefix}.source_a.{source_a_identifier_field}",
                    group="source_a",
                    label=source_a_identifier_label,
                    field=source_a_identifier_field,
                )
            )
        else:
            columns.append(
                NamespacedOutputColumn(
                    id=f"{prefix}.source_a.{field}",
                    group="source_a",
                    label=SOURCE_A_HEADER_BY_FIELD[field],
                    field=field,
                )
            )
    for field in SOURCE_B_FIELD_ORDER:
        columns.append(
            NamespacedOutputColumn(
                id=f"{prefix}.source_b.{field}",
                group="source_b",
                label=SOURCE_B_HEADER_BY_FIELD[field],
                field=field,
            )
        )
    return tuple(columns)


REPORT1_NAMESPACED_COLUMNS: tuple[NamespacedOutputColumn, ...] = _build_namespaced_catalog(
    "report1",
    source_a_identifier_field="organisation",
    source_a_identifier_label="Organisation",
)

REPORT2_NAMESPACED_COLUMNS: tuple[NamespacedOutputColumn, ...] = _build_namespaced_catalog(
    "division",
    source_a_identifier_field="division",
    source_a_identifier_label="Division",
)

REPORT1_NAMESPACED_IDS: frozenset[str] = frozenset(c.id for c in REPORT1_NAMESPACED_COLUMNS)
REPORT2_NAMESPACED_IDS: frozenset[str] = frozenset(c.id for c in REPORT2_NAMESPACED_COLUMNS)

REPORT1_DEFAULT_NAMESPACED_KEYS: list[str] = [
    "report1.source_a.sno",
    "report1.source_a.organisation",
    "report1.source_a.received",
    "report1.source_a.percent_share",
    "report1.source_a.closed",
    "report1.source_a.avg_disposal_time",
    "report1.source_b.feedback_received",
    "report1.source_b.percent_feedback",
    "report1.source_b.excellent",
    "report1.source_b.satisfactory",
    "report1.source_b.unsatisfactory",
    "report1.source_b.percent_unsatisfactory",
]

REPORT2_DEFAULT_NAMESPACED_KEYS: list[str] = [
    "division.source_a.sno",
    "division.source_a.division",
    "division.source_a.received",
    "division.source_a.percent_share",
    "division.source_a.closed",
    "division.source_a.avg_disposal_time",
    "division.source_b.feedback_received",
    "division.source_b.percent_feedback",
    "division.source_b.excellent",
    "division.source_b.satisfactory",
    "division.source_b.unsatisfactory",
    "division.source_b.percent_unsatisfactory",
]

REPORT1_LEGACY_TO_NAMESPACED: dict[str, str] = {
    "serialNo": "report1.source_a.sno",
    "organisation": "report1.source_a.organisation",
    "openingBalance": "report1.source_a.opening_balance",
    "received": "report1.source_a.received",
    "pctShare": "report1.source_a.percent_share",
    "closed": "report1.source_a.closed",
    "closingBalance": "report1.source_a.closing_balance",
    "pctDisposal": "report1.source_a.percent_disposal",
    "avgDisposalTime": "report1.source_a.avg_disposal_time",
    "avgRating": "report1.source_a.avg_rating",
    "avgPendencyTime": "report1.source_a.avg_pendency_time",
    "forwarded": "report1.source_a.forwarded",
    "avgFrt": "report1.source_a.avg_frt",
    "feedbackReceived": "report1.source_b.feedback_received",
    "pctFeedback": "report1.source_b.percent_feedback",
    "excellent": "report1.source_b.excellent",
    "satisfactory": "report1.source_b.satisfactory",
    "unsatisfactory": "report1.source_b.unsatisfactory",
    "pctUnsatisfactory": "report1.source_b.percent_unsatisfactory",
}

REPORT2_LEGACY_TO_NAMESPACED: dict[str, str] = {
    "serialNo": "division.source_a.sno",
    "division": "division.source_a.division",
    "organisation": "division.source_a.division",
    "openingBalance": "division.source_a.opening_balance",
    "received": "division.source_a.received",
    "pctShare": "division.source_a.percent_share",
    "closed": "division.source_a.closed",
    "closingBalance": "division.source_a.closing_balance",
    "pctDisposal": "division.source_a.percent_disposal",
    "avgDisposalTime": "division.source_a.avg_disposal_time",
    "avgRating": "division.source_a.avg_rating",
    "avgPendencyTime": "division.source_a.avg_pendency_time",
    "forwarded": "division.source_a.forwarded",
    "avgFrt": "division.source_a.avg_frt",
    "feedbackReceived": "division.source_b.feedback_received",
    "pctFeedback": "division.source_b.percent_feedback",
    "excellent": "division.source_b.excellent",
    "satisfactory": "division.source_b.satisfactory",
    "unsatisfactory": "division.source_b.unsatisfactory",
    "pctUnsatisfactory": "division.source_b.percent_unsatisfactory",
}

NAMESPACED_REPORT_SLUGS = frozenset({"report1", "division"})


def namespaced_catalog_for_slug(report_slug: str) -> tuple[NamespacedOutputColumn, ...]:
    if report_slug == "report1":
        return REPORT1_NAMESPACED_COLUMNS
    if report_slug == "division":
        return REPORT2_NAMESPACED_COLUMNS
    return ()


def default_namespaced_keys(report_slug: str) -> list[str]:
    if report_slug == "report1":
        return list(REPORT1_DEFAULT_NAMESPACED_KEYS)
    if report_slug == "division":
        return list(REPORT2_DEFAULT_NAMESPACED_KEYS)
    return []


def migrate_to_namespaced_ids(report_slug: str, selected: Iterable[str]) -> list[str]:
    """Map legacy flat keys or namespaced IDs to canonical namespaced IDs."""
    if report_slug == "report1":
        mapping = REPORT1_LEGACY_TO_NAMESPACED
        allowed = REPORT1_NAMESPACED_IDS
    elif report_slug == "division":
        mapping = REPORT2_LEGACY_TO_NAMESPACED
        allowed = REPORT2_NAMESPACED_IDS
    else:
        return list(selected)

    migrated: list[str] = []
    seen: set[str] = set()
    for raw in selected:
        text = str(raw or "").strip()
        if not text:
            continue
        key = mapping.get(text, text)
        if key in allowed and key not in seen:
            migrated.append(key)
            seen.add(key)
    return migrated


def _namespaced_field_offset(field: str, *, source_a_identifier_field: str) -> int:
    if field == source_a_identifier_field:
        return SOURCE_A_FIELD_ORDER.index("identifier")
    try:
        return SOURCE_A_FIELD_ORDER.index(field)
    except ValueError:
        raise ValueError(f"Unknown source_a field: {field}") from None


def resolve_namespaced_merged_index(
    column: NamespacedOutputColumn,
    *,
    source_a_len: int,
    source_a_identifier_field: str,
) -> int:
    if column.group == "source_a":
        offset = _namespaced_field_offset(
            column.field,
            source_a_identifier_field=source_a_identifier_field,
        )
        return offset
    if column.group == "source_b":
        if column.field == "sno":
            return source_a_len
        if column.field == "organisation":
            return source_a_len + 1
        data_offset = SOURCE_B_DATA_FIELD_ORDER.index(column.field)
        return source_a_len + 2 + data_offset
    raise ValueError(f"Unknown column group: {column.group}")


def resolve_namespaced_output_label(
    column: NamespacedOutputColumn,
    selected_ids: Iterable[str],
) -> str:
    if column.group == "source_a" and column.field == "sno":
        return "S.No."
    if column.group == "source_b" and column.field == "sno":
        return "Feedback S.No."
    if column.group == "source_a" and column.field in {"organisation", "division"}:
        return column.label
    if column.group == "source_b" and column.field == "organisation":
        return "Feedback Organisation"
    return column.label


def project_merged_table_namespaced(
    merged_headers: list[str],
    rows: list[list[str]],
    selected_ids: Iterable[str],
    *,
    report_slug: str,
    report_label: str = "Report",
) -> tuple[list[str], list[list[str]]]:
    """Project merged internal table using namespaced column IDs and user order."""
    catalog = namespaced_catalog_for_slug(report_slug)
    if not catalog:
        raise ValueError(f"{report_label} does not use namespaced projection")
    id_to_col = {col.id: col for col in catalog}
    key_list = list(selected_ids)
    source_a_len = len(merged_headers) - 2 - len(SOURCE_B_DATA_COLUMNS)
    if source_a_len < 1:
        raise ValueError(
            f"{report_label} invalid merged headers (source_a_len={source_a_len}): "
            f"{merged_headers}"
        )
    identifier_field = "organisation" if report_slug == "report1" else "division"

    out_headers: list[str] = []
    indices: list[int] = []
    for col_id in key_list:
        column = id_to_col.get(col_id)
        if column is None:
            raise ValueError(f"{report_label} unknown output column id: {col_id}")
        idx = resolve_namespaced_merged_index(
            column,
            source_a_len=source_a_len,
            source_a_identifier_field=identifier_field,
        )
        if idx >= len(merged_headers):
            raise ValueError(
                f"{report_label} column {col_id} index {idx} out of range "
                f"(merged width={len(merged_headers)})"
            )
        out_headers.append(resolve_namespaced_output_label(column, key_list))
        indices.append(idx)

    out_rows = [
        [row[idx] if idx < len(row) else "" for idx in indices]
        for row in rows
    ]
    return out_headers, out_rows


def namespaced_labels(selected_ids: Iterable[str], report_slug: str) -> list[str]:
    catalog = namespaced_catalog_for_slug(report_slug)
    id_to_col = {col.id: col for col in catalog}
    selected = list(selected_ids)
    return [
        resolve_namespaced_output_label(id_to_col[col_id], selected)
        for col_id in selected
        if col_id in id_to_col
    ]

SUMMABLE_HEADERS = frozenset(
    {
        "Opening Balance",
        "Received",
        "Closed",
        "Closing Balance",
        "Forwarded",
        "Feedback Received",
        "Excellent",
        "Satisfactory",
        "Unsatisfactory",
    }
)

AGGREGATE_HEADERS = frozenset(
    {
        "% Share",
        "% Disposal",
        "% Feedback",
        "% Unsatisfactory",
        "Avg. Disposal Time",
        "Avg. Rating",
        "Avg. Pendency Time",
        "Avg. FRT",
    }
)

ORG_HEADERS = frozenset({"Organisation", "Division", "Organization"})


@dataclass(frozen=True)
class OutputColumn:
    key: str
    label: str
    aliases: tuple[str, ...]
    required: bool = True
    computed: bool = False


def _col(
    key: str,
    label: str,
    *aliases: str,
    required: bool = True,
    computed: bool = False,
) -> OutputColumn:
    names = (label, *aliases)
    return OutputColumn(key=key, label=label, aliases=names, required=required, computed=computed)


REPORT1_OUTPUT_COLUMNS: tuple[OutputColumn, ...] = (
    _col("serialNo", "S.No.", "S.No.", required=False, computed=True),
    _col("organisation", "Organisation", "Organisation", "Organization"),
    _col("openingBalance", "Opening Balance", "Opening Balance"),
    _col("received", "Received", "Received"),
    _col("pctShare", "% Share", "% Share"),
    _col("closed", "Closed", "Closed"),
    _col("closingBalance", "Closing Balance", "Closing Balance"),
    _col("pctDisposal", "% Disposal", "% Disposal"),
    _col("avgDisposalTime", "Avg. Disposal Time", "Avg. Disposal Time", required=False),
    _col("avgRating", "Avg. Rating", "Avg. Rating", required=False),
    _col("avgPendencyTime", "Avg. Pendency Time", "Avg. Pendency Time", required=False),
    _col("forwarded", "Forwarded", "Forwarded", required=False),
    _col("avgFrt", "Avg. FRT", "Avg. FRT", required=False),
    _col("feedbackReceived", "Feedback Received", "Feedback Received"),
    _col("pctFeedback", "% Feedback", "% Feedback"),
    _col("excellent", "Excellent", "Excellent"),
    _col("satisfactory", "Satisfactory", "Satisfactory"),
    _col("unsatisfactory", "Unsatisfactory", "Unsatisfactory"),
    _col("pctUnsatisfactory", "% Unsatisfactory", "% Unsatisfactory"),
)

REPORT2_OUTPUT_COLUMNS: tuple[OutputColumn, ...] = (
    _col("serialNo", "S.No.", "S.No.", required=False, computed=True),
    _col("division", "Division", "Organisation", "Organization", "Division"),
    _col("openingBalance", "Opening Balance", "Opening Balance"),
    _col("received", "Received", "Received"),
    _col("pctShare", "% Share", "% Share"),
    _col("closed", "Closed", "Closed"),
    _col("closingBalance", "Closing Balance", "Closing Balance"),
    _col("pctDisposal", "% Disposal", "% Disposal"),
    _col("avgDisposalTime", "Avg. Disposal Time", "Avg. Disposal Time", required=False),
    _col("avgRating", "Avg. Rating", "Avg. Rating", required=False),
    _col("avgPendencyTime", "Avg. Pendency Time", "Avg. Pendency Time", required=False),
    _col("forwarded", "Forwarded", "Forwarded", required=False),
    _col("avgFrt", "Avg. FRT", "Avg. FRT", required=False),
    _col("feedbackReceived", "Feedback Received", "Feedback Received"),
    _col("pctFeedback", "% Feedback", "% Feedback"),
    _col("excellent", "Excellent", "Excellent"),
    _col("satisfactory", "Satisfactory", "Satisfactory"),
    _col("unsatisfactory", "Unsatisfactory", "Unsatisfactory"),
    _col("pctUnsatisfactory", "% Unsatisfactory", "% Unsatisfactory"),
)

REPORT5_OUTPUT_COLUMNS: tuple[OutputColumn, ...] = (
    _col("serialNo", "S.No.", computed=True, required=False),
    _col("complaintRefNo", "Complaint Ref Number", "complaintRefNo", "Ref. No.", "Refer Number", "Reference Number"),
    _col("createdOn", "Created On", "createdOn", "Registration Date", "Complaint Date", "Date"),
    _col("trainStation", "Train/Station", "trainStation", "Train", "Station"),
    _col("complaintTypeName", "Comp Type Name", "complaintTypeName", "Type"),
    _col("subTypeName", "Sub Type Name", "subTypeName", "Sub Type", "SubType", "Subtype"),
    _col("zoneCode", "Zone Code", "zoneCode", "Zone", "Owning Zone"),
    _col("divCode", "Div Code", "divCode", "Div", "Owning Div"),
    _col("department", "Department", "department", "Dept", "deptCode"),
    _col("status", "Status", "status", "finalStatus"),
    _col("feedbackRemark", "Feedback Remark", "feedbackRemark"),
    _col(
        "trainNameForReport",
        "Train Name For Report",
        "trainNameForReport",
        "trainNameForReport/Station Name",
    ),
    _col("complaintDesc", "Complaint Description", "complaintDesc"),
    _col("remarks", "Remarks", "remarks"),
    _col("userId", "User ID", "userId", "User Id"),
)

REPORT6_OUTPUT_COLUMNS: tuple[OutputColumn, ...] = (
    _col("serialNo", "S.No.", computed=True, required=False),
    _col("complaintRefNo", "Complaint Ref Number", "complaintRefNo", "Ref. No.", "Refer Number", "Reference Number"),
    _col("trainStation", "Train/Station", "trainStation", "Train", "Station"),
    _col("complaintTypeName", "Comp Type Name", "complaintTypeName", "Type"),
    _col("subTypeName", "Sub Type Name", "subTypeName", "Sub Type", "SubType", "Subtype"),
    _col("zoneCode", "Zone Code", "zoneCode", "Zone", "Owning Zone"),
    _col("divCode", "Div Code", "divCode", "Div", "Owning Div"),
    _col("department", "Department", "department", "Dept", "deptCode"),
    _col("status", "Status", "status", "finalStatus"),
    _col("feedbackRemark", "Feedback Remark", "feedbackRemark"),
    _col("complaintDesc", "Complaint Description", "complaintDesc"),
    _col("remarks", "Remarks", "remarks"),
    _col("userId", "User ID", "userId", "User Id"),
)

REMOVED_OUTPUT_LABELS = frozenset(
    {
        "Ref. No.",
        "Refer Number",
        "Reference Number",
        "Complaint Date",
        "Department",
        "Mode",
        "Complaint Mode",
        "Type",
        "Sub Type",
        "SubType",
        "Subtype",
    }
)

LEGACY_COLUMN_KEY_ALIASES: dict[str, str] = {
    "refNo": "complaintRefNo",
    "complaintDate": "createdOn",
    "type": "complaintTypeName",
    "subType": "subTypeName",
    "mode": "mode",  # removed — drop on migration
    "zone": "zoneCode",
    "div": "divCode",
}


def output_labels(columns: Iterable[OutputColumn]) -> list[str]:
    return [column.label for column in columns]


REPORT1_SELECTED_KEYS: list[str] = list(REPORT1_DEFAULT_NAMESPACED_KEYS)

REPORT2_SELECTED_KEYS: list[str] = list(REPORT2_DEFAULT_NAMESPACED_KEYS)

REPORT1_UNAPPROVED_KEYS = frozenset(
    {
        "openingBalance",
        "closingBalance",
        "pctDisposal",
        "avgRating",
        "avgPendencyTime",
        "forwarded",
        "avgFrt",
    }
)

REPORT2_UNAPPROVED_KEYS = frozenset(
    {
        "openingBalance",
        "closingBalance",
        "pctDisposal",
        "avgRating",
        "avgPendencyTime",
        "forwarded",
        "avgFrt",
    }
)

REPORT1_UNAPPROVED_LABELS = frozenset(
    {
        "Opening Balance",
        "Closing Balance",
        "% Disposal",
        "Avg. Rating",
        "Avg. Pendency Time",
        "Forwarded",
        "Avg. FRT",
    }
)

REPORT2_UNAPPROVED_LABELS = frozenset(
    {
        "Opening Balance",
        "Closing Balance",
        "% Disposal",
        "% Balance",
        "Avg. Rating",
        "Avg. Pendency Time",
        "Forwarded",
        "Avg. FRT",
    }
)

REPORT5_SELECTED_KEYS: list[str] = [
    "scr-train.sno",
    "scr-train.complaint_ref_no",
    "scr-train.created_on",
    "scr-train.train_station",
    "scr-train.comp_type_name",
    "scr-train.sub_type_name",
    "scr-train.zone_code",
    "scr-train.div_code",
    "scr-train.feedback_remark",
    "scr-train.train_name_for_report",
    "scr-train.complaint_desc",
    "scr-train.remarks",
    "scr-train.user_id",
]

REPORT6_SELECTED_KEYS: list[str] = [
    "scr-station.sno",
    "scr-station.complaint_ref_no",
    "scr-station.train_station",
    "scr-station.comp_type_name",
    "scr-station.sub_type_name",
    "scr-station.zone_code",
    "scr-station.div_code",
    "scr-station.feedback_remark",
    "scr-station.complaint_desc",
    "scr-station.remarks",
    "scr-station.user_id",
]

REPORT5_UNAPPROVED_KEYS = frozenset(
    {
        "department",
        "deptCode",
        "status",
        "mode",
    }
)

REPORT6_UNAPPROVED_KEYS = frozenset(
    {
        "department",
        "deptCode",
        "status",
        "createdOn",
        "trainNameForReport",
        "mode",
    }
)

REPORT5_UNAPPROVED_LABELS = frozenset(
    {
        "Department",
        "Status",
        "Mode",
        "Complaint Mode",
        "Ref. No.",
        "Refer Number",
        "Reference Number",
        "Complaint Date",
        "Type",
        "Sub Type",
        "SubType",
        "Subtype",
    }
)

REPORT6_UNAPPROVED_LABELS = frozenset(
    {
        "Department",
        "Status",
        "Created On",
        "Complaint Date",
        "Train Name For Report",
        "Mode",
        "Complaint Mode",
        "Ref. No.",
        "Refer Number",
        "Reference Number",
        "Type",
        "Sub Type",
        "SubType",
        "Subtype",
    }
)


def visible_merged_headers(headers: list[str], hidden: set[int]) -> list[str]:
    return [header for idx, header in enumerate(headers, start=1) if idx not in hidden]


def visible_merged_indices(headers: list[str], hidden: set[int]) -> list[int]:
    return [idx for idx in range(1, len(headers) + 1) if idx not in hidden]


def migrate_selected_column_keys(selected: Iterable[str]) -> list[str]:
    """Map legacy saved column keys to current canonical keys; drop removed fields."""
    migrated: list[str] = []
    seen: set[str] = set()
    for raw in selected:
        key = LEGACY_COLUMN_KEY_ALIASES.get(raw, raw)
        if key == "mode":
            continue
        if key not in seen:
            migrated.append(key)
            seen.add(key)
    return migrated


def default_output_column_keys(columns: tuple[OutputColumn, ...]) -> list[str]:
    """All output fields visible by default (includes serialNo)."""
    return [column.key for column in columns]


default_visible_column_keys = default_output_column_keys


def keys_to_output_labels(keys: Iterable[str], columns: tuple[OutputColumn, ...]) -> list[str]:
    key_to_label = {column.key: column.label for column in columns}
    return [key_to_label[key] for key in keys if key in key_to_label]


REPORT1_SELECTED_VISIBLE_LABELS = namespaced_labels(REPORT1_SELECTED_KEYS, "report1")
REPORT2_SELECTED_VISIBLE_LABELS = namespaced_labels(REPORT2_SELECTED_KEYS, "division")
REPORT5_SELECTED_VISIBLE_LABELS = [
    "S.No.",
    "Complaint Ref Number",
    "Created On",
    "Train/Station",
    "Comp Type Name",
    "Sub Type Name",
    "Zone Code",
    "Div Code",
    "Feedback Remark",
    "Train Name For Report",
    "Complaint Description",
    "Remarks",
    "User ID",
]
REPORT6_SELECTED_VISIBLE_LABELS = [
    "S.No.",
    "Complaint Ref Number",
    "Train/Station",
    "Comp Type Name",
    "Sub Type Name",
    "Zone Code",
    "Div Code",
    "Feedback Remark",
    "Complaint Description",
    "Remarks",
    "User ID",
]

# Backward-compatible aliases (prefer SELECTED_* for final output)
REPORT1_VISIBLE_LABELS = REPORT1_SELECTED_VISIBLE_LABELS
REPORT2_VISIBLE_LABELS = REPORT2_SELECTED_VISIBLE_LABELS
REPORT5_VISIBLE_LABELS = REPORT5_SELECTED_VISIBLE_LABELS
REPORT6_VISIBLE_LABELS = REPORT6_SELECTED_VISIBLE_LABELS


def select_columns_by_keys(
    columns: tuple[OutputColumn, ...],
    keys: Iterable[str],
) -> tuple[OutputColumn, ...]:
    key_to_col = {column.key: column for column in columns}
    selected: list[OutputColumn] = []
    for key in keys:
        column = key_to_col.get(key)
        if column is not None:
            selected.append(column)
    return tuple(selected)


def _source_index(full_headers: list[str], column: OutputColumn) -> int | None:
    for alias in column.aliases:
        if alias in full_headers:
            return full_headers.index(alias)
    return None


def project_merged_table(
    full_headers: list[str],
    rows: list[list[str]],
    selected_keys: Iterable[str],
    columns: tuple[OutputColumn, ...],
    *,
    report_label: str = "Report",
) -> tuple[list[str], list[list[str]]]:
    """Project merged internal table to the exact final allowlist (label order preserved)."""
    key_list = list(selected_keys)
    key_to_col = {column.key: column for column in columns}
    out_headers: list[str] = []
    indices: list[int | None] = []
    missing_required: list[str] = []

    for key in key_list:
        column = key_to_col.get(key)
        if column is None:
            raise ValueError(f"{report_label} unknown output column key: {key}")
        idx = _source_index(full_headers, column)
        if idx is None:
            if column.required and not column.computed:
                missing_required.append(f"{column.key} ({column.label})")
            out_headers.append(column.label)
            indices.append(None)
            continue
        out_headers.append(column.label)
        indices.append(idx)

    if missing_required:
        raise ValueError(
            f"{report_label} missing required source columns: {', '.join(missing_required)}; "
            f"discovered headers: {full_headers}"
        )
    if len(out_headers) != len(key_list):
        raise ValueError(
            f"{report_label} projection produced {len(out_headers)} columns, "
            f"expected {len(key_list)}"
        )

    out_rows = [
        [
            row[idx] if idx is not None and idx < len(row) else ""
            for idx in indices
        ]
        for row in rows
    ]
    return out_headers, out_rows


def assert_exact_visible_columns(
    expected_labels: list[str],
    headers: list[str],
    *,
    report_label: str = "Report",
) -> None:
    """Verify headers match the exact final allowlist with no extras."""
    if headers != expected_labels:
        raise AssertionError(
            f"{report_label} visible columns mismatch.\n"
            f"Expected ({len(expected_labels)}): {expected_labels}\n"
            f"Actual ({len(headers)}): {headers}"
        )


def merge_required_output_columns(
    selected: Iterable[str],
    columns: tuple[OutputColumn, ...],
) -> list[str]:
    """Backward-compatible alias: append only missing required keys."""
    from app.automation.processing.column_config import merge_saved_column_config

    return merge_saved_column_config(selected, columns)


def trim_worksheet_columns(worksheet, *, keep_columns: int) -> None:
    """Remove template columns beyond the processor output width."""
    if keep_columns <= 0:
        return
    extra = worksheet.max_column - keep_columns
    if extra > 0:
        worksheet.delete_cols(keep_columns + 1, extra)


def resolve_row_value(row: dict[str, str], column: OutputColumn) -> str:
    for alias in column.aliases:
        value = row.get(alias)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return ""


def validate_source_columns(
    source_headers: list[str],
    columns: tuple[OutputColumn, ...],
    *,
    report_label: str,
) -> None:
    header_set = set(source_headers)
    missing: list[str] = []
    for column in columns:
        if column.computed or not column.required:
            continue
        if not any(alias in header_set for alias in column.aliases):
            missing.append(f"{column.key} ({column.label})")
    if missing:
        raise ValueError(
            f"{report_label} missing required source columns: {', '.join(missing)}"
        )


def format_scr_output_rows(
    rows: list[dict[str, str]],
    columns: tuple[OutputColumn, ...],
) -> list[list[str]]:
    output: list[list[str]] = []
    for index, row in enumerate(rows, start=1):
        values: list[str] = []
        for column in columns:
            if column.key == "serialNo":
                values.append(str(index))
            else:
                values.append(resolve_row_value(row, column))
        output.append(values)
    return output


def _parse_int(value: str) -> int | None:
    text = str(value or "").replace(",", "").strip()
    if not text or text == "-":
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _sum_column(values: Iterable[str]) -> str:
    total = 0
    found = False
    for value in values:
        parsed = _parse_int(value)
        if parsed is not None:
            total += parsed
            found = True
    return str(total) if found else ""


def _cell_value_blank(value: str) -> bool:
    text = str(value or "").strip()
    return not text or text == "-"


def _format_percent(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return ""
    return f"{(numerator / denominator) * 100:.2f}"


def _get_int_at(values: list[str], idx: int | None) -> int | None:
    if idx is None or idx >= len(values):
        return None
    return _parse_int(values[idx])


def _backfill_summable_a_values(
    a_values: list[str],
    source_a_headers: list[str],
    data_rows: list[list[str]],
) -> None:
    """Fill blank summable Source A cells from merged data row sums."""
    for header in source_a_headers:
        if header not in SUMMABLE_HEADERS or header == "Closing Balance":
            continue
        idx = _header_index(source_a_headers, header)
        if idx is None or not _cell_value_blank(a_values[idx]):
            continue
        a_values[idx] = _sum_column(
            row[idx] for row in data_rows if idx < len(row)
        )


def _backfill_closing_balance(
    a_values: list[str],
    source_a_headers: list[str],
    data_rows: list[list[str]],
) -> None:
    closing_idx = _header_index(source_a_headers, "Closing Balance")
    if closing_idx is None or not _cell_value_blank(a_values[closing_idx]):
        return
    ob_idx = _header_index(source_a_headers, "Opening Balance")
    rec_idx = _header_index(source_a_headers, "Received")
    closed_idx = _header_index(source_a_headers, "Closed")
    if ob_idx is not None and rec_idx is not None and closed_idx is not None:
        opening = _get_int_at(a_values, ob_idx) or 0
        received = _get_int_at(a_values, rec_idx) or 0
        closed = _get_int_at(a_values, closed_idx) or 0
        if received > 0 or opening > 0:
            a_values[closing_idx] = str(opening + received - closed)
            return
    a_values[closing_idx] = _sum_column(
        row[closing_idx] for row in data_rows if closing_idx < len(row)
    )


def _parse_float_percent(value: str) -> float | None:
    text = str(value or "").replace("%", "").replace(",", "").strip()
    if not text or text == "-":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _sum_percent_column(values: Iterable[str]) -> str:
    total = 0.0
    found = False
    for value in values:
        parsed = _parse_float_percent(value)
        if parsed is not None:
            total += parsed
            found = True
    return f"{total:.2f}" if found else ""


def _parse_time_to_minutes(value: str) -> float | None:
    text = str(value or "").strip()
    if not text or text == "-":
        return None
    if ":" not in text:
        return None
    parts = text.split(":", 1)
    try:
        return int(parts[0]) * 60 + int(parts[1])
    except ValueError:
        return None


def _format_minutes_as_time(minutes: float) -> str:
    total = int(round(minutes))
    return f"{total // 60}:{total % 60:02d}"


def _weighted_time_average(
    data_rows: list[list[str]],
    time_idx: int,
    weight_idx: int,
) -> str:
    result = _weighted_time_average_with_stats(data_rows, time_idx, weight_idx)
    return result.formatted_result


@dataclass(frozen=True)
class WeightedTimeAverageStats:
    formatted_result: str
    valid_rows_used: int
    total_closed_weight: int
    calculated_minutes: float | None


def _is_total_data_row(row: list[str], org_idx: int | None) -> bool:
    if org_idx is None or org_idx >= len(row):
        return False
    return "total" in str(row[org_idx] or "").strip().lower()


def _weighted_time_average_with_stats(
    data_rows: list[list[str]],
    time_idx: int,
    weight_idx: int,
    *,
    org_idx: int | None = None,
) -> WeightedTimeAverageStats:
    total_weight = 0
    weighted_sum = 0.0
    valid_rows_used = 0
    for row in data_rows:
        if _is_total_data_row(row, org_idx):
            continue
        if time_idx >= len(row) or weight_idx >= len(row):
            continue
        weight = _parse_int(row[weight_idx])
        minutes = _parse_time_to_minutes(row[time_idx])
        if weight is not None and weight > 0 and minutes is not None:
            total_weight += weight
            weighted_sum += minutes * weight
            valid_rows_used += 1
    if total_weight <= 0:
        return WeightedTimeAverageStats("", 0, 0, None)
    calculated_minutes = weighted_sum / total_weight
    return WeightedTimeAverageStats(
        _format_minutes_as_time(calculated_minutes),
        valid_rows_used,
        total_weight,
        calculated_minutes,
    )


@dataclass(frozen=True)
class Report1AvgDisposalTimeResult:
    formatted_result: str
    source: str
    valid_rows_used: int
    total_closed_weight: int
    calculated_minutes: float | None


def _portal_avg_disposal_time(total_a: dict[str, str] | None) -> str | None:
    if not total_a:
        return None
    for key in ("Avg. Disposal Time", "Avg Disposal Time", "avg_disposal_time"):
        raw = str(total_a.get(key, "") or "").strip()
        minutes = _parse_time_to_minutes(raw)
        if minutes is not None:
            return _format_minutes_as_time(minutes)
    return None


def fill_report1_avg_disposal_time_total(
    total_row: list[str],
    *,
    source_a_headers: list[str],
    data_rows: list[list[str]],
    total_a: dict[str, str] | None,
) -> Report1AvgDisposalTimeResult:
    """Prefer portal Source A total; else weighted average by Closed."""
    time_idx = _header_index(source_a_headers, "Avg. Disposal Time")
    if time_idx is None:
        return Report1AvgDisposalTimeResult("", "", 0, 0, None)

    portal_value = _portal_avg_disposal_time(total_a)
    if portal_value:
        if time_idx < len(total_row):
            total_row[time_idx] = portal_value
        logger.info(
            "report1_avg_disposal_time_total",
            extra={
                "report1_avg_time_source": "portal_total",
                "valid_rows_used": 0,
                "total_closed_weight": 0,
                "calculated_minutes": _parse_time_to_minutes(portal_value),
                "formatted_result": portal_value,
            },
        )
        return Report1AvgDisposalTimeResult(
            formatted_result=portal_value,
            source="portal_total",
            valid_rows_used=0,
            total_closed_weight=0,
            calculated_minutes=_parse_time_to_minutes(portal_value),
        )

    if time_idx < len(total_row) and not _cell_value_blank(total_row[time_idx]):
        existing = str(total_row[time_idx]).strip()
        logger.info(
            "report1_avg_disposal_time_total",
            extra={
                "report1_avg_time_source": "portal_total",
                "valid_rows_used": 0,
                "total_closed_weight": 0,
                "calculated_minutes": _parse_time_to_minutes(existing),
                "formatted_result": existing,
            },
        )
        return Report1AvgDisposalTimeResult(
            formatted_result=existing,
            source="portal_total",
            valid_rows_used=0,
            total_closed_weight=0,
            calculated_minutes=_parse_time_to_minutes(existing),
        )

    closed_idx = _header_index(source_a_headers, "Closed")
    org_idx = _header_index(source_a_headers, _org_header(source_a_headers))
    if closed_idx is None:
        logger.info("report1_avg_disposal_time_total_unavailable")
        return Report1AvgDisposalTimeResult("", "", 0, 0, None)

    stats = _weighted_time_average_with_stats(
        data_rows,
        time_idx,
        closed_idx,
        org_idx=org_idx,
    )
    if not stats.formatted_result:
        logger.info("report1_avg_disposal_time_total_unavailable")
        return Report1AvgDisposalTimeResult("", "", 0, 0, None)

    if time_idx < len(total_row):
        total_row[time_idx] = stats.formatted_result

    logger.info(
        "report1_avg_disposal_time_total",
        extra={
            "report1_avg_time_source": "weighted_fallback",
            "valid_rows_used": stats.valid_rows_used,
            "total_closed_weight": stats.total_closed_weight,
            "calculated_minutes": stats.calculated_minutes,
            "formatted_result": stats.formatted_result,
        },
    )
    return Report1AvgDisposalTimeResult(
        formatted_result=stats.formatted_result,
        source="weighted_fallback",
        valid_rows_used=stats.valid_rows_used,
        total_closed_weight=stats.total_closed_weight,
        calculated_minutes=stats.calculated_minutes,
    )


def _apply_weighted_averages(
    a_values: list[str],
    source_a_headers: list[str],
    data_rows: list[list[str]],
) -> None:
    weighted_specs = (
        ("Avg. Disposal Time", "Closed"),
        ("Avg. Pendency Time", "Closing Balance"),
        ("Avg. FRT", "Received"),
    )
    for time_header, weight_header in weighted_specs:
        time_idx = _header_index(source_a_headers, time_header)
        weight_idx = _header_index(source_a_headers, weight_header)
        if time_idx is None or weight_idx is None:
            continue
        if not _cell_value_blank(a_values[time_idx]):
            continue
        a_values[time_idx] = _weighted_time_average(data_rows, time_idx, weight_idx)


def _compute_a_aggregates(
    a_values: list[str],
    source_a_headers: list[str],
    *,
    data_rows: list[list[str]] | None = None,
    pct_share_mode: str = "hundred",
) -> None:
    """Compute percentage aggregates from backfilled Source A totals."""
    ob_idx = _header_index(source_a_headers, "Opening Balance")
    rec_idx = _header_index(source_a_headers, "Received")
    closed_idx = _header_index(source_a_headers, "Closed")
    share_idx = _header_index(source_a_headers, "% Share")
    disposal_idx = _header_index(source_a_headers, "% Disposal")

    opening = _get_int_at(a_values, ob_idx) or 0
    received = _get_int_at(a_values, rec_idx)
    closed = _get_int_at(a_values, closed_idx)

    if share_idx is not None and _cell_value_blank(a_values[share_idx]):
        if pct_share_mode == "hundred":
            a_values[share_idx] = "100.00"
        elif pct_share_mode == "sum" and data_rows:
            a_values[share_idx] = _sum_percent_column(
                row[share_idx] for row in data_rows if share_idx < len(row)
            )

    if (
        disposal_idx is not None
        and _cell_value_blank(a_values[disposal_idx])
        and closed is not None
    ):
        denominator = opening + (received or 0)
        if denominator > 0:
            a_values[disposal_idx] = _format_percent(closed, denominator)


def _backfill_summable_b_values(
    b_values: list[str],
    source_b_columns: list[str],
    data_rows: list[list[str]],
    feedback_start: int,
) -> None:
    for offset, column in enumerate(source_b_columns):
        if column not in SUMMABLE_HEADERS:
            continue
        col_idx = feedback_start + offset
        if offset >= len(b_values) or not _cell_value_blank(b_values[offset]):
            continue
        b_values[offset] = _sum_column(
            row[col_idx] for row in data_rows if col_idx < len(row)
        )


def _compute_b_aggregates(
    b_values: list[str],
    source_b_columns: list[str],
    a_values: list[str],
    source_a_headers: list[str],
    *,
    data_rows: list[list[str]] | None = None,
    feedback_start: int = 0,
    pct_feedback_mode: str = "hundred",
) -> None:
    rec_idx = _header_index(source_a_headers, "Received")
    received = _get_int_at(a_values, rec_idx)

    fb_idx = source_b_columns.index("Feedback Received") if "Feedback Received" in source_b_columns else None
    unsat_idx = source_b_columns.index("Unsatisfactory") if "Unsatisfactory" in source_b_columns else None
    pct_fb_idx = source_b_columns.index("% Feedback") if "% Feedback" in source_b_columns else None
    pct_unsat_idx = (
        source_b_columns.index("% Unsatisfactory") if "% Unsatisfactory" in source_b_columns else None
    )

    feedback_received = _get_int_at(b_values, fb_idx) if fb_idx is not None else None
    unsatisfactory = _get_int_at(b_values, unsat_idx) if unsat_idx is not None else None

    if pct_fb_idx is not None and _cell_value_blank(b_values[pct_fb_idx]):
        if pct_feedback_mode == "hundred":
            b_values[pct_fb_idx] = "100.00"
        elif pct_feedback_mode == "sum" and data_rows and pct_fb_idx is not None:
            col_idx = feedback_start + pct_fb_idx
            b_values[pct_fb_idx] = _sum_percent_column(
                row[col_idx] for row in data_rows if col_idx < len(row)
            )
        elif (
            received is not None
            and feedback_received is not None
        ):
            b_values[pct_fb_idx] = _format_percent(feedback_received, received)

    if (
        pct_unsat_idx is not None
        and _cell_value_blank(b_values[pct_unsat_idx])
        and feedback_received is not None
        and feedback_received > 0
        and unsatisfactory is not None
    ):
        b_values[pct_unsat_idx] = _format_percent(unsatisfactory, feedback_received)


def _header_index(headers: list[str], name: str) -> int | None:
    try:
        return headers.index(name)
    except ValueError:
        return None


def _org_header(headers: list[str]) -> str:
    for candidate in ("Organisation", "Division", "Organization"):
        if candidate in headers:
            return candidate
    return "Organisation"


def is_total_output_row(headers: list[str], row: list[str]) -> bool:
    """True when the row's organisation/division label is Total."""
    org_header = _org_header(headers)
    idx = _header_index(headers, org_header)
    if idx is None or idx >= len(row):
        return False
    return "total" in str(row[idx]).strip().lower()


def total_output_row_indices(headers: list[str], rows: list[list[str]]) -> set[int]:
    """Zero-based indices into ``rows`` for total footer rows."""
    return {idx for idx, row in enumerate(rows) if is_total_output_row(headers, row)}


def pdf_table_bold_row_indices(headers: list[str], rows: list[list[str]]) -> frozenset[int]:
    """Table row indices (header is row 0) that should use bold body font."""
    return frozenset(idx + 1 for idx in total_output_row_indices(headers, rows))


def build_merged_total_row(
    *,
    merged_headers: list[str],
    data_rows: list[list[str]],
    source_a_headers: list[str],
    source_b_headers: list[str],
    total_a: dict[str, str] | None,
    total_b: dict[str, str] | None,
    source_b_columns: list[str],
    org_label_a: str,
    org_label_b: str | None = None,
    pct_share_mode: str = "hundred",
    pct_feedback_mode: str = "hundred",
    compute_weighted_averages: bool = False,
) -> list[str]:
    """Build final totals row using source aggregates when present, else safe sums."""
    org_header = _org_header(source_a_headers)
    feedback_org_header = _org_header(source_b_headers) if source_b_headers else "Organisation"
    b_org_label = org_label_b or org_label_a

    if total_a:
        a_values = apply_serial_number(
            source_a_headers,
            [total_a.get(header, "") for header in source_a_headers],
            None,
        )
        org_idx = _header_index(source_a_headers, org_header)
        if org_idx is not None:
            a_values[org_idx] = org_label_a
    else:
        a_values = [""] * len(source_a_headers)
        org_idx = _header_index(source_a_headers, org_header)
        if org_idx is not None:
            a_values[org_idx] = org_label_a
        sno_idx = _header_index(source_a_headers, "S.No.")
        if sno_idx is not None:
            a_values[sno_idx] = ""
        for header in source_a_headers:
            if header in SUMMABLE_HEADERS:
                idx = _header_index(source_a_headers, header)
                if idx is None:
                    continue
                a_values[idx] = _sum_column(row[idx] for row in data_rows)

    feedback_start = len(source_a_headers) + 2

    if total_b:
        b_values = [total_b.get(column, "") for column in source_b_columns]
    else:
        b_values = []
        for offset, column in enumerate(source_b_columns):
            col_idx = feedback_start + offset
            if column in SUMMABLE_HEADERS:
                b_values.append(
                    _sum_column(row[col_idx] for row in data_rows if col_idx < len(row))
                )
            else:
                b_values.append("")

    _backfill_closing_balance(a_values, source_a_headers, data_rows)
    _backfill_summable_a_values(a_values, source_a_headers, data_rows)
    _compute_a_aggregates(
        a_values,
        source_a_headers,
        data_rows=data_rows,
        pct_share_mode=pct_share_mode,
    )
    _backfill_summable_b_values(b_values, source_b_columns, data_rows, feedback_start)
    _compute_b_aggregates(
        b_values,
        source_b_columns,
        a_values,
        source_a_headers,
        data_rows=data_rows,
        feedback_start=feedback_start,
        pct_feedback_mode=pct_feedback_mode,
    )
    if compute_weighted_averages:
        _apply_weighted_averages(a_values, source_a_headers, data_rows)

    feedback_org = (total_b or {}).get(feedback_org_header, b_org_label)
    return a_values + ["", feedback_org] + b_values


def report2_columns_to_copy_from_report1(
    report2_headers: list[str],
    report1_totals: dict[str, str],
) -> list[str]:
    """Column names in Report 2 that should receive Report 1 total values."""
    return [
        header
        for header in report2_headers
        if header in report1_totals and header in REPORT2_TOTALS_FROM_REPORT1_COLUMNS
    ]


def save_report1_output_total_row(
    headers: list[str],
    rows: list[list[str]],
    dest_dir: Path,
) -> Path | None:
    """Persist Report 1 projected total row for Report 2 to consume (by column name)."""
    if not rows or not is_total_output_row(headers, rows[-1]):
        return None
    payload = {
        header: (rows[-1][idx] if idx < len(rows[-1]) else "")
        for idx, header in enumerate(headers)
    }
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / REPORT1_OUTPUT_TOTAL_SIDECAR_FILENAME
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def load_report1_output_total_row(extracted_report1_dir: Path) -> dict[str, str] | None:
    """Load Report 1 total row sidecar written during the same automation run."""
    path = extracted_report1_dir / REPORT1_OUTPUT_TOTAL_SIDECAR_FILENAME
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(payload, dict):
        return None
    return {str(key): str(value) for key, value in payload.items()}


def apply_report1_totals_to_report2_row(
    total_row: list[str],
    report2_headers: list[str],
    report1_totals: dict[str, str],
) -> list[str]:
    """Overlay Report 1 totals onto Report 2 total row for shared column names only."""
    updated = list(total_row)
    copied: list[str] = []
    for header in report2_columns_to_copy_from_report1(report2_headers, report1_totals):
        idx = report2_headers.index(header)
        if idx < len(updated):
            updated[idx] = report1_totals[header]
            copied.append(header)
    if copied:
        logger.info(
            "report2_totals_copied_from_report1",
            extra={"columns_copied": copied},
        )
    return updated


def validate_report2_common_totals_match_report1(
    total_row: list[str],
    report2_headers: list[str],
    report1_totals: dict[str, str],
) -> None:
    """Ensure every shared-column total in Report 2 exactly matches Report 1."""
    mismatches: list[tuple[str, str, str]] = []
    for header in report2_columns_to_copy_from_report1(report2_headers, report1_totals):
        idx = report2_headers.index(header)
        report2_value = str(total_row[idx] if idx < len(total_row) else "").strip()
        report1_value = str(report1_totals.get(header, "")).strip()
        if report2_value != report1_value:
            mismatches.append((header, report1_value, report2_value))
    if mismatches:
        details = ", ".join(
            f"{header} (report1={expected}, report2={actual})"
            for header, expected, actual in mismatches
        )
        raise ValueError(
            f"Report 2 total row does not match Report 1 for shared columns: {details}"
        )


def build_report2_display_total_row(
    *,
    merged_headers: list[str],
    data_rows: list[list[str]],
    source_a_headers: list[str],
    source_b_headers: list[str],
    source_b_columns: list[str],
) -> list[str]:
    """Totals from displayed Top-N rows (Report 1 overlays applied after projection)."""
    return build_merged_total_row(
        merged_headers=merged_headers,
        data_rows=data_rows,
        source_a_headers=source_a_headers,
        source_b_headers=source_b_headers,
        total_a=None,
        total_b=None,
        source_b_columns=source_b_columns,
        org_label_a="Total",
        org_label_b="Total",
        pct_share_mode="sum",
        pct_feedback_mode="sum",
        compute_weighted_averages=True,
    )


def assert_column_order_contains(required_sequence: list[str], headers: list[str]) -> None:
    """Verify headers contain required_sequence in order (ignoring hidden columns)."""
    positions = []
    search_from = 0
    for label in required_sequence:
        try:
            idx = headers.index(label, search_from)
        except ValueError as exc:
            raise AssertionError(f"Expected column {label!r} in headers {headers}") from exc
        positions.append(idx)
        search_from = idx + 1
    if positions != sorted(positions):
        raise AssertionError(f"Columns out of order: {required_sequence}")
