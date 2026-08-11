"""Filter definitions for MIS Report 4 (Cause-wise Top 10 from Zone/Train Type)."""

from __future__ import annotations

from dataclasses import dataclass

from app.automation.report1_filters import FilterFieldDefinition


COMPLAINT_TYPES_ORDERED = [
    "Security",
    "Coach Cleanliness",
    "Bedroll",
    "Water Availability",
    "Electrical Equipment",
    "Catering and Vending Services",
    "Coach Maintenance",
]

# Exact labels from live #complaintTypeInput options
PORTAL_TYPE_MAPPINGS = {
    "Security": "Security- Train",
    "Coach Cleanliness": "Coach - Cleanliness- Train",
    "Bedroll": "Bed Roll- Train",
    "Water Availability": "Water Availability- Train",
    "Electrical Equipment": "Electrical Equipment- Train",
    "Catering and Vending Services": "Catering & Vending Services- Train",
    "Coach Maintenance": "Coach - Maintenance- Train",
}


@dataclass(frozen=True)
class TypeConfig:
    """Configuration for a complaint type in Report 4."""

    name: str
    portal_value: str
    section_title: str


def get_type_configs() -> list[TypeConfig]:
    """Return the ordered list of complaint type configurations."""
    configs = []
    for type_name in COMPLAINT_TYPES_ORDERED:
        portal_value = PORTAL_TYPE_MAPPINGS.get(type_name, type_name)
        section_title = f"Rail Madad 10 trains having maximum {type_name} grievances"
        configs.append(
            TypeConfig(
                name=type_name,
                portal_value=portal_value,
                section_title=section_title,
            )
        )
    return configs


def get_report4_base_filters() -> list[FilterFieldDefinition]:
    """Return the base filter list for Report 4 (without Type set)."""
    # From Date is set by portal_from_date.apply_previous_from_date (Phase 2).
    return [
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


def get_report4_filters_for_type(type_name: str) -> list[FilterFieldDefinition]:
    """Return the filter list for Report 4 with the specified Type."""
    portal_value = PORTAL_TYPE_MAPPINGS.get(type_name, type_name)
    base_filters = get_report4_base_filters()
    type_filter = FilterFieldDefinition(
        name="type",
        selector="#complaintTypeInput",
        field_type="select",
        value=portal_value,
        required=True,
        label="Type",
    )
    return base_filters + [type_filter]


def filters_for_report4() -> list[FilterFieldDefinition]:
    """Return the curated filter list for Report 4 (base without specific Type)."""
    return get_report4_base_filters()
