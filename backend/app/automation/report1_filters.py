"""Curated filter definitions for MIS Report 1 (refine after live discovery)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal


FilterFieldType = Literal["text", "date", "select", "radio", "checkbox"]


@dataclass(frozen=True)
class FilterFieldDefinition:
    """Describes a single report filter field to populate."""

    name: str
    selector: str
    field_type: FilterFieldType
    value: str
    required: bool = True
    label: str = ""


def resolve_filter_value(value_key: str, date_format: str = "%d/%m/%Y") -> str:
    """Resolve symbolic filter values such as 'today'."""
    if value_key == "today":
        return datetime.now().strftime(date_format)
    if value_key == "today_iso":
        return datetime.now().strftime("%Y-%m-%d")
    # Alias kept for compatibility; Date Range must always be Previous Day.
    if value_key in {"today_range", "previous_day_range"}:
        return "Previous Day"
    return value_key


def resolve_field_value(field: FilterFieldDefinition, date_format: str = "%d/%m/%Y") -> str:
    return resolve_filter_value(field.value, date_format=date_format)


def _infer_field_type(discovered: dict[str, Any]) -> FilterFieldType:
    tag = str(discovered.get("tag", "")).lower()
    input_type = str(discovered.get("field_type") or discovered.get("type") or "").lower()
    if tag == "select":
        return "select"
    if tag == "textarea":
        return "text"
    if input_type == "checkbox":
        return "checkbox"
    if input_type == "radio":
        return "radio"
    if input_type == "date" or "date" in str(discovered.get("field_name", "")).lower():
        return "date"
    return "text"


def normalize_discovered_field(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize discovery output to stable field keys."""
    field_id = raw.get("field_id") or raw.get("id") or ""
    field_name = raw.get("field_name") or raw.get("name") or ""
    field_type = raw.get("field_type") or raw.get("type") or raw.get("tag") or ""
    field_label = raw.get("field_label") or raw.get("label") or ""
    selector = raw.get("selector") or (f"#{field_id}" if field_id else "")
    if not selector and field_name:
        selector = f"[name='{field_name}']"
    current_value = raw.get("current_value")
    if current_value is None:
        current_value = raw.get("value") or ""
    return {
        "tag": raw.get("tag", ""),
        "field_id": field_id,
        "field_name": field_name,
        "field_type": field_type,
        "field_label": field_label,
        "selector": selector,
        "current_value": current_value,
        "required": bool(raw.get("required", False)),
        "options": raw.get("options") or [],
    }


def build_filters_from_discovery(
    discovered: list[dict[str, Any]],
    slug: str = "report1",
) -> list[FilterFieldDefinition]:
    """Build filter definitions from live discovery, with date/today defaults."""
    from app.automation.report_keys import canonicalize_report_key

    # Feedback Tab 6 for Report 1 dual-source is still slug "report6"
    if slug == "report6":
        return list(REPORT_6_FILTERS)

    key = canonicalize_report_key(slug)
    if key == "division":
        from app.automation.report2_filters import REPORT_2_FILTERS
        return list(REPORT_2_FILTERS)
    if key == "train-no":
        from app.automation.report3_filters import REPORT_3_FILTERS
        return list(REPORT_3_FILTERS)
    if key == "types":
        from app.automation.report4_filters import get_report4_base_filters
        return list(get_report4_base_filters())
    if key == "scr-train":
        from app.automation.report5_filters import REPORT_5_FILTERS
        return list(REPORT_5_FILTERS)
    if key == "scr-station":
        from app.automation.report6_scr_filters import REPORT_6_SCR_FILTERS
        return list(REPORT_6_SCR_FILTERS)
    if key != "report1":
        return []

    normalized = [normalize_discovered_field(field) for field in discovered]
    filters: list[FilterFieldDefinition] = []
    seen: set[str] = set()

    for field in normalized:
        tag = str(field.get("tag", "")).lower()
        if tag == "button" or not field.get("selector"):
            continue

        field_id = str(field.get("field_id") or "")
        field_label = str(field.get("field_label") or "").strip()
        field_name = str(field.get("field_name") or field_id or "").strip()
        label_lower = field_label.lower()
        name_lower = field_name.lower()
        logical_name = field_name or field_id or field_label.replace(" ", "_").lower()
        if not logical_name or logical_name in seen:
            continue
        seen.add(logical_name)

        field_type = _infer_field_type(field)
        selector = str(field["selector"])
        current_value = str(field.get("current_value") or "")

        if field_id == "dateRange" or (field_type == "select" and "date range" in label_lower):
            continue
        elif field_type in ("text", "date") and any(
            token in label_lower or token in name_lower
            for token in ("from date", "fromdate", "frmdate", "from_date")
        ):
            continue
        elif field_type in ("text", "date") and any(
            token in label_lower or token in name_lower
            for token in ("to date", "todate", "to_date")
        ):
            continue
        elif field.get("required"):
            value = current_value
            required = True
            if not value:
                continue
        else:
            continue

        filters.append(
            FilterFieldDefinition(
                name=logical_name,
                selector=selector,
                field_type=field_type,
                value=value,
                required=required,
                label=field_label,
            )
        )

    return filters if filters else list(REPORT_1_FILTERS)


