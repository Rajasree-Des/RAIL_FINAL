"""Run timing spans for profiling full automation runs."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from app.automation.config import config
from app.automation.utils import ensure_directory, log_automation_event
import logging

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class SpanRecord:
    name: str
    started_at: str
    completed_at: str | None = None
    duration_seconds: float | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReportTiming:
    slug: str
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float | None = None
    extraction_seconds: float | None = None
    processing_seconds: float | None = None
    spans: dict[str, float] = field(default_factory=dict)


@dataclass
class RunTiming:
    """Accumulates wall-clock timings for one full automation run."""

    run_id: str
    started_at: str = field(default_factory=_now_iso)
    completed_at: str | None = None
    total_duration_seconds: float | None = None
    spans: dict[str, float] = field(default_factory=dict)
    reports: dict[str, ReportTiming] = field(default_factory=dict)
    fixed_sleep_seconds: float = 0.0
    fixed_sleep_events: list[dict[str, Any]] = field(default_factory=list)
    retry_count: int = 0
    _active: dict[str, float] = field(default_factory=dict, repr=False)

    def record_fixed_sleep(self, seconds: float, *, reason: str = "") -> None:
        if seconds <= 0:
            return
        self.fixed_sleep_seconds = round(self.fixed_sleep_seconds + seconds, 3)
        if reason:
            self.fixed_sleep_events.append(
                {"reason": reason, "seconds": round(seconds, 3)}
            )

    def record_retry(self, *, reason: str = "") -> None:
        self.retry_count += 1
        log_automation_event(logger, "timing_retry", run_id=self.run_id, reason=reason)

    def start_span(self, name: str) -> None:
        self._active[name] = time.perf_counter()

    def end_span(self, name: str, **meta: Any) -> float:
        start = self._active.pop(name, None)
        if start is None:
            return 0.0
        elapsed = time.perf_counter() - start
        self.spans[name] = round(elapsed, 3)
        log_automation_event(
            logger,
            "timing_span",
            span=name,
            duration_seconds=self.spans[name],
            **meta,
        )
        return elapsed

    @contextmanager
    def span(self, name: str, **meta: Any) -> Iterator[None]:
        self.start_span(name)
        try:
            yield
        finally:
            self.end_span(name, **meta)

    @contextmanager
    def report_span(self, slug: str, span_name: str, **meta: Any) -> Iterator[None]:
        """Record both top-level `span_name:slug` and per-report span maps."""
        full = f"{span_name}:{slug}"
        self.start_span(full)
        try:
            yield
        finally:
            elapsed = self.end_span(full, slug=slug, **meta)
            self.record_report_span(slug, span_name, elapsed)

    def ensure_report(self, slug: str) -> ReportTiming:
        if slug not in self.reports:
            self.reports[slug] = ReportTiming(slug=slug)
        return self.reports[slug]

    def start_report(self, slug: str) -> None:
        rt = self.ensure_report(slug)
        rt.started_at = _now_iso()
        self.start_span(f"report:{slug}")
        log_automation_event(logger, "report_started", slug=slug, run_id=self.run_id)

    def end_report(self, slug: str, **meta: Any) -> None:
        rt = self.ensure_report(slug)
        rt.completed_at = _now_iso()
        elapsed = self.end_span(f"report:{slug}", slug=slug, **meta)
        rt.duration_seconds = round(elapsed, 3)
        log_automation_event(
            logger,
            "report_completed",
            slug=slug,
            run_id=self.run_id,
            duration_seconds=rt.duration_seconds,
            **meta,
        )

    def record_report_span(self, slug: str, span_name: str, seconds: float) -> None:
        rt = self.ensure_report(slug)
        rt.spans[span_name] = round(seconds, 3)
        if span_name == "extraction":
            rt.extraction_seconds = round(seconds, 3)
        elif span_name == "processing":
            rt.processing_seconds = round(seconds, 3)

    def finish(self) -> dict[str, Any]:
        self.completed_at = _now_iso()
        start = datetime.fromisoformat(self.started_at)
        end = datetime.fromisoformat(self.completed_at)
        self.total_duration_seconds = round((end - start).total_seconds(), 3)
        payload = self.to_dict()
        perf = self.build_performance_report()
        log_automation_event(
            logger,
            "full_run_completed",
            run_id=self.run_id,
            total_duration_seconds=self.total_duration_seconds,
            report_count=len(self.reports),
            portal_wait_seconds=perf.get("portal_wait_seconds"),
            application_seconds=perf.get("application_seconds"),
            fixed_sleep_seconds=perf.get("fixed_sleep_seconds"),
        )
        self.write_json()
        self.write_performance_json(perf)
        import os

        perf_label = os.environ.get("AUTOMATION_PERF_LABEL", "").strip()
        if perf_label:
            self.write_labeled_performance_json(perf, perf_label)
        else:
            self.write_labeled_performance_json(perf, "after")
        return payload

    _PORTAL_SPAN_PREFIXES = (
        "browser_connect",
        "nav_filter_submit",
        "sorting",
        "extraction",
        "feedback_extraction",
        "handler_execute",
        "report:",
        "phase6_pdf_download",
        "archive",
        "comprehensive_regenerate",
    )
    _APP_SPAN_PREFIXES = (
        "ingestion",
        "processing",
        "excel_generation",
        "pdf_generation",
        "ingestion_feedback",
    )

    def build_performance_report(self) -> dict[str, Any]:
        portal = 0.0
        app = 0.0
        for name, seconds in self.spans.items():
            if any(name.startswith(p) for p in self._APP_SPAN_PREFIXES):
                app += seconds
            elif any(name.startswith(p) or p in name for p in self._PORTAL_SPAN_PREFIXES):
                portal += seconds
            else:
                portal += seconds
        per_report = {
            slug: {
                "duration_seconds": rt.duration_seconds,
                "extraction_seconds": rt.extraction_seconds,
                "processing_seconds": rt.processing_seconds,
                "spans": dict(rt.spans),
            }
            for slug, rt in self.reports.items()
            if rt.duration_seconds is not None
        }
        critical = max(
            per_report.items(),
            key=lambda item: item[1].get("duration_seconds") or 0,
            default=(None, {}),
        )
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_duration_seconds": self.total_duration_seconds,
            "portal_wait_seconds": round(portal, 3),
            "application_seconds": round(app, 3),
            "fixed_sleep_seconds": self.fixed_sleep_seconds,
            "fixed_sleep_events": list(self.fixed_sleep_events),
            "retry_count": self.retry_count,
            "spans": dict(self.spans),
            "per_report": per_report,
            "critical_path_report": critical[0],
            "critical_path_seconds": critical[1].get("duration_seconds"),
            "top_bottlenecks": sorted(
                self.spans.items(), key=lambda x: x[1], reverse=True
            )[:5],
        }

    def write_performance_json(self, payload: dict[str, Any]) -> Path:
        debug_dir = ensure_directory(Path(config.extracted_data_dir).parent / "debug")
        path = debug_dir / f"performance_{self.run_id}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def write_labeled_performance_json(
        self, payload: dict[str, Any], label: str
    ) -> Path:
        """Write performance snapshot as performance_{label}_{run_id}.json."""
        debug_dir = ensure_directory(Path(config.extracted_data_dir).parent / "debug")
        safe = label.strip().replace(" ", "_")
        path = debug_dir / f"performance_{safe}_{self.run_id}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_duration_seconds": self.total_duration_seconds,
            "spans": dict(self.spans),
            "reports": {
                slug: {
                    "slug": rt.slug,
                    "started_at": rt.started_at,
                    "completed_at": rt.completed_at,
                    "duration_seconds": rt.duration_seconds,
                    "extraction_seconds": rt.extraction_seconds,
                    "processing_seconds": rt.processing_seconds,
                    "spans": dict(rt.spans),
                }
                for slug, rt in self.reports.items()
            },
        }

    def write_json(self) -> Path:
        debug_dir = ensure_directory(Path(config.extracted_data_dir).parent / "debug")
        path = debug_dir / f"run_timing_{self.run_id}.json"
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path
