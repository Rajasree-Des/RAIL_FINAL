"""Shared report date-range model and helpers (Asia/Kolkata calendar boundaries)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from app.automation.config import config

logger = logging.getLogger(__name__)

DEFAULT_TIMEZONE = "Asia/Kolkata"
DISPLAY_DATE_FMT = "%d-%m-%Y"
ISO_DATE_FMT = "%Y-%m-%d"
PORTAL_DATE_FMT = config.date_format

ResolutionSource = Literal["frontend", "backend_default"]


class DateRangeValidationError(ValueError):
    """Raised when date_from/date_to are invalid."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class DateRangeSnapshot:
    """Immutable run-level date range frozen at automation start."""

    run_id: str
    date_from: date
    date_to: date
    timezone: str = DEFAULT_TIMEZONE

    @classmethod
    def from_range(
        cls,
        run_id: str,
        date_range: ReportDateRange,
        *,
        tz: str = DEFAULT_TIMEZONE,
    ) -> DateRangeSnapshot:
        return cls(
            run_id=run_id,
            date_from=date_range.date_from,
            date_to=date_range.date_to,
            timezone=tz,
        )

    def to_report_date_range(self) -> ReportDateRange:
        return ReportDateRange(date_from=self.date_from, date_to=self.date_to)

    def iso_from(self) -> str:
        return self.date_from.isoformat()

    def iso_to(self) -> str:
        return self.date_to.isoformat()

    def as_dict(self) -> dict[str, str]:
        return {
            "date_from": self.iso_from(),
            "date_to": self.iso_to(),
            "timezone": self.timezone,
        }


def log_global_date_range_resolved(
    snapshot: DateRangeSnapshot,
    *,
    resolution_source: ResolutionSource = "backend_default",
) -> None:
    from app.automation.utils import log_automation_event

    log_automation_event(
        logger,
        "global_date_range_resolved",
        run_id=snapshot.run_id,
        date_from=snapshot.iso_from(),
        date_to=snapshot.iso_to(),
        timezone=snapshot.timezone,
        resolution_source=resolution_source,
    )


@dataclass(frozen=True)
class ReportDateRange:
    """Immutable report date range (inclusive calendar days in project timezone)."""

    date_from: date
    date_to: date

    def __post_init__(self) -> None:
        if self.date_from > self.date_to:
            raise DateRangeValidationError(
                "INVALID_DATE_RANGE",
                "date_from must be on or before date_to",
            )

    @classmethod
    def default_global_range(
        cls,
        tz: str = DEFAULT_TIMEZONE,
        *,
        moment: datetime | None = None,
    ) -> ReportDateRange:
        """Global default: yesterday through today (Asia/Kolkata)."""
        today = _calendar_today(tz, moment=moment)
        yesterday = today - timedelta(days=1)
        return cls(date_from=yesterday, date_to=today)

    @classmethod
    def default_previous_day(
        cls,
        tz: str = DEFAULT_TIMEZONE,
        *,
        moment: datetime | None = None,
    ) -> ReportDateRange:
        """Default: previous calendar day for both ends (Asia/Kolkata)."""
        day = _previous_calendar_day(tz, moment=moment)
        return cls(date_from=day, date_to=day)

    @classmethod
    def from_iso(cls, date_from: str, date_to: str) -> ReportDateRange:
        try:
            start = date.fromisoformat(date_from)
            end = date.fromisoformat(date_to)
        except ValueError as exc:
            raise DateRangeValidationError(
                "INVALID_DATE_RANGE",
                "date_from and date_to must be YYYY-MM-DD",
            ) from exc
        return cls(date_from=start, date_to=end)

    @classmethod
    def from_request(
        cls,
        date_from: str | None,
        date_to: str | None,
        *,
        tz: str = DEFAULT_TIMEZONE,
    ) -> ReportDateRange:
        return resolve_run_date_range(
            None,
            request_date_from=date_from,
            request_date_to=date_to,
            tz=tz,
        )

    @classmethod
    def from_snapshot(cls, snapshot: dict[str, Any] | None) -> ReportDateRange:
        if not snapshot:
            return cls.default_global_range()
        if snapshot.get("date_from") and snapshot.get("date_to"):
            return cls.from_iso(str(snapshot["date_from"]), str(snapshot["date_to"]))
        legacy = snapshot.get("report_date")
        if legacy:
            parsed = parse_display_date(str(legacy))
            if parsed is not None:
                return cls(date_from=parsed, date_to=parsed)
        return cls.default_global_range()

    def to_portal_from(self, fmt: str | None = None) -> str:
        return self.date_from.strftime(fmt or PORTAL_DATE_FMT)

    def to_portal_to(self, fmt: str | None = None) -> str:
        return self.date_to.strftime(fmt or PORTAL_DATE_FMT)

    def display_from(self) -> str:
        return self.date_from.strftime(DISPLAY_DATE_FMT)

    def display_to(self) -> str:
        return self.date_to.strftime(DISPLAY_DATE_FMT)

    def title_suffix(self) -> str:
        if self.date_from == self.date_to:
            return f"on date {self.display_from()}"
        return f"from {self.display_from()} to {self.display_to()}"

    def filename_suffix(self) -> str:
        if self.date_from == self.date_to:
            return self.display_from()
        return f"{self.display_from()}_to_{self.display_to()}"

    def storage_key(self) -> str:
        return f"{self.date_from.isoformat()}_{self.date_to.isoformat()}"

    def legacy_report_date(self) -> str:
        return self.display_from()

    def iso_from(self) -> str:
        return self.date_from.isoformat()

    def iso_to(self) -> str:
        return self.date_to.isoformat()

    def snapshot_fields(self) -> dict[str, str]:
        fields = {
            "date_from": self.iso_from(),
            "date_to": self.iso_to(),
        }
        if self.date_from == self.date_to:
            fields["report_date"] = self.legacy_report_date()
        return fields

    def matches_snapshot(self, other: dict[str, Any] | ReportDateRange) -> bool:
        if isinstance(other, ReportDateRange):
            return self == other
        try:
            resolved = self.from_snapshot(other)
        except DateRangeValidationError:
            return False
        return self == resolved


