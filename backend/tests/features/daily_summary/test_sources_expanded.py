"""Tests for expanded daily summary source loading."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from app.features.daily_summary.sources import resolve_run_sources
from app.infrastructure.database.models import AutomationRunModel


def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def test_loads_report9_and_comprehensive_sections(tmp_path, monkeypatch):
    base = tmp_path / "storage" / "extracted"
    r9_index = base / "report9" / "report9_combined_index.csv"
    r9_csv = base / "report9" / "all_zone_train.csv"
    comp_index = base / "comprehensive-10-13" / "comprehensive_combined_index.csv"
    comp_csv = base / "comprehensive-10-13" / "report10_cw.csv"

    _write_csv(r9_csv, ["Cause", "Received"], [["Security", "10"], ["Total", "10"]])
    _write_csv(
        r9_index,
        ["source_id", "section_title", "zone", "csv_path", "row_count", "status", "error"],
        [["all_zone_train", "Train", "ALL", str(r9_csv), "1", "success", ""]],
    )
    _write_csv(
        comp_csv,
        ["Division", "Received", "Closed"],
        [["SC", "3", "2"], ["Total", "3", "2"]],
    )
    _write_csv(
        comp_index,
        ["section_id", "section_name", "csv_path", "row_count", "status", "error"],
        [["report10_cw", "Report 10", str(comp_csv), "1", "success", ""]],
    )

    monkeypatch.setattr(
        "app.features.daily_summary.sources.is_under_storage",
        lambda p: True,
    )

    run = AutomationRunModel(
        id="run-xyz",
        profile_id="prof",
        status="completed",
        created_by="user-1",
        result_json=json.dumps(
            {
                "reports": [
                    {
                        "slug": "report9",
                        "status": "success",
                        "source_csv_path": str(r9_index),
                    },
                    {
                        "slug": "comprehensive-10-13",
                        "status": "success",
                        "source_csv_path": str(comp_index),
                    },
                ]
            }
        ),
    )
    sources = resolve_run_sources(run)
    assert sources.reports["report9"].available
    assert "all_zone_train" in sources.reports["report9"].section_datasets
    assert sources.reports["comprehensive-10-13"].available
    assert "report10_cw" in sources.reports["comprehensive-10-13"].section_datasets
