"""Shared automation utilities."""

import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


def previous_day_report_date(
    *,
    fmt: str = "%d-%m-%Y",
    now: datetime | None = None,
) -> str:
    """Return report_date = current_date - 1 day (for titles/filenames/metadata)."""
    moment = now or datetime.now()
    return (moment - timedelta(days=1)).strftime(fmt)


def artifact_filename_timestamp(*, now: datetime | None = None) -> str:
    """Intermediate artifact stamp: previous-day date + current clock time."""
    moment = now or datetime.now()
    report_day = moment - timedelta(days=1)
    return f"{report_day.strftime('%Y-%m-%d')}_{moment.strftime('%H-%M-%S')}"

# Keys reserved on logging.LogRecord — must not appear in logger.info(..., extra={...}).
_RESERVED_LOGRECORD_KEYS = frozenset(
    {
        "name",
        "msg",
        "args",
        "created",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "thread",
        "threadName",
        "exc_info",
        "exc_text",
        "stack_info",
        "taskName",
    }
)

# Preferred safe aliases for common automation structured fields.
_LOG_FIELD_ALIASES = {
    "name": "field_name",
    "type": "field_type",
    "label": "field_label",
    "value": "field_value",
    "id": "field_id",
}


def _safe_log_key(key: str) -> str:
    """Return a LogRecord-safe structured logging key."""
    if key in _LOG_FIELD_ALIASES:
        return _LOG_FIELD_ALIASES[key]
    if key in _RESERVED_LOGRECORD_KEYS:
        return f"log_{key}"
    return key


def _sanitize_log_extra(fields: dict[str, object]) -> dict[str, object]:
    """Rename keys that collide with LogRecord reserved attributes."""
    sanitized: dict[str, object] = {}
    for key, value in fields.items():
        sanitized[_safe_log_key(key)] = value
    return sanitized


def ensure_directory(path: Path) -> Path:
    """Create a directory if it does not exist and return the path."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_report_dir(base_dir: str | Path, report_slug: str) -> Path:
    """Resolve per-report storage dir without double-appending slug."""
    base = Path(base_dir)
    return base if base.name == report_slug else base / report_slug


def resolve_run_scoped_dir(base_dir: str | Path, report_slug: str, run_id: str) -> Path:
    """Resolve run-scoped storage dir: base/<slug>/<run_id>/"""
    return resolve_report_dir(base_dir, report_slug) / run_id


def normalize_url(url: str) -> str:
    """Normalize a URL for comparison (lowercase host, no trailing slash)."""
    return url.rstrip("/").lower()


def log_automation_event(logger: logging.Logger, event: str, **fields: object) -> None:
    """Emit a structured automation log line with consistent extra fields."""
    safe_fields = _sanitize_log_extra(fields)
    extra = _sanitize_log_extra({"automation_event": event, **safe_fields})
    parts = [f"{key}={value}" for key, value in safe_fields.items()]
    message = event if not parts else f"{event} | {' | '.join(parts)}"
    logger.info(message, extra=extra)
