"""Filter definitions for MIS Report 5 (SCR Train Mode Unsatisfactory Feedback)."""

from __future__ import annotations

from app.automation.report1_filters import FilterFieldDefinition


# From Date is set by portal_from_date.apply_previous_from_date (Phase 3).
REPORT_5_FILTERS: list[FilterFieldDefinition] = [
    FilterFieldDefinition(
        name="excluding_refund_cases",
        selector="#refundInput",
        field_type="select",
        value="YES",
        required=False,
        label="Excluding Refund Cases",
    ),
    FilterFieldDefinition(
        name="excluding_inquiry_cases",
        selector="#inquiryInput",
        field_type="select",
        value="Yes",
        required=False,
        label="Excluding Inquiry Cases",
    ),
    FilterFieldDefinition(
        name="zone",
        selector="#complaintZoneInput",
        field_type="select",
        # ALL so Zone Wise table includes an explicit South Central Railway row
        value="ALL",
        required=True,
        label="Zone",
    ),
    FilterFieldDefinition(
        name="division",
        selector="#complaintDivInput",
        field_type="select",
        value="ALL",
        required=False,
        label="Division",
    ),
    FilterFieldDefinition(
        name="department",
        selector="#complaintDeptInput",
        field_type="select",
        value="ALL",
        required=False,
        label="Department",
    ),
    FilterFieldDefinition(
        name="mode",
        selector="#complaintModeInput",
        field_type="select",
        value="Train",
        required=True,
        label="Mode",
    ),
    FilterFieldDefinition(
        name="type",
        selector="#complaintTypeInput",
        field_type="select",
        value="ALL",
        required=False,
        label="Type",
    ),
    FilterFieldDefinition(
        name="sub_type",
        selector="#complaintSubTypeInput",
        field_type="select",
        value="ALL",
        required=False,
        label="Sub Type",
    ),
    FilterFieldDefinition(
        name="view",
        selector="#viewType",
        field_type="select",
        # Live portal option (no spaces around slash)
        value="Zone Wise/ Dept. Wise",
        required=True,
        label="View",
    ),
    FilterFieldDefinition(
        name="excluding_assistance_cases",
        selector="#assistanceInput",
        field_type="select",
        value="Yes",
        required=False,
        label="Excluding Assistance Cases",
    ),
]


def filters_for_report5() -> list[FilterFieldDefinition]:
    """Return the curated filter list for Report 5 SCR Train Mode."""
    return list(REPORT_5_FILTERS)
