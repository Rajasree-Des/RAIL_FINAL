"""Unit tests for Daily Summary aggregation."""

from __future__ import annotations

from pathlib import Path

from app.automation.processing.bottom_report_models import BottomReportResult
from app.features.daily_summary.aggregator import (
    aggregate_bottom_20,
    aggregate_cause_wise,
    aggregate_territorial,
    build_summary_data,
    format_train_name_for_summary,
)
from app.features.daily_summary.sources import ReportSource, RunSources


def test_format_train_name_strips_brackets():
    assert format_train_name_for_summary("NZM-HYB DAKSHIN EXP [SUPERFAST]") == "NZM-HYB DAKSHIN EXP"


def test_aggregate_bottom_20_scr_trains():
    source = ReportSource(
        slug="train-no",
        status="success",
        available=True,
        rows=[
            {
                "Train No.": "12721",
                "Train Name": "DAKSHIN",
                "Owning Zone": "South Central Railway",
                "Owning Division": "SC",
                "Received": "42",
            },
            {
                "Train No.": "99999",
                "Train Name": "OTHER",
                "Owning Zone": "Western Railway",
                "Owning Division": "BCT",
                "Received": "40",
            },
        ],
    )
    section = aggregate_bottom_20(source)
    assert len(section.scr_trains) == 1
    assert section.scr_trains[0].train_no == "12721"
    assert section.scr_trains[0].complaint_count == 42


def test_aggregate_cause_wise_nil():
    source = ReportSource(
        slug="types",
        status="success",
        available=True,
        type_datasets={
            "Security": [
                {
                    "Train No.": "11111",
                    "Train Name": "NR EXP",
                    "Owning Zone": "Northern Railway",
                    "Owning Division": "DLI",
                    "Received": "3",
                }
            ],
        },
    )
    section = aggregate_cause_wise(source)
    assert section.is_nil is True
    assert section.blocks == []


def test_aggregate_territorial_from_fixture():
    fixture = (
        Path(__file__).resolve().parents[3]
        / "storage"
        / "extracted"
        / "bottom-report"
        / "e492468d-b487-49b7-8880-53e525e56def"
        / "result.json"
    )
    if not fixture.is_file():
        return

    bottom = BottomReportResult.load(fixture)
    source = ReportSource(
        slug="bottom-report",
        status="success",
        available=True,
        bottom_report=bottom,
        source_csv_path=str(fixture),
    )
    section = aggregate_territorial(source)
    assert section.causes
    punctuality = next(c for c in section.causes if c.cause_id == "punctuality")
    assert punctuality.divisions
    sc_div = next(d for d in punctuality.divisions if d.division_code == "SC")
    assert sc_div.trains
    assert sc_div.trains[0].train_name == "DNR-SC EXP"


def test_build_summary_data_tracks_missing():
    sources = RunSources(
        run_id="run-1",
        user_id="user-1",
        run_status="completed",
        reports={},
        missing_reports=["types", "bottom-report", "scr-train", "scr-station"],
    )
    data = build_summary_data(sources, "16.08.2026")
    assert "types" in data.missing_sources
    assert data.report_date == "16.08.2026"
