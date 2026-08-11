"""Tests for runtime output column configuration and projection."""

from __future__ import annotations

import pytest

from app.automation.processing.column_config import (
    project_for_output,
    resolve_projection_column_keys,
    sanitize_projection_keys,
    validate_projection_selection,
    migrate_output_column_keys,
)
from app.automation.processing.output_columns import (
    REPORT1_DEFAULT_NAMESPACED_KEYS,
    REPORT1_NAMESPACED_IDS,
    REPORT5_OUTPUT_COLUMNS,
    SOURCE_B_DATA_COLUMNS,
    migrate_to_namespaced_ids,
)
from app.automation.run_context import RunContext, reset_run_context, set_run_context
from app.automation.timing import RunTiming


def _ctx(**kwargs) -> RunContext:
    run_id = kwargs.pop("run_id", "run-test")
    return RunContext(run_id=run_id, timing=RunTiming(run_id=run_id), **kwargs)


def test_manual_snapshot_preserves_subset_selection():
    subset = [
        "report1.source_a.organisation",
        "report1.source_a.received",
        "report1.source_b.feedback_received",
    ]
    ctx = _ctx(
        manual_config={
            "report_slug": "report1",
            "column_order": subset,
        },
    )
    token = set_run_context(ctx)
    try:
        keys, source = resolve_projection_column_keys("report1")
        assert source == "manual_snapshot"
        assert keys == subset
    finally:
        reset_run_context(token)


def test_saved_config_used_when_no_manual_snapshot(monkeypatch):
    monkeypatch.setattr(
        "app.features.reports.config_store.load_report_config",
        lambda slug, user_id=None: {
            "column_order": list(REPORT1_DEFAULT_NAMESPACED_KEYS),
        },
    )
    token = set_run_context(_ctx())
    try:
        keys, source = resolve_projection_column_keys("report1")
        assert source == "saved_user_config"
        assert keys == REPORT1_DEFAULT_NAMESPACED_KEYS
    finally:
        reset_run_context(token)


def test_defaults_when_no_manual_or_saved(monkeypatch):
    monkeypatch.setattr(
        "app.features.reports.config_store.load_report_config",
        lambda slug, user_id=None: None,
    )
    token = set_run_context(_ctx())
    try:
        keys, source = resolve_projection_column_keys("report1")
        assert source == "report_default"
        assert keys == REPORT1_DEFAULT_NAMESPACED_KEYS
    finally:
        reset_run_context(token)


def test_sanitize_projection_keys_does_not_expand_selection():
    sanitized = sanitize_projection_keys(
        ["report1.source_a.sno", "report1.source_a.organisation", "report1.source_a.received"],
        "report1",
    )
    assert sanitized == [
        "report1.source_a.sno",
        "report1.source_a.organisation",
        "report1.source_a.received",
    ]


def test_validate_projection_selection_requires_at_least_one():
    with pytest.raises(ValueError, match="at least one"):
        validate_projection_selection("report1", [])


def test_validate_projection_selection_rejects_unknown_ids():
    with pytest.raises(ValueError, match="approved allowlist"):
        validate_projection_selection(
            "report1",
            ["report1.source_a.organisation", "serialNo"],
        )


def test_project_for_output_uses_valid_manual_selection():
    source_a = [
        "S.No.",
        "Organisation",
        "Opening Balance",
        "Received",
        "% Share",
        "Closed",
        "Closing Balance",
        "% Disposal",
        "Avg. Disposal Time",
        "Avg. Rating",
        "Avg. Pendency Time",
        "Forwarded",
        "Avg. FRT",
    ]
    full_headers = source_a + ["S.No.", "Organisation"] + list(SOURCE_B_DATA_COLUMNS)
    ctx = _ctx(
        manual_config={
            "report_slug": "report1",
            "column_order": [
                "report1.source_a.organisation",
                "report1.source_a.received",
                "report1.source_b.feedback_received",
            ],
        },
    )
    token = set_run_context(ctx)
    try:
        headers, out_rows, labels, keys, _source = project_for_output(
            "report1",
            full_headers=full_headers,
            rows=[
                ["1", "Alpha", "0", "5", "0", "0", "0", "0", "0", "0", "0", "0", "0", "1", "Alpha", "3", "0", "0", "0", "0", "0"],
                ["", "Total", "", "5", "", "", "", "", "", "", "", "", "", "", "Total", "3", "", "", "", "", ""],
            ],
        )
        assert keys == [
            "report1.source_a.organisation",
            "report1.source_a.received",
            "report1.source_b.feedback_received",
        ]
        assert headers == ["Organisation", "Received", "Feedback Received"]
        assert out_rows[0] == ["Alpha", "5", "3"]
    finally:
        reset_run_context(token)


def test_project_for_output_allows_subset():
    source_a = [
        "S.No.",
        "Organisation",
        "Opening Balance",
        "Received",
        "% Share",
        "Closed",
        "Closing Balance",
        "% Disposal",
        "Avg. Disposal Time",
        "Avg. Rating",
        "Avg. Pendency Time",
        "Forwarded",
        "Avg. FRT",
    ]
    full_headers = source_a + ["S.No.", "Organisation"] + list(SOURCE_B_DATA_COLUMNS)
    ctx = _ctx(
        manual_config={
            "report_slug": "report1",
            "column_order": ["report1.source_a.received"],
        },
    )
    token = set_run_context(ctx)
    try:
        headers, out_rows, labels, keys, _source = project_for_output(
            "report1",
            full_headers=full_headers,
            rows=[["1", "Alpha", "0", "5", "0", "0", "0", "0", "0", "0", "0", "0", "0", "1", "Alpha", "3", "0", "0", "0", "0", "0"]],
        )
        assert keys == ["report1.source_a.received"]
        assert headers == ["Received"]
    finally:
        reset_run_context(token)


def test_migrate_to_namespaced_ids_from_legacy():
    migrated = migrate_to_namespaced_ids(
        "report1",
        ["serialNo", "organisation", "feedbackReceived"],
    )
    assert migrated == [
        "report1.source_a.sno",
        "report1.source_a.organisation",
        "report1.source_b.feedback_received",
    ]


def test_namespaced_catalog_has_21_ids():
    assert len(REPORT1_NAMESPACED_IDS) == 21


def test_scr_report5_allows_flexible_subset():
    subset = [
        "scr-train.complaint_ref_no",
        "scr-train.created_on",
        "scr-train.train_station",
    ]
    validate_projection_selection("scr-train", subset)


def test_migrate_output_column_keys_from_labels_scr_only():
    keys = migrate_output_column_keys(
        ["Complaint Ref Number", "Created On"],
        REPORT5_OUTPUT_COLUMNS,
    )
    assert keys == ["complaintRefNo", "createdOn"]


def test_bottom_report_ignores_column_selection():
    from app.automation.processing.column_config import (
        is_columnless_manual_report,
        validate_column_order,
    )
    from app.features.reports.schemas import ManualGenerateRequest
    from app.features.reports.service import build_config_snapshot

    assert is_columnless_manual_report("bottom-report")

    body = ManualGenerateRequest(
        date_from="2026-08-01",
        date_to="2026-08-10",
        selected_column_ids=["serialNo", "organisation"],
        column_order=["serialNo", "organisation"],
    )
    snapshot = build_config_snapshot(body, report_slug="bottom-report")
    assert snapshot["selected_column_ids"] == []
    assert snapshot["column_order"] == []

    validate_column_order("bottom-report", [], ["serialNo", "organisation"])
