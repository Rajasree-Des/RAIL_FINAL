"""Filter definitions and section metadata for Report 9 (Mode Wise Cause Wise)."""

from __future__ import annotations

from dataclasses import dataclass

from app.automation.report1_filters import FilterFieldDefinition

REPORT9_TAB_LABEL = "7) Mode Wise Cause Wise"
REPORT9_PAGE_PATH = "/mis_reports/report7"
REPORT9_URL_FRAGMENT = "mis_reports/report7"

ZONE_ALL = "ALL"
ZONE_SCR = "South Central Railway"

# Portal tables expose Cause + Received; S.No. and % Share are derived in the processor.
REPORT9_REQUIRED_HEADERS = frozenset({"Cause", "Received"})

OUTPUT_HEADERS = ["S.No.", "Cause", "Received", "% Share"]


@dataclass(frozen=True)
class Report9SourceConfig:
    """One of the four Report 9 extraction sources."""

    source_id: str
    zone: str
    heading_match: tuple[str, ...]
    table_ids: tuple[str, ...]
    section_title: str
    missing_error: str
    filename: str


SOURCE_A_TRAIN = Report9SourceConfig(
    source_id="all_zone_train",
    zone=ZONE_ALL,
    heading_match=(
        "train complaints cause wise",
        "7.1) train",
        "rail madad train cause wise grievances",
    ),
    table_ids=("tabled1",),
    section_title="Rail Madad Train Cause Wise Grievances",
    missing_error="REPORT9_ALL_TRAIN_TABLE_MISSING",
    filename="all_zone_train.csv",
)

SOURCE_A_STATION = Report9SourceConfig(
    source_id="all_zone_station",
    zone=ZONE_ALL,
    heading_match=(
        "station complaints cause wise",
        "7.2) station",
        "rail madad station cause wise grievances",
    ),
    table_ids=("tabled2",),
    section_title="Rail Madad Station Cause Wise Grievances",
    missing_error="REPORT9_ALL_STATION_TABLE_MISSING",
    filename="all_zone_station.csv",
)

SOURCE_B_TRAIN = Report9SourceConfig(
    source_id="scr_train",
    zone=ZONE_SCR,
    heading_match=(
        "train complaints cause wise",
        "7.1) train",
        "rail madad scr train cause wise grievances",
    ),
    table_ids=("tabled1",),
    section_title="Rail Madad SCR Train Cause Wise Grievances",
    missing_error="REPORT9_SCR_TRAIN_TABLE_MISSING",
    filename="scr_train.csv",
)

SOURCE_B_STATION = Report9SourceConfig(
    source_id="scr_station",
    zone=ZONE_SCR,
    heading_match=(
        "station complaints cause wise",
        "7.2) station",
        "rail madad scr station cause wise grievances",
    ),
    table_ids=("tabled2",),
    section_title="Rail Madad SCR Station Cause Wise Grievances",
    missing_error="REPORT9_SCR_STATION_TABLE_MISSING",
    filename="scr_station.csv",
)

SOURCE_A_CONFIGS = (SOURCE_A_TRAIN, SOURCE_A_STATION)
SOURCE_B_CONFIGS = (SOURCE_B_TRAIN, SOURCE_B_STATION)
ALL_SOURCE_CONFIGS = SOURCE_A_CONFIGS + SOURCE_B_CONFIGS

SECTION_ORDER = (
    SOURCE_A_TRAIN,
    SOURCE_A_STATION,
    SOURCE_B_TRAIN,
    SOURCE_B_STATION,
)

REPORT_9_ZONE_ALL_FILTERS: list[FilterFieldDefinition] = [
    FilterFieldDefinition(
        name="zone",
        selector="#complaintZoneInput",
        field_type="select",
        value=ZONE_ALL,
        required=True,
        label="Zone",
    ),
]

REPORT_9_ZONE_SCR_FILTERS: list[FilterFieldDefinition] = [
    FilterFieldDefinition(
        name="zone",
        selector="#complaintZoneInput",
        field_type="select",
        value=ZONE_SCR,
        required=True,
        label="Zone",
    ),
]


def filters_for_zone(zone: str) -> list[FilterFieldDefinition]:
    if zone == ZONE_SCR:
        return list(REPORT_9_ZONE_SCR_FILTERS)
    return list(REPORT_9_ZONE_ALL_FILTERS)
