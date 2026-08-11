"""Train number extraction and frequency aggregation for Bottom Report."""

from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from app.automation.processing.bottom_report_models import QualifyingTrain
from app.automation.scr_field_map import canonicalize_scr_row

logger = logging.getLogger(__name__)

_TRAIN_NUMBER_RE = re.compile(r"\b(0?\d{4,5})\b")
_STATION_ONLY_HINTS = re.compile(r"^\s*[A-Z]{2,5}\s*[-/]", re.I)


@dataclass
class DivisionTrainAggregation:
    """All trains in one division with reconciliation counts."""

    trains: list[QualifyingTrain] = field(default_factory=list)
    valid_train_row_count: int = 0
    non_train_row_count: int = 0
    grouped_train_total: int = 0


def _normalize_mode(mode: str) -> str:
    return re.sub(r"\s+", " ", (mode or "").strip()).lower()


def mode_indicates_train(mode: str) -> bool:
    text = _normalize_mode(mode)
    if not text:
        return True
    if text in {"t", "train"}:
        return True
    if "train" in text:
        return True
    if text in {"s", "station"} or "station" in text:
        return False
    return True


def extract_train_number(train_station: str, *, mode: str = "") -> str | None:
    """Extract train number as string, preserving leading zeros."""
    text = str(train_station or "").strip()
    if not text:
        return None
    if not mode_indicates_train(mode):
        return None
    if _STATION_ONLY_HINTS.match(text) and not _TRAIN_NUMBER_RE.search(text):
        return None
    match = _TRAIN_NUMBER_RE.search(text)
    if not match:
        return None
    train_no = match.group(1)
    if train_no.isdigit() and len(train_no) < 4:
        return None
    return train_no


def _resolve_from_to(canonical: dict[str, str], portal_row: dict[str, str]) -> str:
    for key in ("trainNameForReport", "Train Name For Report", "trainName", "Train Name", "train_name"):
        value = str(canonical.get(key) or portal_row.get(key) or "").strip()
        if value and value.lower() != "null":
            return value
    return ""


def _resolve_owning_railway(canonical: dict[str, str], portal_row: dict[str, str]) -> str:
    for key in (
        "ownZoneCode",
        "zoneCode",
        "owningZone",
        "owning_zone",
        "Owning Zone",
        "Owning Railway",
    ):
        value = str(canonical.get(key) or portal_row.get(key) or "").strip()
        if value and value.lower() != "null":
            return value.upper()
    return ""


def _row_mode(portal_row: dict[str, str]) -> str:
    for key in ("Mode", "mode", "complaintMode"):
        value = str(portal_row.get(key) or "").strip()
        if value:
            return value
    return ""


def _pick_most_frequent_name(names: list[str]) -> str:
    if not names:
        return ""
    counts = Counter(names)
    best_count = max(counts.values())
    candidates = sorted(name for name, count in counts.items() if count == best_count)
    return candidates[0] if candidates else ""


def aggregate_division_trains(
    detail_rows: list[dict[str, str]],
    *,
    division_code: str = "",
) -> DivisionTrainAggregation:
    """Group all valid train numbers in a division with total complaint counts."""
    counts: Counter[str] = Counter()
    name_candidates: dict[str, list[str]] = defaultdict(list)
    owning_values: dict[str, list[str]] = defaultdict(list)
    valid_train_rows = 0
    non_train_rows = 0

    for row in detail_rows:
        canonical = canonicalize_scr_row(dict(row))
        mode = _row_mode(row)
        train_station = (
            str(canonical.get("trainStation") or row.get("Train/Station") or "").strip()
        )
        train_no = extract_train_number(train_station, mode=mode)
        if not train_no:
            non_train_rows += 1
            continue
        valid_train_rows += 1
        counts[train_no] += 1
        from_to = _resolve_from_to(canonical, row)
        if from_to:
            name_candidates[train_no].append(from_to)
        owning = _resolve_owning_railway(canonical, row)
        if owning:
            owning_values[train_no].append(owning)

    trains: list[QualifyingTrain] = []
    for train_no, count in counts.items():
        from_to = _pick_most_frequent_name(name_candidates.get(train_no) or [])
        owning_list = owning_values.get(train_no) or []
        unique_owning = set(owning_list)
        owning_railway = owning_list[0] if owning_list else ""
        if len(unique_owning) > 1:
            logger.warning(
                "bottom_report owning railway conflict train=%s division=%s values=%s",
                train_no,
                division_code,
                sorted(unique_owning),
            )

        trains.append(
            QualifyingTrain(
                train_no=train_no,
                from_to=from_to,
                complaint_count=count,
                owning_railway=owning_railway,
            )
        )

    trains.sort(key=lambda t: (-t.complaint_count, t.train_no))
    grouped_total = sum(t.complaint_count for t in trains)

    return DivisionTrainAggregation(
        trains=trains,
        valid_train_row_count=valid_train_rows,
        non_train_row_count=non_train_rows,
        grouped_train_total=grouped_total,
    )


def aggregate_train_frequencies(
    detail_rows: list[dict[str, str]],
    *,
    threshold: int | None = None,
) -> list[QualifyingTrain]:
    """Backward-compatible wrapper — returns all division trains (no count filter)."""
    _ = threshold
    return aggregate_division_trains(detail_rows).trains


def build_division_train_summary(
    detail_rows: list[dict[str, str]],
) -> dict[str, Any]:
    """Return full aggregation summary for one division's detail rows."""
    agg = aggregate_division_trains(detail_rows)
    return {
        "qualifying_trains": agg.trains,
        "train_counts": {t.train_no: t.complaint_count for t in agg.trains},
        "detail_row_count": len(detail_rows),
        "valid_train_row_count": agg.valid_train_row_count,
        "non_train_row_count": agg.non_train_row_count,
        "grouped_train_total": agg.grouped_train_total,
    }
