"""Tests for canonical artifact title mapping."""

from __future__ import annotations

from datetime import date

import pytest

from app.automation.date_range import ReportDateRange
from app.automation.formatting.artifact_titles import (
    ARTIFACT_DISPLAY_TITLES,
    build_artifact_main_title,
    get_artifact_base_title,
    is_artifact_title_row,
)


def test_artifact_display_titles_match_standard_names() -> None:
    assert ARTIFACT_DISPLAY_TITLES["types"] == "Report 5: Cause Wise Analysis"
    assert ARTIFACT_DISPLAY_TITLES["scr-train"] == "Report 6: SCR Train Report"
    assert ARTIFACT_DISPLAY_TITLES["scr-station"] == "Report 7: SCR Station Report"
    assert (
        ARTIFACT_DISPLAY_TITLES["report9"]
        == "Report 9: All Zones Train/Station Cause Wise on Date"
    )


def test_build_artifact_main_title_single_date() -> None:
    date_range = ReportDateRange(date_from=date(2026, 7, 28), date_to=date(2026, 7, 28))
    assert (
        build_artifact_main_title("types", date_range)
        == "Report 5: Cause Wise Analysis on date 28-07-2026"
    )
    assert (
        build_artifact_main_title("scr-train", date_range)
        == "Report 6: SCR Train Report on date 28-07-2026"
    )
    assert (
        build_artifact_main_title("scr-station", date_range)
        == "Report 7: SCR Station Report on date 28-07-2026"
    )
    assert (
        build_artifact_main_title("report9", date_range)
        == "Report 9: All Zones Train/Station Cause Wise on Date — 28-07-2026"
    )


def test_build_artifact_main_title_date_range() -> None:
    date_range = ReportDateRange(date_from=date(2026, 7, 28), date_to=date(2026, 7, 29))
    assert (
        build_artifact_main_title("types", date_range)
        == "Report 5: Cause Wise Analysis from 28-07-2026 to 29-07-2026"
    )
    assert (
        build_artifact_main_title("report9", date_range)
        == "Report 9: All Zones Train/Station Cause Wise on Date — 28-07-2026 to 29-07-2026"
    )


def test_is_artifact_title_row() -> None:
    assert is_artifact_title_row(["Report 5: Cause Wise Analysis on date 28-07-2026"])
    assert is_artifact_title_row(["Rail Madad Report No 4 - Cause wise Top 10 Trains on date 28-07-2026"])
    assert not is_artifact_title_row(["S.No.", "Train Name"])


def test_get_artifact_base_title_unknown_slug() -> None:
    with pytest.raises(KeyError):
        get_artifact_base_title("unknown-slug")