def _calendar_today(tz: str = DEFAULT_TIMEZONE, *, moment: datetime | None = None) -> date:
    ref = moment or datetime.now(ZoneInfo(tz))
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=ZoneInfo(tz))
    else:
        ref = ref.astimezone(ZoneInfo(tz))
    return ref.date()


def _previous_calendar_day(tz: str = DEFAULT_TIMEZONE, *, moment: datetime | None = None) -> date:
    return _calendar_today(tz, moment=moment) - timedelta(days=1)


def resolve_phase1_from_date(
    tz: str = DEFAULT_TIMEZONE,
    *,
    moment: datetime | None = None,
) -> str:
    """Return yesterday's calendar date in Asia/Kolkata as YYYY-MM-DD."""
    return _previous_calendar_day(tz, moment=moment).isoformat()


def resolve_phase1_to_date(
    tz: str = DEFAULT_TIMEZONE,
    *,
    moment: datetime | None = None,
) -> str:
    """Return today's calendar date in Asia/Kolkata as YYYY-MM-DD."""
    return _calendar_today(tz, moment=moment).isoformat()


def resolve_portal_from_date(
    tz: str = DEFAULT_TIMEZONE,
    *,
    moment: datetime | None = None,
) -> str:
    """Return yesterday's calendar date in Asia/Kolkata as YYYY-MM-DD (Phase 2 alias)."""
    return resolve_phase1_from_date(tz, moment=moment)


def parse_display_date(value: str) -> date | None:
    text = value.strip()
    for fmt in (DISPLAY_DATE_FMT, "%d.%m.%Y", ISO_DATE_FMT, "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _normalize_request_date(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _try_parse_request_range(
    date_from: str | None,
    date_to: str | None,
) -> ReportDateRange | None:
    start = _normalize_request_date(date_from)
    end = _normalize_request_date(date_to)
    if not start or not end:
        return None
    try:
        return ReportDateRange.from_iso(start, end)
    except DateRangeValidationError:
        return None


def _log_date_range_resolution(
    *,
    requested_date_from: str | None,
    requested_date_to: str | None,
    resolved: ReportDateRange,
    resolution_source: ResolutionSource,
    tz: str,
) -> None:
    logger.info(
        "date_range_resolved requested_date_from=%s requested_date_to=%s "
        "resolved_date_from=%s resolved_date_to=%s resolution_source=%s timezone=%s",
        requested_date_from,
        requested_date_to,
        resolved.iso_from(),
        resolved.iso_to(),
        resolution_source,
        tz,
    )


@dataclass(frozen=True)
class DateRangeResolution:
    range: ReportDateRange
    source: ResolutionSource
    requested_date_from: str | None
    requested_date_to: str | None


def resolve_run_date_range_with_meta(
    snapshot: dict[str, Any] | None,
    *,
    request_date_from: str | None = None,
    request_date_to: str | None = None,
    saved_config: dict[str, Any] | None = None,
    tz: str = DEFAULT_TIMEZONE,
) -> DateRangeResolution:
    _ = snapshot, saved_config
    requested_from = _normalize_request_date(request_date_from)
    requested_to = _normalize_request_date(request_date_to)
    parsed = _try_parse_request_range(requested_from, requested_to)
    if parsed is not None:
        resolution = DateRangeResolution(
            range=parsed,
            source="frontend",
            requested_date_from=requested_from,
            requested_date_to=requested_to,
        )
    else:
        resolution = DateRangeResolution(
            range=ReportDateRange.default_global_range(tz),
            source="backend_default",
            requested_date_from=requested_from,
            requested_date_to=requested_to,
        )
    _log_date_range_resolution(
        requested_date_from=requested_from,
        requested_date_to=requested_to,
        resolved=resolution.range,
        resolution_source=resolution.source,
        tz=tz,
    )
    return resolution


