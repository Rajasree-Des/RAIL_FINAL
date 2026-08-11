"""Filter definitions for MIS Report 3 (Top 20 Trains from Zone/Train Type Tab)."""

from __future__ import annotations

from app.automation.report1_filters import FilterFieldDefinition, _label_select


# From Date is set by portal_from_date.apply_previous_from_date (Phase 2).
REPORT_3_FILTERS: list[FilterFieldDefinition] = [
    FilterFieldDefinition(
        name="zone",
        selector="#complaintZoneInput",
        field_type="select",
        value="ALL",
        required=False,
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
        name="department",
        selector="#complaintDeptInput",
        field_type="select",
        value="ALL",
        required=False,
        label="Department",
    ),
    FilterFieldDefinition(
        name="view",
        selector="#viewType",
        field_type="select",
        # Live portal option text (no period): "Train No Wise"
        value="Train No Wise",
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
    # Coach Type (#coachId) is a multi-select; leave portal default (none selected).
]


def filters_for_report3() -> list[FilterFieldDefinition]:
    """Return the curated filter list for Report 3 Zone/Train Type Train No. Wise."""
    return list(REPORT_3_FILTERS)
