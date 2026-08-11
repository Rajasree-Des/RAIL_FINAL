"""Filter definitions for Report 14 (Train Watering Complaints).

Portal tab 11) Train Watering Complaints — dual extract:
- Source A: Previous Watering Point
- Source B: Upcoming Watering Point
Common: Zone=South Central Railway, View=Division Wise when available.

Previous/Upcoming may live on the View select, a dedicated watering select,
or radio/button controls — the handler resolves the control dynamically.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.automation.report1_filters import FilterFieldDefinition

REPORT14_TAB_LABEL = "11) Train Watering Complaints"
# Report 14 always opens portal tab 11 (Train Watering), never Inquiry Wise 2 / tab 14.
# page path is post-menu identity only; handler never URL-goto for form load.
REPORT14_PAGE_PATH = "/mis_reports/report22"
REPORT14_URL_FRAGMENT = "mis_reports/report22"

ZONE_SCR = "South Central Railway"
VIEW_DIVISION_WISE = "Division Wise"

SOURCE_PREVIOUS_LABEL = "Previous Watering Point"
SOURCE_UPCOMING_LABEL = "Upcoming Watering Point"

# Labels that must be verified on the form before Submit.
CORE_FILTER_NAMES = ("zone", "view", "output")

# Portal tables typically expose station/division + complaint metrics.
REPORT14_REQUIRED_HEADERS = frozenset({"Received"})

METRIC_COLUMNS = (
    "Opening Balance",
    "Received",
    "% Share",
    "Closed",
    "Closing Balance",
    "% Disposal",
)

# Side-by-side merged output (processor) — Division-keyed horizontal merge.
OUTPUT_HEADERS = [
    "S.No.",
    "Division",
    "Previous Received",
    "Previous % Share",
    "Previous Average Rating",
    "Upcoming Received",
    "Upcoming % Share",
    "Upcoming Average Rating",
]


@dataclass(frozen=True)
class Report14SourceConfig:
    """One of the two Report 14 watering sources."""

    source_id: str
    section_title: str
    watering_point: str
    missing_error: str
    filename: str
    column_prefix: str
    option_aliases: tuple[str, ...]


SOURCE_PREVIOUS = Report14SourceConfig(
    source_id="previous_watering",
    section_title="Previous Watering Point",
    watering_point=SOURCE_PREVIOUS_LABEL,
    missing_error="REPORT14_PREVIOUS_TABLE_MISSING",
    filename="previous_watering.csv",
    column_prefix="Prev",
    option_aliases=(
        "Previous Watering Point",
        "Previous Watering",
        "Previous watering point",
        "PREVIOUS WATERING POINT",
        "Previous",
        "previous watering point",
        "WP - Previous",
        "Watering Point - Previous",
    ),
)

SOURCE_UPCOMING = Report14SourceConfig(
    source_id="upcoming_watering",
    section_title="Upcoming Watering Point",
    watering_point=SOURCE_UPCOMING_LABEL,
    missing_error="REPORT14_UPCOMING_TABLE_MISSING",
    filename="upcoming_watering.csv",
    column_prefix="Up",
    option_aliases=(
        "Upcoming Watering Point",
        "Upcoming Watering",
        "Upcoming watering point",
        "UPCOMING WATERING POINT",
        "Upcoming",
        "Next Watering Point",
        "Next Watering",
        "upcoming watering point",
        "WP - Upcoming",
        "Watering Point - Upcoming",
    ),
)

SECTION_ORDER = (SOURCE_PREVIOUS, SOURCE_UPCOMING)
ALL_SOURCE_CONFIGS = SECTION_ORDER


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


def base_filters() -> list[FilterFieldDefinition]:
    """Shared core filters for Report 14 (Train Watering form controls only)."""
    return [
        # Prefer ID-only selectors so compound label scans cannot hang on large MIS shells.
        FilterFieldDefinition(
            name="zone",
            selector="#complaintZoneInput",
            field_type="select",
            value=ZONE_SCR,
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
            value=VIEW_DIVISION_WISE,
            required=True,
            label="View",
        ),
    ]


def output_filter(watering_point: str) -> FilterFieldDefinition:
    """Output dropdown: Previous Watering Point / Upcoming Watering Point."""
    return FilterFieldDefinition(
        name="output",
        selector="#outputTypeInput, select[id*='output' i], select[name*='output' i]",
        field_type="select",
        value=watering_point,
        required=True,
        label="Output",
    )


def filters_for_source(watering_point: str) -> list[FilterFieldDefinition]:
    """Base filters + Output = Previous/Upcoming Watering Point."""
    return [*base_filters(), output_filter(watering_point)]


def filters_previous() -> list[FilterFieldDefinition]:
    return filters_for_source(SOURCE_PREVIOUS_LABEL)


def filters_upcoming() -> list[FilterFieldDefinition]:
    return filters_for_source(SOURCE_UPCOMING_LABEL)
