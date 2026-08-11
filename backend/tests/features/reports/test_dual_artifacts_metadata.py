"""Current-run dual artifact metadata must reject stale column/run mismatches."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.automation.run_registry import build_dual_artifact_metadata
from app.features.reports.service import _dual_artifacts_metadata_consistent


def _art(tmp_path: Path, *, slug: str, meta: dict) -> SimpleNamespace:
    path = tmp_path / f"{slug}.xlsx"
    path.write_bytes(b"x")
    return SimpleNamespace(
        report_slug=slug,
        file_path=str(path),
        metadata_json=__import__("json").dumps(meta),
    )


def test_build_dual_artifact_metadata_includes_run_id():
    meta = build_dual_artifact_metadata(
        selected_column_ids=["a", "b"],
        column_order=["a", "b"],
        run_id="run-1",
        report_slug="report1",
    )
    assert meta["run_id"] == "run-1"
    assert meta["report_slug"] == "report1"
    assert meta["column_order"] == ["a", "b"]


def test_dual_artifacts_reject_stale_run_id(tmp_path: Path):
    cols = ["report1.source_a.organisation"]
    meta_ok = build_dual_artifact_metadata(
        selected_column_ids=cols,
        column_order=cols,
        run_id="current-run",
        report_slug="report1",
    )
    meta_stale = dict(meta_ok)
    meta_stale["run_id"] = "old-run"

    excel = _art(tmp_path, slug="report1", meta=meta_ok)
    pdf = _art(tmp_path, slug="report1", meta=meta_stale)
    ok, _ = _dual_artifacts_metadata_consistent(
        excel,
        pdf,
        {"column_order": cols},
        run_id="current-run",
        report_slug="report1",
    )
    assert ok is False


def test_dual_artifacts_accept_matching_current_run(tmp_path: Path):
    cols = ["division.source.division", "division.source.received"]
    meta = build_dual_artifact_metadata(
        selected_column_ids=cols,
        column_order=cols,
        run_id="run-xyz",
        report_slug="division",
    )
    excel = _art(tmp_path, slug="division", meta=meta)
    pdf = _art(tmp_path, slug="division", meta=meta)
    ok, err = _dual_artifacts_metadata_consistent(
        excel,
        pdf,
        {"column_order": cols, "selected_column_ids": cols},
        run_id="run-xyz",
        report_slug="division",
    )
    assert ok is True
    assert err is None


def test_dual_artifacts_reject_column_order_mismatch(tmp_path: Path):
    meta = build_dual_artifact_metadata(
        selected_column_ids=["a"],
        column_order=["a"],
        run_id="run-1",
        report_slug="types",
    )
    excel = _art(tmp_path, slug="types", meta=meta)
    pdf = _art(tmp_path, slug="types", meta=meta)
    ok, _ = _dual_artifacts_metadata_consistent(
        excel,
        pdf,
        {"column_order": ["b"]},
        run_id="run-1",
        report_slug="types",
    )
    assert ok is False
