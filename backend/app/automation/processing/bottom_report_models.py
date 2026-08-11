"""Structured result model for Bottom Performed Trains Report."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Protocol

BOTTOM_REPORT_SLUG = "bottom-report"
RESULT_JSON_FILENAME = "result.json"

DIVISION_RECEIVED_THRESHOLD = 20
TRAIN_INCLUSION_THRESHOLD = 2
# Legacy alias retained for any external references during migration.
TRAIN_REPETITION_THRESHOLD = TRAIN_INCLUSION_THRESHOLD

MSG_NO_QUALIFYING_DIVISION = "No Div. has figured with more than 20 complaints"
MSG_NO_VALID_TRAINS = "No valid train numbers found in detailed complaints."
MSG_NO_TRAIN_GE2 = "No train has figured with 2 or more complaints"
# Legacy alias for tests/code that referenced the old message name.
MSG_NO_QUALIFYING_TRAIN = MSG_NO_VALID_TRAINS


def division_meets_received_threshold(
    received: int,
    *,
    threshold: int = DIVISION_RECEIVED_THRESHOLD,
) -> bool:
    """Drill into a division only when Received is strictly greater than the threshold.

    Received == 20 must NOT qualify. Received >= 21 must qualify.
    """
    return int(received or 0) > int(threshold)


# Final render order (not generation order).
SECTION_RENDER_ORDER = (
    "water_availability",
    "electrical_equipment",
    "security",
    "punctuality",
)

SECTION_DISPLAY_TITLES: dict[str, str] = {
    "water_availability": "Water availability",
    "electrical_equipment": "Electrical Equipment",
    "security": "Security",
    "punctuality": "Punctuality",
}

OUTPUT_COLUMNS = (
    "S No",
    "Trn No",
    "From-To",
    "No of complaints",
    "Owning Rly",
)

NUM_OUTPUT_COLUMNS = len(OUTPUT_COLUMNS)


def _json_safe(value: Any) -> Any:
    """Coerce values for JSON serialization (e.g. date objects from run context)."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


@dataclass
class QualifyingTrain:
    train_no: str
    from_to: str
    complaint_count: int
    owning_railway: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QualifyingTrain:
        return cls(
            train_no=str(data.get("train_no") or ""),
            from_to=str(data.get("from_to") or ""),
            complaint_count=int(data.get("complaint_count") or 0),
            owning_railway=str(data.get("owning_railway") or ""),
        )


@dataclass
class DivisionResult:
    division_name: str
    division_code: str
    division_received: int
    detail_row_count: int = 0
    qualifying_trains: list[QualifyingTrain] = field(default_factory=list)
    no_train_message: str | None = None
    valid_train_row_count: int = 0
    non_train_row_count: int = 0
    grouped_train_total: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "division_name": self.division_name,
            "division_code": self.division_code,
            "division_received": self.division_received,
            "detail_row_count": self.detail_row_count,
            "qualifying_trains": [t.to_dict() for t in self.qualifying_trains],
            "no_train_message": self.no_train_message,
            "valid_train_row_count": self.valid_train_row_count,
            "non_train_row_count": self.non_train_row_count,
            "grouped_train_total": self.grouped_train_total,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DivisionResult:
        trains = [
            QualifyingTrain.from_dict(item)
            for item in (data.get("qualifying_trains") or [])
        ]
        return cls(
            division_name=str(data.get("division_name") or ""),
            division_code=str(data.get("division_code") or ""),
            division_received=int(data.get("division_received") or 0),
            detail_row_count=int(data.get("detail_row_count") or 0),
            qualifying_trains=trains,
            no_train_message=data.get("no_train_message"),
            valid_train_row_count=int(data.get("valid_train_row_count") or 0),
            non_train_row_count=int(data.get("non_train_row_count") or 0),
            grouped_train_total=int(data.get("grouped_train_total") or 0),
        )


@dataclass
class SectionResult:
    section_id: str
    qualifying_divisions: list[DivisionResult] = field(default_factory=list)
    no_division_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "qualifying_divisions": [d.to_dict() for d in self.qualifying_divisions],
            "no_division_message": self.no_division_message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SectionResult:
        divisions = [
            DivisionResult.from_dict(item)
            for item in (data.get("qualifying_divisions") or [])
        ]
        return cls(
            section_id=str(data.get("section_id") or ""),
            qualifying_divisions=divisions,
            no_division_message=data.get("no_division_message"),
        )


@dataclass
class BottomReportResult:
    report_slug: str
    date_from: str
    date_to: str
    sections: dict[str, SectionResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_slug": self.report_slug,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "sections": {
                key: section.to_dict() for key, section in self.sections.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BottomReportResult:
        sections_raw = data.get("sections") or {}
        sections = {
            str(key): SectionResult.from_dict(value)
            for key, value in sections_raw.items()
            if isinstance(value, dict)
        }
        return cls(
            report_slug=str(data.get("report_slug") or BOTTOM_REPORT_SLUG),
            date_from=str(data.get("date_from") or ""),
            date_to=str(data.get("date_to") or ""),
            sections=sections,
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(_json_safe(self.to_dict()), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> BottomReportResult:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Invalid bottom report result JSON")
        return cls.from_dict(payload)


def footer_message(division_received: int, division_code: str) -> str:
    return f"Total {division_received} complaints figured in {division_code} division."


def apply_train_inclusion_filter(trains: list[QualifyingTrain]) -> list[QualifyingTrain]:
    """Keep only trains whose complaint count meets the final inclusion threshold."""
    return [t for t in trains if t.complaint_count >= TRAIN_INCLUSION_THRESHOLD]


class _TrainAggregationLike(Protocol):
    trains: list[QualifyingTrain]
    valid_train_row_count: int


def resolve_no_train_message(agg: _TrainAggregationLike) -> str | None:
    """Resolve division-level no-train message after aggregation."""
    filtered = apply_train_inclusion_filter(agg.trains)
    if filtered:
        return None
    if not agg.trains and agg.valid_train_row_count == 0:
        return MSG_NO_VALID_TRAINS
    return MSG_NO_TRAIN_GE2


def division_heading(division_code: str) -> str:
    code = (division_code or "").strip().upper()
    return f"{code} DIVISION" if code else "DIVISION"


def section_subheading(section_id: str, division_code: str | None = None) -> str:
    """Table banner text matching the reference layout.

    When *division_code* is set (qualifying division table), non-water sections
    include ``in {code} Div.``. When unset (no-division placeholder table),
    omit the division suffix so banners match the reference template.
    """
    if section_id == "water_availability":
        return (
            "Bottom performed Trains on Water availability "
            "w.r.to previous watering point"
        )
    if section_id == "electrical_equipment":
        if division_code:
            return f"Bottom performed Trains w.r.to Ele. Equipment in {division_code} Div."
        return "Bottom performed Trains w.r.to Ele. Equipment"
    if section_id == "security":
        if division_code:
            return f"Bottom performed Trains w.r.to Security in {division_code} Div."
        return "Bottom performed Trains w.r.to Security"
    if section_id == "punctuality":
        if division_code:
            return f"Bottom performed Trains w.r.to Punctuality in {division_code} Div."
        return "Bottom performed Trains w.r.to Punctuality"
    return SECTION_DISPLAY_TITLES.get(section_id, section_id)