def _looks_like_iso_date(value: str) -> bool:
    """Return True for date strings shaped like YYYY-MM-DD."""
    if len(value) != 10:
        return False
    return value[4] == "-" and value[7] == "-"


def _id_select(
    element_id: str,
    label: str,
    value: str,
    *,
    required: bool = True,
) -> FilterFieldDefinition:
    """Build a select filter with ID-based selector as primary, label fallback."""
    name = label.lower().replace(" ", "_").replace("/", "_").replace(".", "")
    label_no_spaces = label.replace(" ", "")
    return FilterFieldDefinition(
        name=name,
        selector=(
            f"#{element_id}, "
            f"select[id='{element_id}'], "
            f"select[name='{element_id}'], "
            f"select[id*='{element_id.replace('Input', '')}'], "
            f"tr:has(td:has-text('{label}')) select, "
            f"tr:has(th:has-text('{label}')) select, "
            f"td:has-text('{label}') + td select, "
            f"label:has-text('{label}') + select, "
            f"select[name*='{label_no_spaces}'], "
            f"select[id*='{label_no_spaces}']"
        ),
        field_type="select",
        value=value,
        required=required,
        label=label,
    )


# Report 1 renders filters on the main admin page (not an iframe).
# From/To Date are handled by portal_from_date.apply_previous_from_date (Phase 1).
REPORT_1_FILTERS: list[FilterFieldDefinition] = [
    _id_select("refundInput", "Excluding Refund Cases", "YES"),
    _id_select("inquiryInput", "Excluding Inquiry Cases", "YES"),
    _id_select("complaintZoneInput", "Zone", "ALL"),
    _id_select("complaintDivInput", "Division", "ALL"),
    _id_select("complaintDeptInput", "Department", "ALL"),
    _id_select("complaintModeInput", "Mode", "ALL"),
    _id_select("complaintTypeInput", "Type", "ALL"),
    _id_select("complaintSubTypeInput", "Sub Type", "ALL"),
    _id_select("viewType", "View", "Zone Wise"),
    _id_select("assistanceInput", "Excluding Assistance Cases", "Yes"),
    _id_select("channelTypeInput", "Channel Type", "ALL", required=False),
    _id_select("trainTypeInput", "Train Type", "ALL", required=False),
]


def _label_select(label: str, value: str, *, required: bool = True) -> FilterFieldDefinition:
    """Build a select filter resolved primarily by visible label text."""
    return FilterFieldDefinition(
        name=label.lower().replace(" ", "_").replace("/", "_").replace(".", ""),
        selector=(
            f"tr:has(td:text-is('{label}')) select, "
            f"tr:has(th:text-is('{label}')) select, "
            f"td:text-is('{label}') + td select, "
            f"label:text-is('{label}') + select, "
            f"tr:has(td:has-text('{label}')) select, "
            f"tr:has(th:has-text('{label}')) select, "
            f"td:has-text('{label}') + td select, "
            f"label:has-text('{label}') + select, "
            f"select[name*='{label.replace(' ', '')}'], "
            f"select[id*='{label.replace(' ', '')}']"
        ),
        field_type="select",
        value=value,
        required=required,
        label=label,
    )


# Feedback (Report 6) filters per automation spec.
# From Date is set by portal_from_date.apply_previous_from_date before Submit.
REPORT_6_FILTERS: list[FilterFieldDefinition] = [
    _label_select("Excluding Refund Cases", "YES"),
    _label_select("Excluding Inquiry Cases", "YES"),
    _label_select("Zone", "ALL"),
    _label_select("Division", "ALL"),
    _label_select("Department", "ALL"),
    _label_select("Mode", "ALL"),
    _label_select("Type", "ALL"),
    _label_select("Sub Type", "ALL"),
    _label_select("View", "Zone Wise / Dept. Wise"),
    _label_select("Excluding Assistance Cases", "Yes"),
]


def filters_for_report(slug: str = "report1") -> list[FilterFieldDefinition]:
    from app.automation.report_keys import canonicalize_report_key

    if slug == "report6":
        return list(REPORT_6_FILTERS)

    key = canonicalize_report_key(slug)
    if key == "report1":
        return list(REPORT_1_FILTERS)
    if key == "division":
        from app.automation.report2_filters import REPORT_2_FILTERS
        return list(REPORT_2_FILTERS)
    if key == "train-no":
        from app.automation.report3_filters import REPORT_3_FILTERS
        return list(REPORT_3_FILTERS)
    if key == "types":
        from app.automation.report4_filters import get_report4_base_filters
        return list(get_report4_base_filters())
    if key == "scr-train":
        from app.automation.report5_filters import REPORT_5_FILTERS
        return list(REPORT_5_FILTERS)
    if key == "scr-station":
        from app.automation.report6_scr_filters import REPORT_6_SCR_FILTERS
        return list(REPORT_6_SCR_FILTERS)
    return []


def applied_filter_records(
    fields: list[FilterFieldDefinition],
    values: dict[str, str],
) -> list[dict[str, Any]]:
    return [
        {
            "name": field.name,
            "value": values.get(field.name, ""),
            "label": field.label or field.name,
        }
        for field in fields
    ]
