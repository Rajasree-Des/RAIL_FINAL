"""Tests for daily summary canonical field resolution."""

from __future__ import annotations

from app.features.daily_summary.fields import get_field, normalize_header_key


def test_normalize_header_key():
    assert normalize_header_key("Train No.") == "trainno"
    assert normalize_header_key("complaintTypeName") == "complainttypename"


def test_get_field_camelcase():
    row = {
        "complaintTypeName": "Security",
        "divCode": "HYB",
        "deptCode": "CML",
        "trainStation": "SC",
    }
    assert get_field(row, "complaint_type") == "Security"
    assert get_field(row, "division") == "HYB"
    assert get_field(row, "department") == "CML"
    assert get_field(row, "station") == "SC"


def test_get_field_display_labels():
    row = {"Type": "Coach - Cleanliness", "Div": "SC", "Dept": "OPS"}
    assert get_field(row, "complaint_type") == "Coach - Cleanliness"
    assert get_field(row, "division") == "SC"
    assert get_field(row, "department") == "OPS"


def test_get_field_returns_none_not_unknown():
    row = {"Mode": "T"}
    assert get_field(row, "complaint_type", slug="scr-train") is None
