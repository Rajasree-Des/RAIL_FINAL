"""Filter definitions for Report 10-13 (Comprehensive Reports).

Four sections extracting from the same Comprehensive (with drill down) page:
- Report 10 (C&W): Department=Carriage & Wagon, Mode=Train, Type=ALL
- Report 11 (Security): Department=ALL, Mode=ALL, Type=Security-Train
- Report 12 (Punctuality): Department=ALL, Mode=ALL, Type=Punctuality-Train
- Report 13 (Electrical Equipment): Department=ALL, Mode=ALL, Type=Electrical Equipment-Train

Common filters for all: Zone=South Central Railway, Division=ALL, View=Division Wise
"""

from __future__ import annotations

from dataclasses import dataclass

from app.automation.report1_filters import FilterFieldDefinition


@dataclass(frozen=True)
class SectionConfig:
    """Configuration for a single comprehensive report section."""

    section_id: str
    name: str
    section_title: str
    department: str
    mode: str
    complaint_type: str


SECTION_CONFIGS: list[SectionConfig] = [
    SectionConfig(
        section_id="report10_cw",
        name="Report 10 - C&W",
        section_title="C&W complaints division wise (as per comprehensive reports)",
        department="Carriage & Wagon",
        mode="Train",
        complaint_type="ALL",
    ),
    SectionConfig(
        section_id="report11_security",
        name="Report 11 - Security",
        section_title="Security complaints (as per comprehensive drop down)",
        department="ALL",
        mode="ALL",
        complaint_type="Security-Train",
    ),
    SectionConfig(
        section_id="report12_punctuality",
        name="Report 12 - Punctuality",
        section_title="Punctuality complaints (as per comprehensive drop down)",
        department="ALL",
        mode="ALL",
        complaint_type="Punctuality-Train",
    ),
    SectionConfig(
        section_id="report13_electrical",
        name="Report 13 - Electrical Equipment",
        section_title="Electrical Equipment complaints division wise (as per comprehensive reports)",
        department="ALL",
        mode="ALL",
        complaint_type="Electrical Equipment-Train",
    ),
]


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


# Mapping of portal filter values to alternative candidate labels
DEPARTMENT_ALIASES: dict[str, list[str]] = {
    "carriage & wagon": ["Carriage & Wagon", "Carriage And Wagon", "C&W", "CARRIAGE & WAGON", "Carriage&Wagon"],
    "all": ["ALL", "All", "all", "--All--", "-- All --"],
}

TYPE_ALIASES: dict[str, list[str]] = {
    "security-train": [
        "Security- Train",      # Exact portal label (space after hyphen)
        "Security-Train",
        "Security - Train",
        "SECURITY-TRAIN",
        "Security Train",
    ],
    "punctuality-train": [
        "Punctuality- Train",   # Exact portal label (space after hyphen)
        "Punctuality-Train",
        "Punctuality - Train",
        "PUNCTUALITY-TRAIN",
        "Punctuality Train",
    ],
    "electrical equipment-train": [
        "Electrical Equipment- Train",  # Exact portal label (space after hyphen)
        "Electrical Equipment-Train",
        "Electrical Equipment - Train",
        "ELECTRICAL EQUIPMENT-TRAIN",
        "Electrical Equipment Train",
        "Electrical Equip-Train",
    ],
    "all": ["ALL", "All", "all", "--All--", "-- All --"],
}

MODE_ALIASES: dict[str, list[str]] = {
    "train": ["Train", "TRAIN", "train"],
    "all": ["ALL", "All", "all", "--All--", "-- All --"],
}


def get_section_filters(section: SectionConfig) -> list[FilterFieldDefinition]:
    """Build filter definitions for a specific section.

    All sections share common base filters but differ in Department, Mode, and Type.
    Zone is always South Central Railway (SCR), Division is ALL, View is Division Wise.

    IMPORTANT: View must be set BEFORE Department/Mode/Type to prevent cascading
    dropdown resets. The portal resets dependent fields when View changes.
    """
    return [
        _id_select("refundInput", "Excluding Refund Cases", "YES"),
        _id_select("inquiryInput", "Excluding Inquiry Cases", "YES"),
        _id_select("complaintZoneInput", "Zone", "South Central Railway"),
        _id_select("complaintDivInput", "Division", "ALL"),
        _id_select("viewType", "View", "Division Wise"),
        _id_select("complaintSubTypeInput", "Sub Type", "ALL"),
        _id_select("assistanceInput", "Excluding Assistance Cases", "Yes"),
        _id_select("channelTypeInput", "Channel Type", "ALL", required=False),
        _id_select("trainTypeInput", "Train Type", "ALL", required=False),
        _id_select("complaintDeptInput", "Department", section.department),
        _id_select("complaintModeInput", "Mode", section.mode),
        _id_select("complaintTypeInput", "Type", section.complaint_type),
    ]


def get_all_section_configs() -> list[SectionConfig]:
    """Return all section configurations in order."""
    return list(SECTION_CONFIGS)


def get_section_config_by_id(section_id: str) -> SectionConfig | None:
    """Look up a section configuration by its ID."""
    for section in SECTION_CONFIGS:
        if section.section_id == section_id:
            return section
    return None


COMPREHENSIVE_1013_SECTION_IDS: list[str] = [
    "report10_cw",
    "report11_security",
    "report12_punctuality",
    "report13_electrical",
]
