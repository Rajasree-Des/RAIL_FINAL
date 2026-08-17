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


def test_loads_bottom_report_json(tmp_path, monkeypatch):
    run_id = "run-xyz"
    result_path = tmp_path / "storage" / "extracted" / "bottom-report" / run_id / "result.json"
    result_path.parent.mkdir(parents=True)
    result_path.write_text(
        json.dumps(
            {
                "report_slug": "bottom-report",
                "date_from": "2026-08-16",
                "date_to": "2026-08-16",
                "sections": {
                    "security": {
                        "section_id": "security",
                        "qualifying_divisions": [],
                        "no_division_message": "No Div. has figured with more than 20 complaints",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "app.features.daily_summary.sources.is_under_storage",
        lambda p: True,
    )

    run = AutomationRunModel(
        id=run_id,
        profile_id="prof",
        status="completed",
        created_by="user-1",
        result_json=json.dumps(
            {
                "reports": [
                    {
                        "slug": "bottom-report",
                        "status": "success",
                        "source_csv_path": str(result_path),
                        "source_paths": [str(result_path)],
                    },
                ]
            }
        ),
    )
    sources = resolve_run_sources(run)
    report = sources.reports["bottom-report"]
    assert report.available
    assert report.bottom_report is not None
    assert report.bottom_report.date_from == "2026-08-16"


def test_accepts_artifact_path_without_run_id_when_from_result_json(tmp_path, monkeypatch):
    run_id = "run-abc"
    csv_path = tmp_path / "storage" / "extracted" / "train-no" / "train-no_2026-08-16.csv"
    _write_csv(
        csv_path,
        ["Train No.", "Train Name", "Owning Zone", "Owning Division", "Received"],
        [["12721", "DAKSHIN", "South Central Railway", "SC", "5"]],
    )

    monkeypatch.setattr(
        "app.features.daily_summary.sources.is_under_storage",
        lambda p: True,
    )

    run = AutomationRunModel(
        id=run_id,
        profile_id="prof",
        status="completed",
        created_by="user-1",
        result_json=json.dumps(
            {
                "reports": [
                    {
                        "slug": "train-no",
                        "status": "success",
                        "source_csv_path": str(csv_path),
                    },
                ]
            }
        ),
    )
    sources = resolve_run_sources(run)
    assert sources.reports["train-no"].available
    assert sources.reports["train-no"].rows[0]["Train No."] == "12721"
    assert any("does not include run_id" in n for n in sources.validation_notes)
