"""Unit tests for Daily Summary builders and source isolation."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from app.features.daily_summary.builder import (
    build_comprehensive_section,
    build_full_summary,
    build_report1_section,
    build_report2_section,
    build_report3_section,
    build_report4_section,
    build_report5_section,
    build_report6_section,
    build_report9_section,
    reconcile_summary,
)
from app.features.daily_summary.sources import ReportSource, RunSources


def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def test_report3_no_scr_sentence():
    rows = [
        {
            "Train No.": "12345",
            "Train Name": "OTHER EXP",
            "Owning Zone": "Northern Railway",
            "Owning Division": "DLI",
            "Received": "10",
        }
    ]
    source = ReportSource(slug="train-no", status="success", available=True, rows=rows)
    text, _ = build_report3_section(source, "14.07.2026")
    assert "No SCR based train had come as on 14.07.2026" in text
    assert "Bottom 20 trains w.r.to maximum Grievances" in text


def test_report3_lists_scr_trains():
    rows = [
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
    ]
    source = ReportSource(slug="train-no", status="success", available=True, rows=rows)
    text, count = build_report3_section(source, "14.07.2026")
    assert "12721 DAKSHIN with 42 complaint(s)" in text
    assert "99999" not in text
    assert count == 2


def test_report4_groups_by_type_and_division():
    source = ReportSource(
        slug="types",
        status="success",
        available=True,
        type_datasets={
            "Security": [
                {
                    "Train No.": "12721",
                    "Train Name": "DAKSHIN",
                    "Owning Zone": "South Central Railway",
                    "Owning Division": "HYB",
                    "Received": "5",
                }
            ],
            "Bedroll": [
                {
                    "Train No.": "17001",
                    "Train Name": "EXP",
                    "Owning Zone": "Western Railway",
                    "Owning Division": "BCT",
                    "Received": "9",
                }
            ],
        },
    )
    text, _ = build_report4_section(source, "14.07.2026")
    assert "*Security*" in text
    assert "*HYB*" in text
    assert "12721 DAKSHIN 5 complaint(s)" in text
    assert "*Bedroll*" in text
    assert "*SCR-NIL*" in text


def test_report4_scr_nil_zone_line():
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
                },
                {
                    "Train No.": "22222",
                    "Train Name": "CR EXP",
                    "Owning Zone": "Central Railway",
                    "Owning Division": "BCT",
                    "Received": "2",
                },
            ],
        },
    )
    text, _ = build_report4_section(source, "14.07.2026")
    assert "*SCR-NIL*" in text
    assert "Unknown" not in text


def test_report5_totals_and_groups():
    source = ReportSource(
        slug="scr-train",
        status="success",
        available=True,
        row_counts={"expected": 3, "unsatisfactory": 3, "unsatisfactory_percent": 40.0},
        rows=[
            {"Type": "Coach - Cleanliness", "Div": "HYB", "Mode": "T"},
            {"Type": "Coach - Cleanliness", "Div": "SC", "Mode": "T"},
            {"Type": "Security", "Div": "HYB", "Mode": "T"},
        ],
    )
    text, count, notes = build_report5_section(source, "14.07.2026")
    assert "Total unsatisfactory feedback of trains are 3, 40.00%" in text
    assert "Coach - Cleanliness    2" in text
    assert "Security    1" in text
    assert "DIVISION Wise" in text
    assert "HYB 2" in text
    assert "REPORT No.6" in text
    assert "Unknown" not in text
    assert count == 3
    assert notes == []


def test_report5_camelcase_headers_no_unknown():
    source = ReportSource(
        slug="scr-train",
        status="success",
        available=True,
        row_counts={"expected": 2, "unsatisfactory": 2, "unsatisfactory_percent": 25.0},
        rows=[
            {
                "complaintTypeName": "Coach - Cleanliness",
                "divCode": "HYB",
                "complaintMode": "T",
            },
            {
                "complaintTypeName": "Security",
                "divCode": "SC",
                "complaintMode": "T",
            },
        ],
    )
    text, _, _ = build_report5_section(source, "14.07.2026")
    assert "Coach - Cleanliness    1" in text
    assert "Security    1" in text
    assert "HYB 1" in text
    assert "SC 1" in text
    assert "Unknown" not in text
    assert "[]" not in text


def test_report5_zero_state():
    source = ReportSource(
        slug="scr-train",
        status="success",
        available=True,
        row_counts={"expected": 0, "unsatisfactory": 0},
        rows=[],
    )
    text, _, _ = build_report5_section(source, "14.07.2026")
    assert "Total unsatisfactory feedback of trains are 0." in text
    assert "No unsatisfactory train feedback cases were reported as on 14.07.2026." in text


def test_report6_formats_and_excludes_pii():
    source = ReportSource(
        slug="scr-station",
        status="success",
        available=True,
        row_counts={"expected": 1},
        rows=[
            {
                "Train/Station": "BMT",
                "complaintDesc": "Platform dirty near entrance",
                "Dept": "CML",
                "Div": "HYB",
                "userMobile": "9999999999",
                "contactId": "secret",
                "userId": "u1",
            }
        ],
    )
    text, _ = build_report6_section(source, "14.07.2026")
    assert "Unsatisfactory feedback at station are 1" in text
    assert "*BMT*" in text
    assert "Platform dirty near entrance" in text
    assert "[CML-HYB]" in text
    assert "9999999999" not in text
    assert "secret" not in text
    assert "u1" not in text
    assert "Unknown" not in text


def test_report6_camelcase_station_and_tags():
    source = ReportSource(
        slug="scr-station",
        status="success",
        available=True,
        row_counts={"expected": 2},
        rows=[
            {
                "trainStation": "SC",
                "complaintDesc": "Dirty platform",
                "deptCode": "CML",
                "divCode": "HYB",
            },
            {
                "trainStation": "SC",
                "complaintDesc": "Dirty platform",
                "deptCode": "CML",
                "divCode": "HYB",
            },
        ],
    )
    text, _ = build_report6_section(source, "14.07.2026")
    assert "*SC*" in text
    assert "[CML-HYB]" in text
    assert "Unknown" not in text
    assert "[]" not in text


def test_report6_zero_state():
    source = ReportSource(
        slug="scr-station",
        status="success",
        available=True,
        row_counts={"expected": 0},
        rows=[],
    )
    text, _ = build_report6_section(source, "14.07.2026")
    assert "Unsatisfactory feedback at station are 0." in text


def test_report1_zone_block():
    source = ReportSource(
        slug="report1",
        status="success",
        available=True,
        rows=[
            {
                "Organisation": "South Central Railway",
                "Received": "100",
                "Closed": "80",
                "Rank": "1",
            },
            {"Organisation": "Total", "Received": "500", "Closed": "400"},
        ],
    )
    text, count = build_report1_section(source, "14.07.2026")
    assert "*ZONE WISE*" in text
    assert "*South Central Railway* Received 100" in text
    assert count == 1


def test_report2_division_block():
    source = ReportSource(
        slug="division",
        status="success",
        available=True,
        rows=[
            {"Division": "Secunderabad", "Received": "10"},
            {"Division": "Hyderabad", "Received": "8"},
        ],
    )
    text, count = build_report2_section(source, "14.07.2026")
    assert "*DIVISION WISE COMPLAINTS*" in text
    assert "SC 10" in text
    assert "HYB 8" in text
    assert count == 18


def test_report9_overview():
    source = ReportSource(
        slug="report9",
        status="success",
        available=True,
        section_datasets={
            "all_zone_train": [
                {"Cause": "Security", "Received": "10"},
                {"Cause": "Total", "Received": "50"},
            ],
        },
    )
    text, count = build_report9_section(source, "14.07.2026")
    assert "*CAUSE WISE OVERVIEW*" in text
    assert "All Zones Train:" in text
    assert "Security" in text
    assert count == 1


def test_comprehensive_section():
    source = ReportSource(
        slug="comprehensive-10-13",
        status="success",
        available=True,
        section_datasets={
            "report10_cw": [
                {"Division": "SC", "Received": "3", "Closed": "2"},
                {"Division": "Total", "Received": "3", "Closed": "2"},
            ],
        },
    )
    text, count = build_comprehensive_section(source, "14.07.2026")
    assert "*COMPREHENSIVE REPORTS*" in text
    assert "Report 10 (C&W)" in text
    assert "Received 3" in text
    assert count == 1


def test_unavailable_uses_standard_message():
    text, _ = build_report1_section(None, "14.07.2026")
    assert "Data unavailable for the selected run." in text


def test_reconcile_scr_train_mismatch():
    source = ReportSource(
        slug="scr-train",
        status="success",
        available=True,
        row_counts={"unsatisfactory": 5},
        rows=[
            {"Type": "Security", "Div": "HYB"},
            {"Type": "Cleanliness", "Div": "SC"},
        ],
    )
    sources = RunSources(
        run_id="run-1",
        user_id="user-1",
        run_status="completed",
        reports={"scr-train": source},
    )
    notes = reconcile_summary(sources, {"scr-train": 2}, [])
    assert any("cause count" in n for n in notes)


def test_full_summary_marks_missing_sections():
    sources = RunSources(
        run_id="run-1",
        user_id="user-1",
        run_status="completed",
        reports={
            "train-no": ReportSource(
                slug="train-no",
                status="success",
                available=True,
                rows=[
                    {
                        "Train No.": "1",
                        "Train Name": "X",
                        "Owning Zone": "Northern Railway",
                        "Received": "1",
                    }
                ],
            ),
        },
        missing_reports=[
            "report1",
            "division",
            "types",
            "scr-train",
            "scr-station",
            "report9",
            "comprehensive-10-13",
        ],
        all_terminal=True,
    )
    text, counts, missing, _ = build_full_summary(sources, "14.07.2026")
    assert "No SCR based train" in text
    assert "Data unavailable for the selected run." in text
    assert "types" in missing
    assert counts["train-no"] == 1


def test_resolve_run_sources_uses_result_json_only(tmp_path, monkeypatch):
    from app.features.daily_summary.sources import resolve_run_sources
    from app.infrastructure.database.models import AutomationRunModel

    storage = tmp_path / "storage" / "extracted" / "train-no"
    storage.mkdir(parents=True)
    current = storage / "current.csv"
    stale = storage / "stale.csv"
    _write_csv(
        current,
        ["Train No.", "Train Name", "Owning Zone", "Owning Division", "Received"],
        [["12721", "DAKSHIN", "South Central Railway", "SC", "5"]],
    )
    _write_csv(
        stale,
        ["Train No.", "Train Name", "Owning Zone", "Owning Division", "Received"],
        [["99999", "STALE", "South Central Railway", "SC", "99"]],
    )

    monkeypatch.setattr(
        "app.features.daily_summary.sources.is_under_storage",
        lambda p: True,
    )

    run = AutomationRunModel(
        id="run-abc",
        profile_id="prof",
        status="completed",
        created_by="user-1",
        result_json=json.dumps(
            {
                "reports": [
                    {
                        "slug": "train-no",
                        "status": "success",
                        "source_csv_path": str(current),
                        "source_paths": [str(current)],
                        "row_counts": {},
                    }
                ]
            }
        ),
    )
    sources = resolve_run_sources(run)
    assert sources.reports["train-no"].available
    assert sources.reports["train-no"].rows[0]["Train No."] == "12721"
    assert all(r["Train No."] != "99999" for r in sources.reports["train-no"].rows)