def resolve_run_date_range(
    snapshot: dict[str, Any] | None,
    *,
    request_date_from: str | None = None,
    request_date_to: str | None = None,
    saved_config: dict[str, Any] | None = None,
    tz: str = DEFAULT_TIMEZONE,
) -> ReportDateRange:
    return resolve_run_date_range_with_meta(
        snapshot,
        request_date_from=request_date_from,
        request_date_to=request_date_to,
        saved_config=saved_config,
        tz=tz,
    ).range


def get_context_date_range() -> ReportDateRange:
    from app.automation.run_context import get_run_context

    ctx = get_run_context()
    if ctx is not None:
        date_range = getattr(ctx, "date_range", None)
        if date_range is not None:
            return date_range
        if ctx.manual_config:
            return ReportDateRange.from_snapshot(ctx.manual_config)
    return ReportDateRange.default_global_range()


def date_range_for_processing(column_selection: dict | None = None) -> ReportDateRange:
    if column_selection and column_selection.get("date_from") and column_selection.get("date_to"):
        return ReportDateRange.from_snapshot(column_selection)
    return get_context_date_range()


def normalize_portal_date(value: str, fmt: str = PORTAL_DATE_FMT) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    match = re.search(r"(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})", text)
    if match:
        text = match.group(1)
    return parse_display_date(text.replace("/", "-").replace(".", "-")) or _try_strftime_parse(text, fmt)


def _try_strftime_parse(text: str, fmt: str) -> date | None:
    try:
        return datetime.strptime(text, fmt).date()
    except ValueError:
        return None


def verify_portal_date_range(
    applied: dict[str, str],
    expected: ReportDateRange,
    *,
    date_format: str = PORTAL_DATE_FMT,
) -> None:
    from app.automation.generator import ReportGenerationError

    from_val = (
        applied.get("fromInput")
        or applied.get("fromDate")
        or applied.get("fromdate")
        or applied.get("frmdate")
    )
    to_val = (
        applied.get("toInput")
        or applied.get("toDate")
        or applied.get("todate")
    )
    date_range_val = applied.get("dateRange")

    if from_val and to_val:
        portal_from = normalize_portal_date(from_val, date_format)
        portal_to = normalize_portal_date(to_val, date_format)
        if portal_from != expected.date_from or portal_to != expected.date_to:
            raise ReportGenerationError(
                f"Portal date range mismatch: expected {expected.to_portal_from(date_format)}"
                f"–{expected.to_portal_to(date_format)}, got {from_val}–{to_val}",
                error_code="PORTAL_DATE_RANGE_MISMATCH",
            )
        return

    if date_range_val and expected.date_from == expected.date_to:
        portal = normalize_portal_date(str(date_range_val), date_format)
        if portal == expected.date_from:
            return

    raise ReportGenerationError(
        "Portal date range could not be verified against snapshot",
        error_code="PORTAL_DATE_RANGE_MISMATCH",
    )


def assert_dataset_matches_range(
    dataset_meta: dict[str, Any] | None,
    expected: ReportDateRange,
) -> None:
    if not dataset_meta:
        return
    ds_from = dataset_meta.get("date_from")
    ds_to = dataset_meta.get("date_to")
    if not ds_from or not ds_to:
        return
    actual = ReportDateRange.from_iso(str(ds_from), str(ds_to))
    if actual != expected:
        raise DateRangeValidationError(
            "DATASET_DATE_RANGE_MISMATCH",
            f"Dataset range {actual.iso_from()}–{actual.iso_to()} "
            f"does not match expected {expected.iso_from()}–{expected.iso_to()}",
        )


def assert_artifact_matches_range(
    artifact_meta: dict[str, Any] | None,
    expected: ReportDateRange,
) -> None:
    if not artifact_meta:
        return
    art_from = artifact_meta.get("date_from")
    art_to = artifact_meta.get("date_to")
    if not art_from or not art_to:
        return
    actual = ReportDateRange.from_iso(str(art_from), str(art_to))
    if actual != expected:
        raise DateRangeValidationError(
            "ARTIFACT_DATE_RANGE_MISMATCH",
            f"Artifact range {actual.iso_from()}–{actual.iso_to()} "
            f"does not match expected {expected.iso_from()}–{expected.iso_to()}",
        )
