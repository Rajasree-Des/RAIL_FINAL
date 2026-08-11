"""Verify Daily Summary API routes are registered and return expected codes."""

from __future__ import annotations

import importlib

from app.features.daily_summary.controller import router as daily_summary_router


def test_daily_summary_routes_registered():
    paths = {getattr(r, "path", "") for r in daily_summary_router.routes}
    assert "/automation/runs/{run_id}/summary" in paths
    assert "/automation/runs/{run_id}/summary/regenerate" in paths
    router_mod = importlib.import_module("app.api.v1.router")
    assert hasattr(router_mod, "daily_summary_router")


def test_summary_not_generated_error_code():
    from app.core.exceptions import SummaryNotGeneratedError

    exc = SummaryNotGeneratedError("run-abc")
    assert exc.code == "SUMMARY_NOT_GENERATED"
    assert "run-abc" in exc.message
