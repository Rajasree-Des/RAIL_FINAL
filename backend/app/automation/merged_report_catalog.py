"""Canonical ordering and labels for merged PDF / Excel downloads."""

from __future__ import annotations

from dataclasses import dataclass

from app.automation.report_keys import canonicalize_report_key


@dataclass(frozen=True)
class MergedReportEntry:
    slug: str
    report_number: int
    display_title: str
    sheet_name: str
    toc_line: str


# Order MUST match frontend REPORT_SLUG_ORDER / AUTOMATION_REPORTS.
MERGED_REPORT_CATALOG: tuple[MergedReportEntry, ...] = (
    MergedReportEntry(
        slug="report1",
        report_number=1,
        display_title="Zone Wise Report",
        sheet_name="Report 1 - Zone Wise",
        toc_line="Report 1 : Zone Wise Report",
    ),
    MergedReportEntry(
        slug="division",
        report_number=2,
        display_title="Division Report",
        sheet_name="Report 2 - Division",
        toc_line="Report 2 : Division Report",
    ),
    MergedReportEntry(
        slug="train-no",
        report_number=3,
        display_title="Top 20 Trains",
        sheet_name="Report 3 - Top 20 Trains",
        toc_line="Report 3 : Top 20 Trains",
    ),
    MergedReportEntry(
        slug="types",
        report_number=5,
        display_title="Cause Wise Analysis",
        sheet_name="Report 5 - Cause Wise",
        toc_line="Report 5 : Cause Wise Analysis",
    ),
    MergedReportEntry(
        slug="scr-train",
        report_number=6,
        display_title="SCR Train Report",
        sheet_name="Report 6 - SCR Train",
        toc_line="Report 6 : SCR Train Report",
    ),
    MergedReportEntry(
        slug="scr-station",
        report_number=7,
        display_title="SCR Station Report",
        sheet_name="Report 7 - SCR Station",
        toc_line="Report 7 : SCR Station Report",
    ),
    MergedReportEntry(
        slug="report9",
        report_number=9,
        display_title="All Zones Train/Station Cause Wise on Date",
        sheet_name="Report 9 - All Zones",
        toc_line="Report 9 : All Zones Train/Station Cause Wise on Date",
    ),
    MergedReportEntry(
        slug="comprehensive-10-13",
        report_number=10,
        display_title="Comprehensive Reports",
        sheet_name="Report 10-13 - Comprehensive",
        toc_line="Report 10–13 : Comprehensive Reports",
    ),
    MergedReportEntry(
        slug="report14",
        report_number=14,
        display_title="Watering Complaints",
        sheet_name="Report 14 - Watering",
        toc_line="Report 14 : Watering Complaints",
    ),
    MergedReportEntry(
        slug="report18",
        report_number=18,
        display_title="Report Vande Bharat",
        sheet_name="Report 18 - Vande Bharat",
        toc_line="Report Vande Bharat",
    ),
    MergedReportEntry(
        slug="bottom-report",
        report_number=19,
        display_title="Bottom Performed Trains Report",
        sheet_name="Bottom Performed Trains",
        toc_line="Bottom Performed Trains Report",
    ),
)

CATALOG_BY_SLUG: dict[str, MergedReportEntry] = {
    entry.slug: entry for entry in MERGED_REPORT_CATALOG
}

# Slugs excluded from Download Complete PDF / Excel only.
# Vande Bharat (report18) still generates and appears individually in the UI.
CONSOLIDATED_DOWNLOAD_EXCLUDED_SLUGS: frozenset[str] = frozenset({"report18", "bottom-report"})


def is_excluded_from_consolidated_download(slug: str | None) -> bool:
    """True when a report must not appear in merged PDF/Excel downloads."""
    if not slug:
        return False
    return canonicalize_report_key(slug) in CONSOLIDATED_DOWNLOAD_EXCLUDED_SLUGS


def consolidated_download_catalog() -> tuple[MergedReportEntry, ...]:
    """Catalog entries included in Download Complete PDF / Excel."""
    return tuple(
        entry
        for entry in MERGED_REPORT_CATALOG
        if entry.slug not in CONSOLIDATED_DOWNLOAD_EXCLUDED_SLUGS
    )


def merged_download_urls(run_id: str) -> dict[str, str]:
    base = f"/api/v1/automation/runs/{run_id}"
    return {
        "download_pdf_all_url": f"{base}/download/pdf/all",
        "download_excel_all_url": f"{base}/download/excel/all",
    }


def resolve_catalog_entry(slug: str | None) -> MergedReportEntry | None:
    if not slug:
        return None
    return CATALOG_BY_SLUG.get(canonicalize_report_key(slug))
