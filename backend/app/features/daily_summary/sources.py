"""Load and validate current-run CSV sources for daily summary."""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.automation.run_registry import is_under_storage
from app.features.daily_summary import SUMMARY_SOURCE_SLUGS, TERMINAL_REPORT_STATUSES
from app.infrastructure.database.models import AutomationRunModel

logger = logging.getLogger(__name__)


@dataclass
class ReportSource:
    slug: str
    status: str
    source_csv_path: str | None = None
    source_paths: list[str] = field(default_factory=list)
    row_counts: dict[str, Any] = field(default_factory=dict)
    available: bool = False
    validation_error: str | None = None
    rows: list[dict[str, str]] = field(default_factory=list)
    type_datasets: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    section_datasets: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    excel_path: str | None = None


@dataclass
class RunSources:
    run_id: str
    user_id: str | None
    run_status: str
    reports: dict[str, ReportSource]
    missing_reports: list[str] = field(default_factory=list)
    validation_notes: list[str] = field(default_factory=list)
    all_terminal: bool = False


def _parse_result_json(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [{k: (v or "") for k, v in row.items()} for row in reader]


def _safe_path(path_str: str | None) -> Path | None:
    if not path_str:
        return None
    path = Path(path_str)
    if not path.is_file():
        return None
    if not is_under_storage(path):
        logger.warning("daily_summary_path_outside_storage path=%s", path)
        return None
    return path


def resolve_run_sources(run: AutomationRunModel) -> RunSources:
    """Resolve report sources strictly from this run's result_json."""
    result = _parse_result_json(run.result_json)
    reports_raw = result.get("reports") or []
    by_slug: dict[str, ReportSource] = {}

    for entry in reports_raw:
        if not isinstance(entry, dict):
            continue
        slug = str(entry.get("slug") or "").strip()
        if not slug:
            continue
        status = str(entry.get("status") or "").strip().lower()
        source_csv = entry.get("source_csv_path")
        source_paths = entry.get("source_paths") or []
        if isinstance(source_paths, list):
            paths = [str(p) for p in source_paths if p]
        else:
            paths = []
        row_counts = entry.get("row_counts") or {}
        if not isinstance(row_counts, dict):
            row_counts = {}
        excel_path = entry.get("excel_path") or entry.get("output_excel_path")
        by_slug[slug] = ReportSource(
            slug=slug,
            status=status,
            source_csv_path=str(source_csv) if source_csv else None,
            source_paths=paths,
            row_counts=row_counts,
            excel_path=str(excel_path) if excel_path else None,
        )

    sources = RunSources(
        run_id=run.id,
        user_id=run.created_by,
        run_status=str(run.status or ""),
        reports=by_slug,
    )

    all_statuses = [r.status for r in by_slug.values()]
    sources.all_terminal = bool(all_statuses) and all(
        s in TERMINAL_REPORT_STATUSES for s in all_statuses
    )

    for slug in SUMMARY_SOURCE_SLUGS:
        if slug not in by_slug:
            sources.missing_reports.append(slug)
            sources.validation_notes.append(f"{slug}: not present in run result")
            continue
        report = by_slug[slug]
        if report.status not in TERMINAL_REPORT_STATUSES:
            sources.validation_notes.append(f"{slug}: non-terminal status {report.status}")
            sources.missing_reports.append(slug)
            continue
        if report.status in {"failed", "skipped"} and not report.source_csv_path:
            sources.missing_reports.append(slug)
            report.validation_error = f"status={report.status}"
            sources.validation_notes.append(f"{slug}: {report.validation_error}")
            continue
        _load_report_data(report, sources)

    return sources


def _load_report_data(report: ReportSource, sources: RunSources) -> None:
    slug = report.slug
    if slug == "types":
        _load_types(report, sources)
        return
    if slug == "report9":
        _load_indexed_sections(
            report,
            sources,
            index_key="source_id",
            dataset_label="report9",
        )
        return
    if slug == "comprehensive-10-13":
        _load_indexed_sections(
            report,
            sources,
            index_key="section_id",
            dataset_label="comprehensive-10-13",
        )
        return

    path = _safe_path(report.source_csv_path)
    if path is None and report.source_paths:
        path = _safe_path(report.source_paths[0])
    if path is None:
        expected = report.row_counts.get("expected")
        if slug in {"scr-train", "scr-station"} and expected == 0:
            report.available = True
            report.rows = []
            return
        report.validation_error = "source CSV missing or outside storage"
        sources.missing_reports.append(slug)
        sources.validation_notes.append(f"{slug}: {report.validation_error}")
        return

    try:
        rows = read_csv_rows(path)
    except OSError as exc:
        report.validation_error = f"failed to read CSV: {exc}"
        sources.missing_reports.append(slug)
        sources.validation_notes.append(f"{slug}: {report.validation_error}")
        return

    if slug == "scr-train":
        ok, note = _validate_mode(rows, "Train")
        if not ok:
            report.validation_error = note
            sources.missing_reports.append(slug)
            sources.validation_notes.append(f"{slug}: {note}")
            return
    if slug == "scr-station":
        ok, note = _validate_mode(rows, "Station")
        if not ok:
            report.validation_error = note
            sources.missing_reports.append(slug)
            sources.validation_notes.append(f"{slug}: {note}")
            return

    report.rows = rows
    report.available = True
    report.source_csv_path = str(path)


def _load_indexed_sections(
    report: ReportSource,
    sources: RunSources,
    *,
    index_key: str,
    dataset_label: str,
) -> None:
    index_path = _safe_path(report.source_csv_path)
    if index_path is None and report.source_paths:
        index_path = _safe_path(report.source_paths[0])
    if index_path is None:
        report.validation_error = f"{dataset_label} combined index missing"
        sources.missing_reports.append(report.slug)
        sources.validation_notes.append(f"{report.slug}: {report.validation_error}")
        return

    try:
        index_rows = read_csv_rows(index_path)
    except OSError as exc:
        report.validation_error = f"failed to read index: {exc}"
        sources.missing_reports.append(report.slug)
        sources.validation_notes.append(f"{report.slug}: {report.validation_error}")
        return

    loaded: dict[str, list[dict[str, str]]] = {}
    for entry in index_rows:
        section_id = (entry.get(index_key) or "").strip()
        status = (entry.get("status") or "").strip().lower()
        csv_path = (entry.get("csv_path") or "").strip()
        if not section_id or status != "success":
            continue
        path = _safe_path(csv_path)
        if path is None:
            sources.validation_notes.append(f"{report.slug}/{section_id}: csv missing")
            continue
        try:
            loaded[section_id] = read_csv_rows(path)
        except OSError as exc:
            sources.validation_notes.append(f"{report.slug}/{section_id}: {exc}")

    if not loaded:
        report.validation_error = f"no successful {dataset_label} section CSVs for this run"
        sources.missing_reports.append(report.slug)
        sources.validation_notes.append(f"{report.slug}: {report.validation_error}")
        return

    report.section_datasets = loaded
    report.available = True
    report.source_csv_path = str(index_path)


def _validate_mode(rows: list[dict[str, str]], expected: str) -> tuple[bool, str]:
    from app.automation.formatting.scr import mode_matches

    if not rows:
        return True, ""
    mode_key = next((k for k in rows[0] if k.lower() == "mode"), None)
    if mode_key is None:
        return True, ""
    wrong = [
        row for row in rows if row.get(mode_key) and not mode_matches(expected, row.get(mode_key, ""))
    ]
    if wrong:
        return False, f"mode mix-up: expected {expected}, found other modes"
    return True, ""


def _load_types(report: ReportSource, sources: RunSources) -> None:
    index_path = _safe_path(report.source_csv_path)
    if index_path is None:
        report.validation_error = "types_combined_index.csv missing"
        sources.missing_reports.append("types")
        sources.validation_notes.append(f"types: {report.validation_error}")
        return

    run_id = sources.run_id
    if run_id and run_id not in str(index_path):
        sources.validation_notes.append(
            f"types: index path does not include run_id={run_id} (still using run result_json path)"
        )

    try:
        index_rows = read_csv_rows(index_path)
    except OSError as exc:
        report.validation_error = f"failed to read index: {exc}"
        sources.missing_reports.append("types")
        sources.validation_notes.append(f"types: {report.validation_error}")
        return

    loaded: dict[str, list[dict[str, str]]] = {}
    for entry in index_rows:
        type_name = (entry.get("type_name") or "").strip()
        status = (entry.get("status") or "").strip().lower()
        csv_path = (entry.get("csv_path") or "").strip()
        if not type_name or status != "success":
            continue
        path = _safe_path(csv_path)
        if path is None:
            sources.validation_notes.append(f"types/{type_name}: csv missing")
            continue
        try:
            loaded[type_name] = read_csv_rows(path)
        except OSError as exc:
            sources.validation_notes.append(f"types/{type_name}: {exc}")

    if not loaded:
        report.validation_error = "no successful type CSVs for this run"
        sources.missing_reports.append("types")
        sources.validation_notes.append(f"types: {report.validation_error}")
        return

    report.type_datasets = loaded
    report.available = True
    report.source_csv_path = str(index_path)
