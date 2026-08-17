"""Tests for territorial section rendering in Daily Summary."""

from __future__ import annotations

from pathlib import Path

from app.automation.processing.bottom_report_models import (
    BottomReportResult,
    SectionResult,
)
from app.features.daily_summary.aggregator import aggregate_territorial, build_summary_data
from app.features.daily_summary.builder import render_summary
from app.features.daily_summary.sources import ReportSource, RunSources


def _load_fixture_bottom_report() -> BottomReportResult | None:
    fixture = (
        Path(__file__).resolve().parents[3]
        / "storage"
        / "extracted"
        / "bottom-report"
        / "e492468d-b487-49b7-8880-53e525e56def"
        / "result.json"
    )
    if not fixture.is_file():
        return None
    return BottomReportResult.load(fixture)


def test_territorial_renders_separate_divisions():
    bottom = _load_fixture_bottom_report()
    if bottom is None:
        return

    sources = RunSources(
        run_id="e492468d-b487-49b7-8880-53e525e56def",
        user_id="user-1",
        run_status="completed",
        reports={
            "train-no": ReportSource(slug="train-no", status="success", available=True, rows=[]),
            "bottom-report": ReportSource(
                slug="bottom-report",
                status="success",
                available=True,
                bottom_report=bottom,
                source_csv_path=str(
                    Path(__file__).resolve().parents[3]
                    / "storage"
                    / "extracted"
                    / "bottom-report"
                    / "e492468d-b487-49b7-8880-53e525e56def"
                    / "result.json"
                ),
            ),
        },
    )
    data = build_summary_data(sources, "16.08.2026")
    text = render_summary(data)
    assert "*TERRITORIAL*" in text
    assert "*Punctuality*" in text
    assert "*SC DIVISION*" in text
    assert "complaints" in text
    assert "12722" in text or "12721" in text


def test_territorial_nil_security_message():
    bottom = BottomReportResult(
        report_slug="bottom-report",
        date_from="2026-08-16",
        date_to="2026-08-16",
        sections={
            "security": SectionResult.from_dict(
                {
                    "section_id": "security",
                    "qualifying_divisions": [],
                    "no_division_message": "No Div. has figured with more than 20 complaints",
                }
            ),
        },
    )
    section = aggregate_territorial(
        ReportSource(
            slug="bottom-report",
            status="success",
            available=True,
            bottom_report=bottom,
        )
    )
    security = next(c for c in section.causes if c.cause_id == "security")
    assert security.no_division_message == "No Div. has figured with more than 20 complaints"
