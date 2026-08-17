"""Normalized data model for Daily Summary generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SectionAvailability(str, Enum):
    AVAILABLE = "available"
    MISSING = "missing"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class TrainLine:
    train_no: str
    train_name: str
    complaint_count: int


@dataclass
class Bottom20Section:
    availability: SectionAvailability = SectionAvailability.MISSING
    scr_trains: list[TrainLine] = field(default_factory=list)
    top20_count: int = 0


@dataclass
class CauseDivisionBlock:
    cause: str
    division: str
    trains: list[TrainLine] = field(default_factory=list)


@dataclass
class CauseWiseSection:
    availability: SectionAvailability = SectionAvailability.MISSING
    is_nil: bool = True
    blocks: list[CauseDivisionBlock] = field(default_factory=list)


@dataclass
class TerritorialDivisionBlock:
    division_code: str
    trains: list[TrainLine] = field(default_factory=list)
    no_train_message: str | None = None


@dataclass
class TerritorialCauseBlock:
    cause_id: str
    cause_label: str
    divisions: list[TerritorialDivisionBlock] = field(default_factory=list)
    no_division_message: str | None = None


@dataclass
class TerritorialSection:
    availability: SectionAvailability = SectionAvailability.MISSING
    causes: list[TerritorialCauseBlock] = field(default_factory=list)


@dataclass
class UnsatisfactoryTrainSection:
    availability: SectionAvailability = SectionAvailability.MISSING
    total: int | None = None
    percent: str | None = None
    cause_counts: list[tuple[str, int]] = field(default_factory=list)
    division_counts: list[tuple[str, int]] = field(default_factory=list)
    row_count: int = 0


@dataclass
class StationHighlight:
    station: str
    complaint_text: str
    department_tag: str | None = None


@dataclass
class StationFeedbackSection:
    availability: SectionAvailability = SectionAvailability.MISSING
    count: int | None = None
    highlights: list[StationHighlight] = field(default_factory=list)
    row_count: int = 0


@dataclass
class SummaryData:
    report_date: str
    run_id: str
    bottom_20: Bottom20Section = field(default_factory=Bottom20Section)
    cause_wise_bottom_10: CauseWiseSection = field(default_factory=CauseWiseSection)
    territorial: TerritorialSection = field(default_factory=TerritorialSection)
    unsatisfactory_train: UnsatisfactoryTrainSection = field(
        default_factory=UnsatisfactoryTrainSection
    )
    station_feedback: StationFeedbackSection = field(default_factory=StationFeedbackSection)
    source_reports: dict[str, str] = field(default_factory=dict)
    missing_sources: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
