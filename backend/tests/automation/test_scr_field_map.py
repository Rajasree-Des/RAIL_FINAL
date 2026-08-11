"""Tests for SCR portal header canonicalization."""

from __future__ import annotations

from pathlib import Path

from app.automation.scr_field_map import (
    canonicalize_scr_row,
    normalize_header,
    portal_header_to_canonical,
    verify_scr_csv,
)

LIVE_CSV = (
    Path(__file__).resolve().parents[2]
    / "storage"
    / "extracted"
    / "scr-train"
    / "scr-train_complaints_raw.csv"
)


def test_normalize_header_collapses_spaces_and_case():
    assert normalize_header("  Ref. No. ") == "ref. no."
    assert normalize_header("Owning   Zone") == "owning zone"


def test_portal_header_aliases_from_live_names():
    assert portal_header_to_canonical("Ref. No.") == "complaintRefNo"
    assert portal_header_to_canonical("Registration Date") == "createdOn"
    assert portal_header_to_canonical("Zone") == "zoneCode"
    assert portal_header_to_canonical("Div") == "divCode"
    assert portal_header_to_canonical("Dept") == "deptCode"
    assert portal_header_to_canonical("trainNameForReport/Station Name") == "trainNameForReport"
    assert portal_header_to_canonical("Disposal Time") == "diff"
    assert portal_header_to_canonical("Status") == "status"


def test_canonicalize_scr_row_maps_by_header_not_position():
    row = {
        "Ref. No.": "RM123",
        "Registration Date": "15-07-26",
        "Zone": "SC",
        "Div": "HYB",
        "complaintDesc": "Dirty coach",
        "userId": "uid1",
        "feedbackRemark": "Poor",
        "Mode": "Train",
    }
    canonical = canonicalize_scr_row(row)
    assert canonical["complaintRefNo"] == "RM123"
    assert canonical["createdOn"] == "15-07-26"
    assert canonical["zoneCode"] == "SC"
    assert canonical["divCode"] == "HYB"
    assert canonical["complaintDesc"] == "Dirty coach"
    assert canonical["mode"] == "Train"


def test_verify_scr_csv_accepts_empty_feedback_remark_when_header_present():
    row = {
        "Ref. No.": "REF001",
        "Train/Station": "Secunderabad Station",
        "Type": "Cleanliness",
        "Sub Type": "Platform",
        "Dept": "Ops",
        "Status": "Pending",
        "Zone": "SC",
        "Div": "HYB",
        "feedbackRemark": "",
        "complaintDesc": "Garbage on platform",
        "remarks": "Needs cleaning",
        "userId": "uid",
        "Mode": "Station",
    }
    result = verify_scr_csv([row], report_num=6)
    assert result.ok is True
    assert "feedbackRemark" not in result.missing_required_fields
    assert "feedbackRemark" in result.empty_required_fields


def test_verify_scr_csv_accepts_fixture_row():
    row = {
        "Ref. No.": "REF001",
        "Registration Date": "15-07-26",
        "Train/Station": "Rajdhani",
        "Type": "Cleanliness",
        "Sub Type": "General",
        "Department": "Ops",
        "Status": "Pending",
        "Zone": "SC",
        "Div": "HYB",
        "feedbackRemark": "Poor",
        "trainNameForReport/Station Name": "Rajdhani",
        "complaintDesc": "Dirty",
        "remarks": "Follow up",
        "userId": "uid",
        "Mode": "Train",
    }
    result = verify_scr_csv([row], report_num=5)
    assert result.ok is True
    assert "complaintRefNo" in result.canonical_fields_mapped


def test_verify_scr_csv_live_headers_if_present():
    if not LIVE_CSV.is_file():
        return
    import csv

    with LIVE_CSV.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if not rows:
        return
    result = verify_scr_csv(rows[:5], report_num=5)
    assert result.row_count <= 5
    assert result.source_headers
