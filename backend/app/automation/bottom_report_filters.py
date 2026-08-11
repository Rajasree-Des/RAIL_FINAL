"""Filter definitions and section metadata for Bottom Performed Trains Report."""

from __future__ import annotations

from dataclasses import dataclass

from app.automation.comprehensive1013_filters import (
    SectionConfig,
    get_section_config_by_id,
    get_section_filters,
)
from app.automation.report14_filters import SOURCE_PREVIOUS, ZONE_SCR, VIEW_DIVISION_WISE

BOTTOM_REPORT_SLUG = "bottom-report"
BOTTOM_REPORT_LOG_PREFIX = "[BottomReport]"
BOTTOM_REPORT_FILE_STEM = "Bottom_Performed_Trains_Report"
REPORT_COMPREHENSIVE_TAB = "1) Comprehensive (with drill down)"
REPORT14_TAB_LABEL = "11) Train Watering Complaint"

ZONE_SCR_LABEL = ZONE_SCR
VIEW_DIVISION_WISE_LABEL = VIEW_DIVISION_WISE


@dataclass(frozen=True)
class BottomSectionConfig:
    section_id: str
    display_title: str
    portal_tab: str
    complaint_type: str | None = None
    watering_point: str | None = None
    comprehensive_section_id: str | None = None


BOTTOM_COMPREHENSIVE_SECTIONS: tuple[BottomSectionConfig, ...] = (
    BottomSectionConfig(
        section_id="security",
        display_title="Security",
        portal_tab=REPORT_COMPREHENSIVE_TAB,
        complaint_type="Security-Train",
        comprehensive_section_id="report11_security",
    ),
    BottomSectionConfig(
        section_id="punctuality",
        display_title="Punctuality",
        portal_tab=REPORT_COMPREHENSIVE_TAB,
        complaint_type="Punctuality-Train",
        comprehensive_section_id="report12_punctuality",
    ),
    BottomSectionConfig(
        section_id="electrical_equipment",
        display_title="Electrical Equipment",
        portal_tab=REPORT_COMPREHENSIVE_TAB,
        complaint_type="Electrical Equipment-Train",
        comprehensive_section_id="report13_electrical",
    ),
)

BOTTOM_WATER_SECTION = BottomSectionConfig(
    section_id="water_availability",
    display_title="Water availability",
    portal_tab=REPORT14_TAB_LABEL,
    watering_point=SOURCE_PREVIOUS.watering_point,
)

# Portal generation order (efficiency).
BOTTOM_GENERATION_ORDER: tuple[str, ...] = (
    "security",
    "punctuality",
    "electrical_equipment",
    "water_availability",
)


def get_comprehensive_section_config(section_id: str) -> SectionConfig | None:
    cfg = next((s for s in BOTTOM_COMPREHENSIVE_SECTIONS if s.section_id == section_id), None)
    if cfg is None or not cfg.comprehensive_section_id:
        return None
    return get_section_config_by_id(cfg.comprehensive_section_id)


def filters_for_comprehensive_section(section_id: str):
    section = get_comprehensive_section_config(section_id)
    if section is None:
        raise ValueError(f"Unknown comprehensive bottom section: {section_id}")
    return get_section_filters(section)
