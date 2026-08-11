"""Namespaced output column catalog and projection for Reports 5 and 6."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

SCR_NAMESPACED_SLUGS = frozenset({"scr-train", "scr-station", "report5", "report6_station"})

SCR_GROUP_TITLES: dict[str, str] = {
    "identifiers": "Identifiers",
    "dates_status": "Dates and Status",
    "complaint_classification": "Complaint Classification",
    "railway_location": "Railway and Location",
    "train_coach": "Train and Coach",
    "feedback_details": "Feedback and Details",
}


@dataclass(frozen=True)
class ScrOutputColumn:
    id: str
    group: str
    label: str
    field: str
    aliases: tuple[str, ...]
    computed: bool = False


def _scr_col(
    prefix: str,
    group: str,
    field_id: str,
    label: str,
    field: str,
    *aliases: str,
    computed: bool = False,
) -> ScrOutputColumn:
    alias_set = (field, label, *aliases)
    return ScrOutputColumn(
        id=f"{prefix}.{field_id}",
        group=group,
        label=label,
        field=field,
        aliases=tuple(dict.fromkeys(alias_set)),
        computed=computed,
    )


def _build_scr_catalog(
    prefix: str,
    *,
    final_status_aliases: tuple[str, ...] = ("finalStatus",),
    avg_cliff_aliases: tuple[str, ...] = ("avgCliff", "avgcDiff"),
) -> tuple[ScrOutputColumn, ...]:
    return (
        _scr_col(prefix, "identifiers", "sno", "S.No.", "serialNo", computed=True),
        _scr_col(
            prefix,
            "identifiers",
            "complaint_ref_no",
            "Complaint Ref Number",
            "complaintRefNo",
            "Ref. No.",
            "Reference Number",
        ),
        _scr_col(prefix, "identifiers", "pnr_uts_no", "PNR/UTS No.", "pnrUtsNo"),
        _scr_col(prefix, "identifiers", "contact_id", "Contact ID", "contactId"),
        _scr_col(prefix, "identifiers", "user_id", "User ID", "userId"),
        _scr_col(prefix, "identifiers", "user_mobile", "User Mobile", "userMobile"),
        _scr_col(
            prefix,
            "dates_status",
            "created_on",
            "Created On",
            "createdOn",
            "Registration Date",
            "Complaint Date",
        ),
        _scr_col(prefix, "dates_status", "modified_on", "Modified On", "modifiedOn", "Closing Date"),
        _scr_col(
            prefix,
            "dates_status",
            "final_status",
            "Final Status",
            "finalStatus",
            *final_status_aliases,
        ),
        _scr_col(prefix, "dates_status", "status", "Status", "status"),
        _scr_col(
            prefix,
            "dates_status",
            "avg_cliff",
            "Avg. Diff",
            "avgCliff",
            *avg_cliff_aliases,
        ),
        _scr_col(
            prefix,
            "complaint_classification",
            "complaint_mode",
            "Complaint Mode",
            "complaintMode",
            "mode",
            "Mode",
        ),
        _scr_col(prefix, "complaint_classification", "channel_type", "Channel Type", "channelType", "Channel"),
        _scr_col(
            prefix,
            "complaint_classification",
            "comp_type_name",
            "Comp Type Name",
            "complaintTypeName",
            "Type",
        ),
        _scr_col(
            prefix,
            "complaint_classification",
            "sub_type_name",
            "Sub Type Name",
            "subTypeName",
            "Sub Type",
        ),
        _scr_col(prefix, "complaint_classification", "commodity", "Commodity", "commodity"),
        _scr_col(prefix, "complaint_classification", "forwarded", "Forwarded", "forwarded"),
        _scr_col(prefix, "railway_location", "train_station", "Train/Station", "trainStation"),
        _scr_col(prefix, "railway_location", "primary_depot", "Primary Depot", "primaryDepot"),
        _scr_col(prefix, "railway_location", "zone_code", "Zone Code", "zoneCode", "Zone"),
        _scr_col(prefix, "railway_location", "div_code", "Div Code", "divCode", "Div"),
        _scr_col(prefix, "railway_location", "own_zone_code", "Owning Zone Code", "ownZoneCode", "Owning Zone"),
        _scr_col(prefix, "railway_location", "own_div_code", "Owning Division Code", "ownDivCode", "Owning Div"),
        _scr_col(
            prefix,
            "railway_location",
            "dept_code",
            "Department Code",
            "deptCode",
            "department",
            "Dept",
        ),
        _scr_col(prefix, "railway_location", "next_station", "Next Station", "nextStation"),
        _scr_col(prefix, "train_coach", "coach_type", "Coach Type", "coachType"),
        _scr_col(prefix, "train_coach", "physical_coach_no", "Physical Coach No.", "physicalCoachNo"),
        _scr_col(
            prefix,
            "train_coach",
            "train_name_for_report",
            "Train Name For Report",
            "trainNameForReport",
            "trainNameForReport/Station Name",
        ),
        _scr_col(
            prefix,
            "train_coach",
            "coach_owning_railway",
            "Coach Owning Railway",
            "coachOwningRailway",
        ),
        _scr_col(prefix, "feedback_details", "rating", "Rating", "rating"),
        _scr_col(prefix, "feedback_details", "feedback_remark", "Feedback Remark", "feedbackRemark"),
        _scr_col(prefix, "feedback_details", "complaint_desc", "Complaint Description", "complaintDesc"),
        _scr_col(prefix, "feedback_details", "remarks", "Remarks", "remarks"),
    )


REPORT5_SCR_COLUMNS: tuple[ScrOutputColumn, ...] = _build_scr_catalog(
    "scr-train",
    final_status_aliases=("status",),
    avg_cliff_aliases=("diff", "Disposal Time"),
)
REPORT6_SCR_COLUMNS: tuple[ScrOutputColumn, ...] = _build_scr_catalog("scr-station")

REPORT5_SCR_IDS: frozenset[str] = frozenset(c.id for c in REPORT5_SCR_COLUMNS)
REPORT6_SCR_IDS: frozenset[str] = frozenset(c.id for c in REPORT6_SCR_COLUMNS)

REPORT5_DEFAULT_SCR_IDS: list[str] = [
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

REPORT6_DEFAULT_SCR_IDS: list[str] = [
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

# Legacy flat keys (pre-namespaced) and camelCase → namespaced ID
SCR_LEGACY_TO_NAMESPACED: dict[str, dict[str, str]] = {
    "scr-train": {
        "serialNo": "scr-train.sno",
        "complaintRefNo": "scr-train.complaint_ref_no",
        "createdOn": "scr-train.created_on",
        "modifiedOn": "scr-train.modified_on",
        "finalStatus": "scr-train.final_status",
        "status": "scr-train.status",
        "avgCliff": "scr-train.avg_cliff",
        "diff": "scr-train.avg_cliff",
        "complaintMode": "scr-train.complaint_mode",
        "mode": "scr-train.complaint_mode",
        "trainStation": "scr-train.train_station",
        "primaryDepot": "scr-train.primary_depot",
        "channelType": "scr-train.channel_type",
        "complaintTypeName": "scr-train.comp_type_name",
        "subTypeName": "scr-train.sub_type_name",
        "zoneCode": "scr-train.zone_code",
        "divCode": "scr-train.div_code",
        "ownZoneCode": "scr-train.own_zone_code",
        "ownDivCode": "scr-train.own_div_code",
        "deptCode": "scr-train.dept_code",
        "department": "scr-train.dept_code",
        "rating": "scr-train.rating",
        "commodity": "scr-train.commodity",
        "forwarded": "scr-train.forwarded",
        "pnrUtsNo": "scr-train.pnr_uts_no",
        "coachType": "scr-train.coach_type",
        "physicalCoachNo": "scr-train.physical_coach_no",
        "feedbackRemark": "scr-train.feedback_remark",
        "nextStation": "scr-train.next_station",
        "contactId": "scr-train.contact_id",
        "trainNameForReport": "scr-train.train_name_for_report",
        "complaintDesc": "scr-train.complaint_desc",
        "remarks": "scr-train.remarks",
        "userId": "scr-train.user_id",
        "userMobile": "scr-train.user_mobile",
        "coachOwningRailway": "scr-train.coach_owning_railway",
    },
    "scr-station": {
        "serialNo": "scr-station.sno",
        "complaintRefNo": "scr-station.complaint_ref_no",
        "createdOn": "scr-station.created_on",
        "modifiedOn": "scr-station.modified_on",
        "finalStatus": "scr-station.final_status",
        "status": "scr-station.status",
        "avgCliff": "scr-station.avg_cliff",
        "complaintMode": "scr-station.complaint_mode",
        "mode": "scr-station.complaint_mode",
        "trainStation": "scr-station.train_station",
        "primaryDepot": "scr-station.primary_depot",
        "channelType": "scr-station.channel_type",
        "complaintTypeName": "scr-station.comp_type_name",
        "subTypeName": "scr-station.sub_type_name",
        "zoneCode": "scr-station.zone_code",
        "divCode": "scr-station.div_code",
        "ownZoneCode": "scr-station.own_zone_code",
        "ownDivCode": "scr-station.own_div_code",
        "deptCode": "scr-station.dept_code",
        "department": "scr-station.dept_code",
        "rating": "scr-station.rating",
        "commodity": "scr-station.commodity",
        "forwarded": "scr-station.forwarded",
        "pnrUtsNo": "scr-station.pnr_uts_no",
        "coachType": "scr-station.coach_type",
        "physicalCoachNo": "scr-station.physical_coach_no",
        "feedbackRemark": "scr-station.feedback_remark",
        "nextStation": "scr-station.next_station",
        "contactId": "scr-station.contact_id",
        "trainNameForReport": "scr-station.train_name_for_report",
        "complaintDesc": "scr-station.complaint_desc",
        "remarks": "scr-station.remarks",
        "userId": "scr-station.user_id",
        "userMobile": "scr-station.user_mobile",
        "coachOwningRailway": "scr-station.coach_owning_railway",
    },
}


def scr_catalog_for_slug(report_slug: str) -> tuple[ScrOutputColumn, ...]:
    from app.automation.report_keys import canonicalize_report_key

    slug = canonicalize_report_key(report_slug)
    if slug in {"scr-station", "report6_station"}:
        return REPORT6_SCR_COLUMNS
    return REPORT5_SCR_COLUMNS


def scr_default_ids(report_slug: str) -> list[str]:
    from app.automation.report_keys import canonicalize_report_key

    slug = canonicalize_report_key(report_slug)
    if slug in {"scr-station", "report6_station"}:
        return list(REPORT6_DEFAULT_SCR_IDS)
    return list(REPORT5_DEFAULT_SCR_IDS)


def scr_allowed_ids(report_slug: str) -> frozenset[str]:
    from app.automation.report_keys import canonicalize_report_key

    slug = canonicalize_report_key(report_slug)
    if slug in {"scr-station", "report6_station"}:
        return REPORT6_SCR_IDS
    return REPORT5_SCR_IDS


def migrate_scr_to_namespaced_ids(report_slug: str, selected: Iterable[str]) -> list[str]:
    from app.automation.report_keys import canonicalize_report_key

    slug = canonicalize_report_key(report_slug)
    if slug in {"scr-station", "report6_station"}:
        mapping = SCR_LEGACY_TO_NAMESPACED["scr-station"]
        allowed = REPORT6_SCR_IDS
        prefix = "scr-station"
    else:
        mapping = SCR_LEGACY_TO_NAMESPACED["scr-train"]
        allowed = REPORT5_SCR_IDS
        prefix = "scr-train"

    migrated: list[str] = []
    seen: set[str] = set()
    for raw in selected:
        text = str(raw or "").strip()
        if not text:
            continue
        if text.startswith(f"{prefix}."):
            key = text
        else:
            key = mapping.get(text, text)
        if key in allowed and key not in seen:
            migrated.append(key)
            seen.add(key)
    return migrated


def scr_labels(selected_ids: Iterable[str], report_slug: str) -> list[str]:
    catalog = {col.id: col for col in scr_catalog_for_slug(report_slug)}
    return [catalog[col_id].label for col_id in selected_ids if col_id in catalog]


def resolve_scr_row_value(row: dict[str, str], column: ScrOutputColumn) -> str:
    for alias in column.aliases:
        value = row.get(alias)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return ""


def validate_selected_scr_fields(
    rows: list[dict[str, str]],
    selected_ids: list[str],
    report_slug: str,
) -> list[str]:
    """Return selected field IDs whose canonical source column is absent from the dataset."""
    if not rows:
        return []
    catalog = {col.id: col for col in scr_catalog_for_slug(report_slug)}
    header_keys: set[str] = set()
    for row in rows:
        header_keys.update(row.keys())
    unavailable: list[str] = []
    for col_id in selected_ids:
        column = catalog.get(col_id)
        if column is None or column.computed:
            continue
        if not any(alias in header_keys for alias in column.aliases):
            unavailable.append(col_id)
    return unavailable


def project_scr_dict_rows(
    rows: list[dict[str, str]],
    selected_ids: Iterable[str],
    report_slug: str,
) -> tuple[list[str], list[list[str]]]:
    catalog = {col.id: col for col in scr_catalog_for_slug(report_slug)}
    key_list = list(selected_ids)
    out_headers: list[str] = []
    columns: list[ScrOutputColumn] = []
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
                values.append(resolve_scr_row_value(row, column))
        out_rows.append(values)
    return out_headers, out_rows


def scr_catalog_entries(report_slug: str) -> list[dict[str, object]]:
    defaults = set(scr_default_ids(report_slug))
    return [
        {
            "id": column.id,
            "label": column.label,
            "group": column.group,
            "group_title": SCR_GROUP_TITLES.get(column.group, column.group),
            "required": False,
            "default_visible": column.id in defaults,
        }
        for column in scr_catalog_for_slug(report_slug)
    ]
