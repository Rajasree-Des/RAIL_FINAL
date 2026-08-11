"""Filter definitions and metadata for Report Vande Bharat (Report No. 18).

Dates are applied via portal_from_date (Phase 1). Zone is forced to
South Central Railway; other portal filters stay at defaults.

Portal identity (from live RailMadad):
  Menu:  18) Vande Bharat Report
  Title: Vande Bharat Train Report
  Path:  /mis_reports/vandebharatreport
"""

from __future__ import annotations

from app.automation.report1_filters import FilterFieldDefinition

REPORT18_TAB_LABEL = "18) Vande Bharat Report"
REPORT18_PAGE_PATH = "/mis_reports/vandebharatreport"
REPORT18_URL_FRAGMENT = "mis_reports/vandebharatreport"

REPORT18_DISPLAY_NAME = "Report Vande Bharat"
REPORT18_FILE_STEM = "Report Vande Bharat"
REPORT18_CSV_FILENAME = "vande_bharat.csv"
REPORT18_DETAIL_CSV_FILENAME = "vande_bharat_complaint_details.csv"
REPORT18_LOG_PREFIX = "[Vande Bharat]"

ZONE_SCR = "South Central Railway"

# Must match the main-content page title only — not the sidebar label
# "18) Vande Bharat Report" (that text is visible on every MIS page).
FORM_HEADING_MARKERS = (
    "Vande Bharat Train Report",
)

FORM_CONTROL_LABELS = (
    "From Date",
    "To Date",
    "Zone",
    "Submit",
)

REPORT_18_FILTERS: list[FilterFieldDefinition] = [
    FilterFieldDefinition(
        name="zone",
        selector="#complaintZoneInput",
        field_type="select",
        value=ZONE_SCR,
        required=True,
        label="Zone",
    ),
]
