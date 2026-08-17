"""Build normalized SummaryData from run-scoped report sources."""

from __future__ import annotations

import re
from collections import Counter, defaultdict

from app.automation.processing.bottom_report_models import MSG_NO_QUALIFYING_DIVISION
from app.automation.report4_filters import COMPLAINT_TYPES_ORDERED
from app.features.daily_summary.row_utils import (
    dept_div_tag,
    division_abbrev,
    safe_complaint_desc,
    station_label,
    top_n,
)
from app.features.daily_summary.constants import (
    DIVISION_DISPLAY_ORDER,
    SUMMARY_SOURCES,
    TERRITORIAL_CAUSE_LABELS,
    TERRITORIAL_CAUSE_ORDER,
    UNSATISFACTORY_CAUSE_ORDER,
)
from app.features.daily_summary.fields import get_field
from app.features.daily_summary.models import (
    Bottom20Section,
    CauseDivisionBlock,
    CauseWiseSection,
    SectionAvailability,
    StationFeedbackSection,
    StationHighlight,
    SummaryData,
    TerritorialCauseBlock,
    TerritorialDivisionBlock,
    TerritorialSection,
    TrainLine,
    UnsatisfactoryTrainSection,
)
from app.features.daily_summary.scr import row_dict_is_scr
from app.features.daily_summary.sources import ReportSource, RunSources

_TRAIN_BRACKET_SUFFIX = re.compile(r"\s*\[[^\]]+\]\s*$")


def format_train_name_for_summary(from_to: str) -> str:
    """Strip trailing bracket tags like [SUPERFAST] from bottom-report From-To."""
    text = (from_to or "").strip()
    while True:
        stripped = _TRAIN_BRACKET_SUFFIX.sub("", text).strip()
        if stripped == text:
            return text
        text = stripped


def _parse_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _division_sort_key(code: str) -> tuple[int, str]:
    order = {name: idx for idx, name in enumerate(DIVISION_DISPLAY_ORDER)}
    return (order.get(code, len(order)), code)


def _cause_sort_key(name: str) -> tuple[int, str]:
    order = {name: idx for idx, name in enumerate(UNSATISFACTORY_CAUSE_ORDER)}
    return (order.get(name, len(order)), name)


def _source_path(report: ReportSource | None) -> str | None:
    if report is None:
        return None
    return report.source_csv_path or (report.source_paths[0] if report.source_paths else None)


def aggregate_bottom_20(source: ReportSource | None) -> Bottom20Section:
    section = Bottom20Section()
    if source is None or not source.available:
        section.availability = SectionAvailability.MISSING
        return section

    top20 = top_n(source.rows, 20)
    section.top20_count = len(top20)
    scr_rows = [
        r
        for r in top20
        if row_dict_is_scr(r, "Owning Zone", "Owning Division", "zoneCode", "ownZoneCode")
    ]
    section.scr_trains = [
        TrainLine(
            train_no=get_field(r, "train_number", slug="train-no") or "",
            train_name=get_field(r, "train_name", slug="train-no") or "",
            complaint_count=_parse_int(get_field(r, "received", slug="train-no")) or 0,
        )
        for r in scr_rows
    ]
    section.availability = SectionAvailability.AVAILABLE
    return section


def aggregate_cause_wise(source: ReportSource | None) -> CauseWiseSection:
    section = CauseWiseSection()
    if source is None or not source.available:
        section.availability = SectionAvailability.MISSING
        return section

    blocks: list[CauseDivisionBlock] = []
    any_scr = False

    for type_name in COMPLAINT_TYPES_ORDERED:
        raw = source.type_datasets.get(type_name) or []
        top10 = top_n(raw, 10)
        scr_rows = [
            r
            for r in top10
            if row_dict_is_scr(r, "Owning Zone", "Owning Division", "zoneCode", "ownZoneCode")
        ]
        if not scr_rows:
            continue
        any_scr = True
        by_div: dict[str, list[TrainLine]] = defaultdict(list)
        seen: set[tuple[str, str, str]] = set()
        for row in scr_rows:
            train_no = get_field(row, "train_number", slug="types") or ""
            train_name = get_field(row, "train_name", slug="types") or ""
            received = get_field(row, "received", slug="types") or "0"
            key = (train_no, train_name, received)
            if key in seen:
                continue
            seen.add(key)
            div = get_field(row, "division", slug="types")
            if not div:
                continue
            by_div[division_abbrev(div)].append(
                TrainLine(
                    train_no=train_no,
                    train_name=train_name,
                    complaint_count=_parse_int(received) or 0,
                )
            )

        for div_code in sorted(by_div.keys(), key=_division_sort_key):
            blocks.append(
                CauseDivisionBlock(
                    cause=type_name,
                    division=div_code,
                    trains=by_div[div_code],
                )
            )

    section.blocks = blocks
    section.is_nil = not any_scr
    section.availability = SectionAvailability.AVAILABLE
    return section


