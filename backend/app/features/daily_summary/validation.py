"""Validation and cross-checks for Daily Summary data."""

from __future__ import annotations

from datetime import date

from app.automation.processing.bottom_report_models import BottomReportResult
from app.features.daily_summary.constants import SUMMARY_SOURCES
from app.features.daily_summary.models import (
    SectionAvailability,
    SummaryData,
)
from app.features.daily_summary.sources import RunSources


def _parse_report_date(value: str) -> date | None:
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            from datetime import datetime

            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def validate_summary_data(
    data: SummaryData,
    sources: RunSources,
    *,
    run_date_from: date | None = None,
) -> list[str]:
    """Return validation notes; do not mutate summary values."""
    notes: list[str] = list(data.warnings)

    if not data.report_date:
        notes.append("report_date missing")
    elif run_date_from is not None:
        parsed = _parse_report_date(data.report_date)
        if parsed and parsed != run_date_from:
            notes.append(
                f"report_date ({data.report_date}) != run.date_from ({run_date_from.isoformat()})"
            )

    bottom_report = sources.reports.get("bottom-report")
    if bottom_report and bottom_report.bottom_report and run_date_from is not None:
        br: BottomReportResult = bottom_report.bottom_report
        if br.date_from:
            try:
                br_date = date.fromisoformat(br.date_from)
                if br_date != run_date_from:
                    notes.append(
                        f"bottom-report date_from ({br.date_from}) != run.date_from "
                        f"({run_date_from.isoformat()})"
                    )
            except ValueError:
                notes.append(f"bottom-report date_from unparseable: {br.date_from}")

    for slug in SUMMARY_SOURCES.values():
        if slug in data.missing_sources:
            notes.append(f"{slug}: required source missing for this run")
            continue
        report = sources.reports.get(slug)
        if report is None or not report.available:
            continue
        path = report.source_csv_path or (report.source_paths[0] if report.source_paths else None)
        if path and sources.run_id and sources.run_id not in path:
            notes.append(f"{slug}: artifact path missing run_id={sources.run_id}")

    unsat = data.unsatisfactory_train
    if unsat.availability == SectionAvailability.AVAILABLE and unsat.total is not None:
        cause_sum = sum(count for _, count in unsat.cause_counts)
        if cause_sum and cause_sum != unsat.total:
            notes.append(
                f"scr-train: cause breakdown sum ({cause_sum}) != total ({unsat.total})"
            )
        if unsat.percent is None:
            notes.append("scr-train: unsatisfactory_percent missing from run metadata")

    station = data.station_feedback
    if (
        station.availability == SectionAvailability.AVAILABLE
        and station.count is not None
        and station.highlights
        and len(station.highlights) != station.count
        and station.row_count
    ):
        notes.append(
            f"scr-station: highlight count ({len(station.highlights)}) "
            f"!= unsatisfactory total ({station.count})"
        )

    for cause_block in data.territorial.causes:
        for div_block in cause_block.divisions:
            for train in div_block.trains:
                if not train.train_no:
                    notes.append(
                        f"territorial/{cause_block.cause_id}/{div_block.division_code}: "
                        "empty train number"
                    )

    if not sources.run_id:
        notes.append("run_id missing from sources")

    return list(dict.fromkeys(notes))
