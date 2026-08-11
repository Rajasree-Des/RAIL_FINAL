"""Tests for Top-N output column catalog and projection (Reports 3 and 4)."""

from __future__ import annotations

from app.automation.processing.topn_output_columns import (
    TOPN_REPORT_SLUGS,
    migrate_topn_to_namespaced_ids,
    topn_allowed_ids,
    topn_catalog_entries,
    topn_default_ids,
    topn_labels,
)


def test_train_no_catalog_has_eleven_fields():
    entries = topn_catalog_entries("train-no")
    assert len(entries) == 11
    ids = {entry["id"] for entry in entries}
    assert ids == topn_allowed_ids("train-no")


def test_types_catalog_has_eleven_fields():
    entries = topn_catalog_entries("types")
    assert len(entries) == 11
    ids = {entry["id"] for entry in entries}
    assert ids == topn_allowed_ids("types")


def test_default_ids_are_independent():
    train_defaults = topn_default_ids("train-no")
    types_defaults = topn_default_ids("types")
    assert len(train_defaults) == 11
    assert len(types_defaults) == 11
    assert all(key.startswith("train-no.") for key in train_defaults)
    assert all(key.startswith("types.") for key in types_defaults)


def test_migrate_legacy_labels_to_namespaced_ids():
    migrated = migrate_topn_to_namespaced_ids(
        "train-no",
        ["Train Name", "Train No.", "Received", "Average Rating"],
    )
    assert migrated == [
        "train-no.train_name",
        "train-no.train_no",
        "train-no.received",
        "train-no.average_rating",
    ]


def test_cross_report_ids_are_dropped_on_migration():
    migrated = migrate_topn_to_namespaced_ids(
        "types",
        ["types.train_name", "train-no.received"],
    )
    assert migrated == ["types.train_name"]


def test_topn_report_slugs_include_aliases():
    assert "train-no" in TOPN_REPORT_SLUGS
    assert "report3" in TOPN_REPORT_SLUGS
    assert "types" in TOPN_REPORT_SLUGS
    assert "report4" in TOPN_REPORT_SLUGS


def test_labels_match_catalog():
    defaults = topn_default_ids("train-no")
    labels = topn_labels(defaults, "train-no")
    assert labels[0] == "S.No."
    assert labels[1] == "Train No."
    assert labels[2] == "Train Name"
    assert "Average Rating" in labels


def test_report3_catalog_places_train_no_after_sno():
    entries = topn_catalog_entries("train-no")
    ids = [entry["id"] for entry in entries]
    assert ids.index("train-no.sno") == 0
    assert ids.index("train-no.train_no") == 1
    assert ids.index("train-no.train_name") == 2


def test_types_catalog_keeps_train_no_after_owning_division():
    entries = topn_catalog_entries("types")
    ids = [entry["id"] for entry in entries]
    assert ids.index("types.train_name") < ids.index("types.train_no")
    assert ids.index("types.owning_division") < ids.index("types.train_no")


def test_ensure_report3_train_no_after_sno_reorders_selection():
    from app.automation.processing.topn_output_columns import ensure_report3_train_no_after_sno

    selected = [
        "train-no.sno",
        "train-no.train_name",
        "train-no.owning_zone",
        "train-no.owning_division",
        "train-no.train_no",
    ]
    assert ensure_report3_train_no_after_sno(selected, "train-no") == [
        "train-no.sno",
        "train-no.train_no",
        "train-no.train_name",
        "train-no.owning_zone",
        "train-no.owning_division",
    ]
    # Report 5 / types must not be reordered by this helper
    types_selected = [
        "types.sno",
        "types.train_name",
        "types.owning_zone",
        "types.owning_division",
        "types.train_no",
    ]
    assert ensure_report3_train_no_after_sno(types_selected, "types") == types_selected