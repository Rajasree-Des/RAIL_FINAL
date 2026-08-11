"""Tests for Report 10-13 comprehensive column snapshot validation."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.automation.comprehensive1013_filters import COMPREHENSIVE_1013_SECTION_IDS
from app.automation.processing.comprehensive_output_columns import (
    COMPREHENSIVE_COLUMN_IDS,
    build_comprehensive_artifact_metadata,
    build_comprehensive_column_snapshot,
    compute_comprehensive_snapshot_hash,
    normalize_comprehensive_column_id,
    sanitize_comprehensive_section_columns,
    validate_comprehensive_artifact_metadata,
)
from app.automation.processing.comprehensive1013_processor import Comprehensive1013Processor
from app.features.reports.schemas import ManualGenerateRequest
from app.features.reports.service import _artifacts_for_slug, _dual_artifacts_metadata_consistent, build_config_snapshot


def _full_sections(**overrides: list[str]) -> dict[str, dict[str, list[str]]]:
    defaults = {
        section_id: {"selected_column_ids": list(COMPREHENSIVE_COLUMN_IDS)}
        for section_id in COMPREHENSIVE_1013_SECTION_IDS
    }
    for section_id, selected in overrides.items():
        defaults[section_id] = {"selected_column_ids": selected}
    return defaults


def _ten_column_sections() -> dict[str, dict[str, list[str]]]:
    ten_cols = [col for col in COMPREHENSIVE_COLUMN_IDS if col != "opening_balance"]
    return _full_sections(
        report10_cw=ten_cols,
        report11_security=ten_cols,
        report12_punctuality=ten_cols,
        report13_electrical=ten_cols,
    )


def _art(tmp_path: Path, *, meta: dict, artifact_type: str = "excel") -> SimpleNamespace:
    path = tmp_path / f"{artifact_type}.bin"
    path.write_bytes(b"x")
    return SimpleNamespace(
        report_slug="comprehensive-10-13",
        artifact_type=artifact_type,
        status="ready",
        file_size_bytes=1,
        file_path=str(path),
        metadata_json=json.dumps(meta),
    )


def test_default_configuration_snapshot_and_metadata():
    sections = _full_sections()
    snapshot = build_comprehensive_column_snapshot(
        sections,
        date_from="2026-08-01",
        date_to="2026-08-01",
    )
    assert snapshot["version"] == 1
    assert snapshot["date_from"] == "2026-08-01"
    assert snapshot["snapshot_hash"]
    assert len(snapshot["sections"]) == 4

    meta = build_comprehensive_artifact_metadata(snapshot, run_id="run-1")
    ok, err = validate_comprehensive_artifact_metadata(meta, meta, snapshot, run_id="run-1")
    assert ok is True
    assert err is None


def test_ten_selected_columns_generate_snapshot():
    snapshot = build_comprehensive_column_snapshot(
        _ten_column_sections(),
        date_from="2026-08-01",
        date_to="2026-08-01",
    )
    assert "opening_balance" not in snapshot["selected_column_ids"]
    assert len(snapshot["sections"]["report10_cw"]["selected_column_ids"]) == 10


def test_different_per_section_selections_do_not_fail_validation():
    sections = {
        section_id: {"selected_column_ids": ["sno", "division", "received"]}
        for section_id in COMPREHENSIVE_1013_SECTION_IDS
    }
    sections["report10_cw"] = {"selected_column_ids": ["sno", "division", "received", "closed"]}
    sections["report11_security"] = {
        "selected_column_ids": ["sno", "division", "received", "share_percent", "avg_rating"]
    }
    snapshot = build_comprehensive_column_snapshot(sections)
    meta = build_comprehensive_artifact_metadata(snapshot, run_id="run-a")

    ok, err = validate_comprehensive_artifact_metadata(meta, meta, snapshot, run_id="run-a")
    assert ok is True
    assert err is None
    assert snapshot["column_order"] == [
        "sno",
        "division",
        "received",
        "share_percent",
        "closed",
        "avg_rating",
    ]


def test_build_config_snapshot_includes_snapshot_hash():
    body = ManualGenerateRequest(
        date_from="2026-08-01",
        date_to="2026-08-01",
        sections=_ten_column_sections(),
    )
    snapshot = build_config_snapshot(body, report_slug="comprehensive-10-13")
    assert snapshot["snapshot_hash"]
    assert snapshot["sections"]["report10_cw"]["selected_column_ids"]


def test_deselected_column_absent_from_projection():
    processor = Comprehensive1013Processor()
    raw_headers = ["S.No.", "Division", "Opening Balance", "Received", "Closed"]
    data_rows = [
        {
            "S.No.": "1",
            "Division": "Hyderabad",
            "Opening Balance": "10",
            "Received": "5",
            "Closed": "3",
        }
    ]
    headers, rows = processor._project_columns(
        raw_headers,
        data_rows,
        ["sno", "division", "received", "closed"],
    )
    assert "Opening Balance" not in headers
    assert headers == ["S.No.", "Division", "Received", "Closed"]


def test_labels_normalize_to_canonical_keys():
    assert normalize_comprehensive_column_id("Received") == "received"
    assert normalize_comprehensive_column_id("% Share") == "share_percent"
    assert sanitize_comprehensive_section_columns(["Received", "Division"]) == [
        "received",
        "division",
    ]


def test_legacy_aliases_normalize_correctly():
    cols = sanitize_comprehensive_section_columns(
        ["S.No.", "Avg. Disposal Time", "Avg Pendency Time"]
    )
    assert cols == ["sno", "avg_disposal_time", "avg_pendency_time"]


def test_unknown_keys_raise_clear_validation_error():
    sections = {
        section_id: {"selected_column_ids": ["sno", "division"]}
        for section_id in COMPREHENSIVE_1013_SECTION_IDS
    }
    sections["report10_cw"] = {"selected_column_ids": ["sno", "not_a_real_column"]}
    with pytest.raises(ValueError, match="invalid="):
        build_comprehensive_column_snapshot(sections)


def test_per_section_order_preserved_in_snapshot():
    ordered = ["division", "sno", "received"]
    snapshot = build_comprehensive_column_snapshot(
        _full_sections(report10_cw=ordered),
    )
    assert snapshot["sections"]["report10_cw"]["selected_column_ids"] == ordered


def test_duplicate_keys_deduped_safely():
    cols = sanitize_comprehensive_section_columns(["received", "received", "division"])
    assert cols == ["received", "division"]


def test_excel_and_pdf_metadata_sections_must_match():
    sections = _full_sections(report10_cw=["sno", "division", "received"])
    snapshot = build_comprehensive_column_snapshot(sections)
    excel_meta = build_comprehensive_artifact_metadata(snapshot)
    pdf_meta = build_comprehensive_artifact_metadata(snapshot)
    pdf_meta["sections"]["report10_cw"]["selected_column_ids"] = ["sno", "division"]

    ok, err = validate_comprehensive_artifact_metadata(excel_meta, pdf_meta, snapshot)
    assert ok is False
    assert "Excel and PDF" in (err or "")


def test_stale_snapshot_hash_rejected():
    sections = _full_sections()
    snapshot = build_comprehensive_column_snapshot(sections, date_from="2026-08-01", date_to="2026-08-01")
    stale_meta = build_comprehensive_artifact_metadata(snapshot, run_id="run-1")
    stale_meta["snapshot_hash"] = "deadbeefdeadbeef"

    fresh_meta = build_comprehensive_artifact_metadata(snapshot, run_id="run-1")
    ok, err = validate_comprehensive_artifact_metadata(
        stale_meta,
        fresh_meta,
        snapshot,
        run_id="run-1",
    )
    assert ok is False
    assert err is not None


def test_date_range_preserved_in_snapshot():
    snapshot = build_comprehensive_column_snapshot(
        _ten_column_sections(),
        date_from="2026-08-01",
        date_to="2026-08-01",
    )
    assert snapshot["date_from"] == "2026-08-01"
    assert snapshot["date_to"] == "2026-08-01"
    hash_a = compute_comprehensive_snapshot_hash(
        snapshot["sections"],
        date_from="2026-08-01",
        date_to="2026-08-01",
    )
    hash_b = compute_comprehensive_snapshot_hash(
        snapshot["sections"],
        date_from="2026-08-02",
        date_to="2026-08-02",
    )
    assert hash_a != hash_b


def test_dual_artifacts_accepts_comprehensive_section_snapshot(tmp_path: Path):
    sections = _full_sections(
        report10_cw=["sno", "division", "received", "closed"],
        report11_security=["sno", "division", "received", "share_percent", "avg_rating"],
    )
    manual_config = build_comprehensive_column_snapshot(
        sections,
        date_from="2026-08-01",
        date_to="2026-08-01",
    )
    meta = build_comprehensive_artifact_metadata(manual_config, run_id="run-xyz")
    excel = _art(tmp_path, meta=meta, artifact_type="excel")
    pdf = _art(tmp_path, meta=meta, artifact_type="pdf")

    ok, err = _dual_artifacts_metadata_consistent(
        excel,
        pdf,
        manual_config,
        run_id="run-xyz",
        report_slug="comprehensive-10-13",
    )
    assert ok is True
    assert err is None


def test_artifacts_for_slug_prefers_matching_snapshot_hash(tmp_path: Path):
    sections = _full_sections()
    snapshot = build_comprehensive_column_snapshot(sections)
    matching = build_comprehensive_artifact_metadata(snapshot, run_id="run-1")
    stale = dict(matching)
    stale["snapshot_hash"] = "stalehash0000000"

    match_art = _art(tmp_path, meta=matching, artifact_type="excel")
    match_art.id = "match"
    stale_art = _art(tmp_path, meta=stale, artifact_type="excel")
    stale_art.id = "stale"

    found = _artifacts_for_slug(
        [stale_art, match_art],
        slug="comprehensive-10-13",
        manual_config=snapshot,
        run_id="run-1",
    )
    assert found["excel"].id == "match"