def aggregate_territorial(source: ReportSource | None) -> TerritorialSection:
    section = TerritorialSection()
    if source is None or not source.available or source.bottom_report is None:
        section.availability = SectionAvailability.MISSING
        return section

    result = source.bottom_report
    cause_blocks: list[TerritorialCauseBlock] = []

    for cause_id in TERRITORIAL_CAUSE_ORDER:
        cause_label = TERRITORIAL_CAUSE_LABELS.get(cause_id, cause_id)
        section_result = result.sections.get(cause_id)
        cause_block = TerritorialCauseBlock(cause_id=cause_id, cause_label=cause_label)

        if section_result is None:
            cause_block.no_division_message = MSG_NO_QUALIFYING_DIVISION
            cause_blocks.append(cause_block)
            continue

        if not section_result.qualifying_divisions:
            cause_block.no_division_message = (
                section_result.no_division_message or MSG_NO_QUALIFYING_DIVISION
            )
            cause_blocks.append(cause_block)
            continue

        div_by_code = {
            div.division_code.upper(): div for div in section_result.qualifying_divisions
        }
        for div_code in DIVISION_DISPLAY_ORDER:
            div_result = div_by_code.get(div_code)
            if div_result is None:
                continue
            trains = [
                TrainLine(
                    train_no=t.train_no,
                    train_name=format_train_name_for_summary(t.from_to),
                    complaint_count=t.complaint_count,
                )
                for t in div_result.qualifying_trains
            ]
            cause_block.divisions.append(
                TerritorialDivisionBlock(
                    division_code=div_result.division_code.upper(),
                    trains=trains,
                    no_train_message=div_result.no_train_message,
                )
            )

        # Include any qualifying division not in the fixed display order.
        for div_code, div_result in sorted(div_by_code.items()):
            if div_code in DIVISION_DISPLAY_ORDER:
                continue
            trains = [
                TrainLine(
                    train_no=t.train_no,
                    train_name=format_train_name_for_summary(t.from_to),
                    complaint_count=t.complaint_count,
                )
                for t in div_result.qualifying_trains
            ]
            cause_block.divisions.append(
                TerritorialDivisionBlock(
                    division_code=div_result.division_code.upper(),
                    trains=trains,
                    no_train_message=div_result.no_train_message,
                )
            )

        cause_blocks.append(cause_block)

    section.causes = cause_blocks
    section.availability = SectionAvailability.AVAILABLE
    return section


def aggregate_unsatisfactory_train(source: ReportSource | None) -> UnsatisfactoryTrainSection:
    section = UnsatisfactoryTrainSection()
    if source is None or not source.available:
        section.availability = SectionAvailability.MISSING
        return section

    counts = source.row_counts or {}
    total = counts.get("expected")
    if total is None:
        total = counts.get("unsatisfactory")
    if total is None:
        total = len(source.rows)
    total_i = _parse_int(total)
    section.total = total_i if total_i is not None else len(source.rows)

    percent = counts.get("unsatisfactory_percent")
    if percent is not None:
        try:
            section.percent = f"{float(percent):.2f}"
        except (TypeError, ValueError):
            pass

    type_counts: Counter[str] = Counter()
    div_counts: Counter[str] = Counter()
    for row in source.rows:
        cause = get_field(row, "complaint_type", slug="scr-train")
        div = get_field(row, "division", slug="scr-train")
        if cause:
            type_counts[cause] += 1
        if div:
            div_counts[division_abbrev(div)] += 1

    section.cause_counts = sorted(
        type_counts.items(),
        key=lambda item: _cause_sort_key(item[0]),
    )
    section.division_counts = sorted(
        div_counts.items(),
        key=lambda item: _division_sort_key(item[0]),
    )
    section.row_count = len(source.rows)
    section.availability = SectionAvailability.AVAILABLE
    return section


def aggregate_station_feedback(source: ReportSource | None) -> StationFeedbackSection:
    section = StationFeedbackSection()
    if source is None or not source.available:
        section.availability = SectionAvailability.MISSING
        return section

    counts = source.row_counts or {}
    total = counts.get("expected")
    if total is None:
        total = counts.get("unsatisfactory")
    if total is None:
        total = len(source.rows)
    total_i = _parse_int(total)
    section.count = total_i if total_i is not None else len(source.rows)

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in source.rows:
        station = station_label(row)
        if not station:
            continue
        grouped[station].append(row)

    highlights: list[StationHighlight] = []
    for station, rows in sorted(grouped.items()):
        seen_descs: set[str] = set()
        for row in rows:
            desc = safe_complaint_desc(row)
            if not desc or desc in seen_descs:
                continue
            seen_descs.add(desc)
            highlights.append(
                StationHighlight(
                    station=station,
                    complaint_text=desc,
                    department_tag=dept_div_tag(row),
                )
            )

    section.highlights = highlights
    section.row_count = len(source.rows)
    section.availability = SectionAvailability.AVAILABLE
    return section


def build_summary_data(sources: RunSources, report_date: str) -> SummaryData:
    """Aggregate all summary sections from the current run's report sources."""
    reports = sources.reports
    missing = list(dict.fromkeys(sources.missing_reports))

    data = SummaryData(
        report_date=report_date,
        run_id=sources.run_id,
        missing_sources=missing,
        warnings=list(sources.validation_notes),
    )

    slug_map = SUMMARY_SOURCES
    for section_key, slug in slug_map.items():
        path = _source_path(reports.get(slug))
        if path:
            data.source_reports[slug] = path

    data.bottom_20 = aggregate_bottom_20(reports.get("train-no"))
    data.cause_wise_bottom_10 = aggregate_cause_wise(reports.get("types"))
    data.territorial = aggregate_territorial(reports.get("bottom-report"))
    data.unsatisfactory_train = aggregate_unsatisfactory_train(reports.get("scr-train"))
    data.station_feedback = aggregate_station_feedback(reports.get("scr-station"))

    return data
