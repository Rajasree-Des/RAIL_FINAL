"""Fresh manual extraction helpers for SCR Train (R5) and SCR Station (R6)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from app.automation.config import config
from app.automation.processing.column_config import project_scr_for_output, validate_projection_selection
from app.automation.report_keys import canonicalize_report_key
from app.automation.utils import log_automation_event, resolve_run_scoped_dir

logger = logging.getLogger(__name__)

SCR_MANUAL_SLUGS = frozenset({"scr-train", "scr-station"})


def is_scr_manual_fresh(config: dict[str, object] | None) -> bool:
    if not config:
        return False
    slug = canonicalize_report_key(str(config.get("report_slug") or ""))
    if slug not in SCR_MANUAL_SLUGS:
        return False
    return bool(config.get("force_fresh_extraction")) or config.get("generation_mode") == "fresh_extraction"


async def validate_manual_scr_column_snapshot(
    report_slug: str,
    config_snapshot: dict[str, object],
) -> None:
    """Validate column selection only — preview may use cached data; Generate must not."""
    slug = canonicalize_report_key(report_slug)
    if slug not in SCR_MANUAL_SLUGS:
        raise ValueError(f"Unsupported SCR manual slug: {report_slug}")

    keys = list(
        config_snapshot.get("column_order")
        or config_snapshot.get("selected_column_ids")
        or []
    )
    if not keys:
        raise ValueError("INVALID_SELECTED_COLUMNS: No columns selected")

    validate_projection_selection(slug, keys)

    try:
        project_scr_for_output(
            slug,
            [],
            selected_keys=keys,
            config_source="manual_snapshot",
        )
    except ValueError as exc:
        raise ValueError(str(exc)) from exc


def resolve_scr_extracted_csv_path(report_slug: str, run_id: str) -> Path:
    slug = canonicalize_report_key(report_slug)
    extracted_dir = resolve_run_scoped_dir(config.extracted_data_dir, slug, run_id)
    return extracted_dir / f"{slug}_complaints_raw.csv"


def verify_current_run_source(
    csv_path: Path,
    *,
    run_id: str,
    report_slug: str,
    run_started_at: str | None = None,
) -> None:
    """Reject stale or run-mismatched extraction sources for manual fresh runs."""
    slug = canonicalize_report_key(report_slug)
    if not csv_path.is_file() or csv_path.stat().st_size <= 0:
        raise ValueError(
            f"CURRENT_RUN_SOURCE_MISSING: No extraction CSV for run {run_id} ({slug})"
        )

    path_str = str(csv_path.resolve())
    if run_id not in path_str:
        log_automation_event(
            logger,
            "stale_source_rejected",
            run_id=run_id,
            report_slug=slug,
            source_path=path_str,
            reason="run_id_not_in_path",
        )
        raise ValueError(
            f"STALE_SOURCE_REJECTED: Source path does not belong to run {run_id}: {path_str}"
        )

    if run_started_at:
        try:
            started = datetime.fromisoformat(run_started_at.replace("Z", "+00:00"))
            if started.tzinfo is None:
                started = started.replace(tzinfo=UTC)
            mtime = datetime.fromtimestamp(csv_path.stat().st_mtime, tz=UTC)
            if mtime < started:
                log_automation_event(
                    logger,
                    "stale_source_rejected",
                    run_id=run_id,
                    report_slug=slug,
                    source_path=path_str,
                    reason="mtime_before_run_start",
                    source_mtime=mtime.isoformat(),
                    run_started_at=started.isoformat(),
                )
                raise ValueError(
                    f"STALE_SOURCE_REJECTED: Source modified before run start: {path_str}"
                )
        except ValueError as exc:
            if "STALE_SOURCE_REJECTED" in str(exc):
                raise


def log_manual_fresh_started(
    *,
    run_id: str,
    report_slug: str,
    config_snapshot: dict[str, object],
) -> None:
    keys = list(
        config_snapshot.get("column_order")
        or config_snapshot.get("selected_column_ids")
        or []
    )
    log_automation_event(
        logger,
        "manual_report_run_started",
        run_id=run_id,
        report_slug=report_slug,
        report_date=config_snapshot.get("report_date"),
        selected_column_ids=keys,
        selected_column_count=len(keys),
        configuration_source=config_snapshot.get("configuration_source"),
    )
    log_automation_event(
        logger,
        "fresh_extraction_forced",
        run_id=run_id,
        report_slug=report_slug,
    )
