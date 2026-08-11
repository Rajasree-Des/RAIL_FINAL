"""Filter definitions for MIS Report 2 (Division Wise Top 25).

Uses ID-based selectors as primary with label-based fallbacks for robustness.
Field IDs discovered from portal: #refundInput, #inquiryInput, #assistanceInput,
#viewType, #complaintZoneInput, #complaintDivInput, #complaintDeptInput,
#complaintModeInput, #complaintTypeInput, #complaintSubTypeInput.
"""

from __future__ import annotations

from app.automation.report1_filters import FilterFieldDefinition


def _id_select(
    element_id: str,
    label: str,
    value: str,
    *,
    required: bool = True,
) -> FilterFieldDefinition:
    """Build a select filter with ID-based selector as primary, label fallback.

    Uses explicit element ID first (most reliable), then attribute patterns,
    then label-based selectors as fallback for robustness.
    """
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


REPORT_2_FILTERS: list[FilterFieldDefinition] = [
    _id_select("refundInput", "Excluding Refund Cases", "YES"),
    _id_select("inquiryInput", "Excluding Inquiry Cases", "YES"),
    _id_select("complaintZoneInput", "Zone", "ALL"),
    _id_select("complaintDivInput", "Division", "ALL"),
    _id_select("complaintDeptInput", "Department", "ALL"),
    _id_select("complaintModeInput", "Mode", "ALL"),
    _id_select("complaintTypeInput", "Type", "ALL"),
    _id_select("complaintSubTypeInput", "Sub Type", "ALL"),
    _id_select("viewType", "View", "Division Wise"),
    _id_select("assistanceInput", "Excluding Assistance Cases", "Yes"),
    _id_select("channelTypeInput", "Channel Type", "ALL", required=False),
    _id_select("trainTypeInput", "Train Type", "ALL", required=False),
]


REPORT_2_FEEDBACK_FILTERS: list[FilterFieldDefinition] = [
    _id_select("refundInput", "Excluding Refund Cases", "YES"),
    _id_select("inquiryInput", "Excluding Inquiry Cases", "YES"),
    _id_select("complaintZoneInput", "Zone", "ALL"),
    _id_select("complaintDivInput", "Division", "ALL"),
    _id_select("complaintDeptInput", "Department", "ALL"),
    _id_select("complaintModeInput", "Mode", "ALL"),
    _id_select("complaintTypeInput", "Type", "ALL"),
    _id_select("complaintSubTypeInput", "Sub Type", "ALL"),
    _id_select("viewType", "View", "Division Wise"),
    _id_select("assistanceInput", "Excluding Assistance Cases", "Yes"),
]


def filters_for_report2() -> list[FilterFieldDefinition]:
    """Return the curated filter list for Report 2 Comprehensive Division Wise."""
    return list(REPORT_2_FILTERS)


def filters_for_report2_feedback() -> list[FilterFieldDefinition]:
    """Return the curated filter list for Report 2 Feedback Division Wise."""
    return list(REPORT_2_FEEDBACK_FILTERS)
