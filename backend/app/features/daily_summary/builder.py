"""Deterministic text builders for Daily Summary sections."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date

from app.automation.comprehensive1013_filters import COMPREHENSIVE_1013_SECTION_IDS
from app.automation.report4_filters import COMPLAINT_TYPES_ORDERED
from app.features.daily_summary.aggregator import build_summary_data
from app.features.daily_summary.constants import (
    CAUSE_WISE_HEADER,
    GREETING,
    REPORT6_REFERENCE,
)
from app.features.daily_summary.models import (
    Bottom20Section,
    CauseWiseSection,
    SectionAvailability,
    StationFeedbackSection,
    SummaryData,
    TerritorialSection,
    TrainLine,
    UnsatisfactoryTrainSection,
)
from app.features.daily_summary.validation import validate_summary_data
from app.features.daily_summary.fields import get_field
from app.features.daily_summary.scr import row_dict_is_scr, text_is_scr
from app.features.daily_summary.sources import ReportSource, RunSources

_UNAVAILABLE = "Data unavailable for the selected run."

_ZONE_ABBREVS: dict[str, str] = {
    "northern railway": "NR",
    "north central railway": "NCR",
    "north eastern railway": "NER",
    "north east frontier railway": "NFR",
    "central railway": "CR",
    "western railway": "WR",
    "eastern railway": "ER",
    "east central railway": "ECR",
    "east coast railway": "ECoR",
    "south eastern railway": "SER",
    "south east central railway": "SECR",
    "south western railway": "SWR",
    "south central railway": "SCR",
    "west central railway": "WCR",
    "north western railway": "NWR",
    "southern railway": "SR",
    "metro railway": "MR",
}

_COMPREHENSIVE_LABELS: dict[str, str] = {
    "report10_cw": "Report 10 (C&W)",
    "report11_security": "Report 11 (Security)",
    "report12_punctuality": "Report 12 (Punctuality)",
    "report13_electrical": "Report 13 (Electrical)",
}

_REPORT9_LABELS: dict[str, str] = {
    "all_zone_train": "All Zones Train",
    "all_zone_station": "All Zones Station",
    "scr_train": "SCR Train",
    "scr_station": "SCR Station",
}


from app.features.daily_summary.row_utils import (
    dept_div_tag as _dept_div_tag,
    division_abbrev as _division_abbrev,
    is_total_row as _is_total_row,
    safe_complaint_desc as _safe_complaint_desc,
    station_label as _station_label,
    top_n as _top_n,
)


def _split_total_row(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], dict[str, str] | None]:
    if not rows:
        return [], None
    last = rows[-1]
    if _is_total_row(last, "Division", "Organisation", "Cause", "cause"):
        return rows[:-1], last
    return rows, None


def _zone_abbrev(row: dict[str, str], *, slug: str | None = None) -> str | None:
    zone = get_field(row, "zone", slug=slug)
    if not zone:
        return None
    if text_is_scr(zone):
        return "SCR"
    lowered = zone.casefold()
    for pattern, abbr in _ZONE_ABBREVS.items():
        if pattern in lowered:
            return abbr
    tokens = zone.split()
    if len(tokens) >= 2 and tokens[-1].casefold() == "railway":
        return "".join(t[0] for t in tokens[:-1]).upper()
    if len(zone) <= 5 and zone.isupper():
        return zone
    return zone[:4].upper()


def _unavailable(report_name: str) -> str:
    return f"{report_name}: {_UNAVAILABLE}"


def build_report1_section(source: ReportSource | None, report_date: str) -> tuple[str, int]:
    if source is None or not source.available:
        return _unavailable("Report 1 (Zone Wise)"), 0

    data, total_row = _split_total_row(source.rows)
    lines = ["*ZONE WISE*", ""]
    count = 0
    for row in data:
        org = get_field(row, "organisation", slug="report1") or get_field(row, "zone", slug="report1")
        if not org:
            continue
        received = get_field(row, "received", slug="report1") or "0"
        closed = get_field(row, "closed", slug="report1")
        rank = get_field(row, "rank", slug="report1")
        parts = [f"*{org}* Received {received}"]
        if closed:
            parts.append(f"Closed {closed}")
        if rank:
            parts.append(f"Rank {rank}")
        lines.append(", ".join(parts))
        count += 1

    if total_row:
        received = get_field(total_row, "received", slug="report1")
        closed = get_field(total_row, "closed", slug="report1")
        if received or closed:
            parts = ["Total"]
            if received:
                parts.append(f"Received {received}")
            if closed:
                parts.append(f"Closed {closed}")
            lines.append(", ".join(parts))

    if count == 0:
        return (
            f"*ZONE WISE*\n\nNo zone-wise data rows for {report_date}.",
            0,
        )
    return "\n".join(lines) + "\n", count


def build_report2_section(source: ReportSource | None, report_date: str) -> tuple[str, int]:
    if source is None or not source.available:
        return _unavailable("Report 2 (Division Wise)"), 0

    data, _ = _split_total_row(source.rows)
    div_counts: Counter[str] = Counter()
    for row in data:
        div = get_field(row, "division", slug="division")
        received = get_field(row, "received", slug="division")
        if not div or not received:
            continue
        try:
            count = int(received)
        except ValueError:
            continue
        div_counts[_division_abbrev(div)] += count

    if not div_counts:
        return (
            f"*DIVISION WISE COMPLAINTS*\n\nNo division-wise data for {report_date}.",
            0,
        )

    parts = [
        f"{abbr} {count}"
        for abbr, count in sorted(div_counts.items(), key=lambda x: (-x[1], x[0]))
    ]
    text = "*DIVISION WISE COMPLAINTS*\n\n[" + ", ".join(parts) + "]\n"
    return text, sum(div_counts.values())


def build_report3_section(source: ReportSource | None, report_date: str) -> tuple[str, int]:
    if source is None or not source.available:
        return _unavailable("Report 3 (Top 20 Trains)"), 0

    top20 = _top_n(source.rows, 20)
    scr_rows = [
        r
        for r in top20
        if row_dict_is_scr(r, "Owning Zone", "Owning Division", "zoneCode", "ownZoneCode")
    ]
    if not scr_rows:
        text = (
            "Good morning Sir/Madam,\n\n"
            f"In Bottom 20 trains w.r.to maximum Grievances, No SCR based train had come "
            f"as on {report_date}."
        )
        return text, len(top20)

    lines = [
        "Good morning Sir/Madam,",
        "",
        f"In Bottom 20 trains w.r.to maximum Grievances, the following SCR based trains "
        f"were reported as on {report_date}:",
        "",
    ]
    for row in scr_rows:
        train_no = get_field(row, "train_number", slug="train-no") or ""
        train_name = get_field(row, "train_name", slug="train-no") or ""
        received = get_field(row, "received", slug="train-no") or "0"
        lines.append(f"{train_no} {train_name} with {received} complaint(s)")
    return "\n".join(lines), len(top20)


def _zone_distribution_line(
    top10: list[dict[str, str]],
    *,
    has_scr: bool,
    slug: str = "types",
) -> str:
    zone_counts: Counter[str] = Counter()
    for row in top10:
        abbr = _zone_abbrev(row, slug=slug)
        if abbr and abbr != "SCR":
            zone_counts[abbr] += 1
    parts: list[str] = []
    if not has_scr:
        parts.append("*SCR-NIL*")
    for abbr, count in sorted(zone_counts.items(), key=lambda x: (-x[1], x[0])):
        parts.append(f"{abbr}-{count}")
    return "[" + ", ".join(parts) + "]" if parts else ""


def build_report4_section(source: ReportSource | None, report_date: str) -> tuple[str, int]:
    if source is None or not source.available:
        return _unavailable("Report 5 (Cause Wise)"), 0

    blocks: list[str] = [
        "Sir,",
        "",
        "In cause wise train wise in bottom 10 trains [w.r.to Report 10: Zone wise train wise]",
        "",
    ]
    total_rows = 0
    any_scr = False

    for type_name in COMPLAINT_TYPES_ORDERED:
        raw = source.type_datasets.get(type_name) or []
        top10 = _top_n(raw, 10)
        total_rows += len(top10)
        scr = [
            r
            for r in top10
            if row_dict_is_scr(r, "Owning Zone", "Owning Division", "zoneCode", "ownZoneCode")
        ]
        zone_line = _zone_distribution_line(top10, has_scr=bool(scr))
        if not scr:
            if zone_line:
                blocks.append(f"*{type_name}*")
                blocks.append(zone_line)
                blocks.append("")
            continue
        any_scr = True
        seen: set[tuple[str, str, str]] = set()
        by_div: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in scr:
            train_no = get_field(row, "train_number", slug="types") or ""
            train_name = get_field(row, "train_name", slug="types") or ""
            received = get_field(row, "received", slug="types") or ""
            key = (train_no, train_name, received)
            if key in seen:
                continue
            seen.add(key)
            div = get_field(row, "division", slug="types")
            if div:
                by_div[div].append(row)

        blocks.append(f"*{type_name}*")
        if zone_line:
            blocks.append(zone_line)
        for div_name, trains in sorted(by_div.items()):
            blocks.append(f"*{div_name}*")
            for row in trains:
                train_no = get_field(row, "train_number", slug="types") or ""
                train_name = get_field(row, "train_name", slug="types") or ""
                received = get_field(row, "received", slug="types") or "0"
                blocks.append(f"{train_no} {train_name} {received} complaint(s)")
        blocks.append("")

    if not any_scr:
        blocks.append(
            f"No SCR based trains were reported in cause-wise bottom 10 as on {report_date}."
        )
        blocks.append("")

    return "\n".join(blocks).rstrip() + "\n", total_rows


def build_report5_section(source: ReportSource | None, report_date: str) -> tuple[str, int, list[str]]:
    notes: list[str] = []
    if source is None or not source.available:
        return _unavailable("Report 6 (SCR Train)"), 0, notes

    counts = source.row_counts or {}
    total = counts.get("expected")
    if total is None:
        total = counts.get("unsatisfactory")
    if total is None:
        total = len(source.rows)
    try:
        total_i = int(total)
    except (TypeError, ValueError):
        total_i = len(source.rows)

    if total_i == 0 and not source.rows:
        text = (
            "Total unsatisfactory feedback of trains are 0.\n\n"
            f"No unsatisfactory train feedback cases were reported as on {report_date}."
        )
        return text, 0, notes

    percent = counts.get("unsatisfactory_percent")
    percent_str: str | None = None
    if percent is not None:
        try:
            percent_f = float(percent)
            percent_str = f"{percent_f:.2f}"
        except (TypeError, ValueError):
            notes.append("scr-train: unsatisfactory_percent unparseable")
    else:
        notes.append("scr-train: unsatisfactory_percent missing from run metadata")

    if percent_str is not None:
        header = f"Total unsatisfactory feedback of trains are {total_i}, {percent_str}%"
    else:
        header = f"Total unsatisfactory feedback of trains are {total_i}"

    type_counts: Counter[str] = Counter()
    div_counts: Counter[str] = Counter()
    for row in source.rows:
        cause = get_field(row, "complaint_type", slug="scr-train")
        div = get_field(row, "division", slug="scr-train")
        if cause:
            type_counts[cause] += 1
        if div:
            div_counts[_division_abbrev(div)] += 1

    lines = [header, ""]
    for name, count in sorted(type_counts.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"{name}    {count}")
    if div_counts:
        lines.append("")
        lines.append("DIVISION Wise")
        div_parts = [
            f"{name} {count}"
            for name, count in sorted(div_counts.items(), key=lambda x: (-x[1], x[0]))
        ]
        lines.append("[" + " ".join(div_parts) + "]")
    lines.append("")
    lines.append(
        "All concerned for information & N.A. w.r.to unsatisfactory feedback "
        "in REPORT No.6 on case to case basis."
    )
    return "\n".join(lines), len(source.rows), notes


def build_report6_section(source: ReportSource | None, report_date: str) -> tuple[str, int]:
    if source is None or not source.available:
        return _unavailable("Report 7 (SCR Station)"), 0

    counts = source.row_counts or {}
    total = counts.get("expected")
    if total is None:
        total = counts.get("unsatisfactory")
    if total is None:
        total = len(source.rows)
    try:
        total_i = int(total)
    except (TypeError, ValueError):
        total_i = len(source.rows)

    if total_i == 0 and not source.rows:
        text = (
            "Unsatisfactory feedback at station are 0.\n\n"
            f"No unsatisfactory station feedback cases were reported as on {report_date}."
        )
        return text, 0

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in source.rows:
        station = _station_label(row)
        if not station:
            continue
        grouped[station].append(row)

    lines = [f"Unsatisfactory feedback at station are {total_i}", ""]
    for station, rows in sorted(grouped.items()):
        lines.append(f"*{station}*")
        descs: list[str] = []
        tags: set[str] = set()
        for row in rows:
            desc = _safe_complaint_desc(row)
            if desc and desc not in descs:
                descs.append(desc)
            tag = _dept_div_tag(row)
            if tag:
                tags.add(tag)
        for desc in descs:
            lines.append(desc)
        for tag in sorted(tags):
            lines.append(tag)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n", len(source.rows)


def build_report9_section(source: ReportSource | None, report_date: str) -> tuple[str, int]:
    if source is None or not source.available:
        return _unavailable("Report 9 (Cause Wise Overview)"), 0

    lines = ["*CAUSE WISE OVERVIEW*", ""]
    total_rows = 0
    for source_id, label in _REPORT9_LABELS.items():
        rows = source.section_datasets.get(source_id) or []
        data, total_row = _split_total_row(rows)
        if not data and not total_row:
            continue
        total_rows += len(data)
        top_causes: list[str] = []
        for row in data[:3]:
            cause = get_field(row, "complaint_type", slug="report9") or get_field(row, "organisation", slug="report9")
            received = get_field(row, "received", slug="report9") or "0"
            if cause:
                top_causes.append(f"{cause} ({received})")
        summary = ", ".join(top_causes) if top_causes else "—"
        if total_row:
            total_received = get_field(total_row, "received", slug="report9")
            if total_received:
                summary = f"Total {total_received}; top: {summary}"
        lines.append(f"{label}: {summary}")
    if total_rows == 0:
        return (
            f"*CAUSE WISE OVERVIEW*\n\nNo cause-wise overview data for {report_date}.",
            0,
        )
    return "\n".join(lines) + "\n", total_rows


def build_comprehensive_section(source: ReportSource | None, report_date: str) -> tuple[str, int]:
    if source is None or not source.available:
        return _unavailable("Reports 10–13 (Comprehensive)"), 0

    lines = ["*COMPREHENSIVE REPORTS*", ""]
    total_rows = 0
    for section_id in COMPREHENSIVE_1013_SECTION_IDS:
        label = _COMPREHENSIVE_LABELS.get(section_id, section_id)
        rows = source.section_datasets.get(section_id) or []
        data, total_row = _split_total_row(rows)
        if not data and not total_row:
            lines.append(f"{label}: no data")
            continue
        total_rows += len(data)

        received_total = get_field(total_row, "received", slug="comprehensive-10-13") if total_row else None
        closed_total = get_field(total_row, "closed", slug="comprehensive-10-13") if total_row else None

        highest_div = ""
        highest_count = -1
        for row in data:
            div = get_field(row, "division", slug="comprehensive-10-13")
            received = get_field(row, "received", slug="comprehensive-10-13")
            if not div or not received:
                continue
            try:
                count = int(received)
            except ValueError:
                continue
            if count > highest_count:
                highest_count = count
                highest_div = _division_abbrev(div)

        parts: list[str] = []
        if received_total:
            parts.append(f"Received {received_total}")
        if closed_total:
            parts.append(f"Closed {closed_total}")
        if highest_div and highest_count >= 0:
            parts.append(f"highest {highest_div} ({highest_count})")
        lines.append(f"{label}: {', '.join(parts) if parts else '—'}")

    if total_rows == 0:
        return (
            f"*COMPREHENSIVE REPORTS*\n\nNo comprehensive report data for {report_date}.",
            0,
        )
    return "\n".join(lines) + "\n", total_rows


def reconcile_summary(
    sources: RunSources,
    row_counts: dict[str, int],
    notes: list[str],
) -> list[str]:
    """Validate cross-section totals and append reconciliation notes."""
    out = list(notes)
    r5 = sources.reports.get("scr-train")
    if r5 and r5.available and r5.rows:
        counts = r5.row_counts or {}
        expected = counts.get("unsatisfactory") or counts.get("expected")
        try:
            expected_i = int(expected) if expected is not None else len(r5.rows)
        except (TypeError, ValueError):
            expected_i = len(r5.rows)

        type_sum = sum(
            1
            for row in r5.rows
            if get_field(row, "complaint_type", slug="scr-train")
        )
        div_sum = sum(
            1 for row in r5.rows if get_field(row, "division", slug="scr-train")
        )
        if type_sum and type_sum != expected_i:
            out.append(
                f"scr-train: cause count ({type_sum}) != unsatisfactory total ({expected_i})"
            )
        if div_sum and div_sum != expected_i:
            out.append(
                f"scr-train: division count ({div_sum}) != unsatisfactory total ({expected_i})"
            )

    r6 = sources.reports.get("scr-station")
    if r6 and r6.available:
        counts = r6.row_counts or {}
        expected = counts.get("unsatisfactory") or counts.get("expected")
        try:
            expected_i = int(expected) if expected is not None else len(r6.rows)
        except (TypeError, ValueError):
            expected_i = len(r6.rows)
        grouped = {
            station
            for row in r6.rows
            if (station := _station_label(row))
        }
        if grouped and len(grouped) != expected_i and r6.rows:
            out.append(
                f"scr-station: grouped station count ({len(grouped)}) "
                f"!= unsatisfactory total ({expected_i})"
            )

    r9 = sources.reports.get("report9")
    if r9 and r9.available:
        for source_id, rows in r9.section_datasets.items():
            data, total_row = _split_total_row(rows)
            if not total_row or not data:
                continue
            total_received = get_field(total_row, "received", slug="report9")
            if not total_received:
                continue
            try:
                total_i = int(total_received)
            except ValueError:
                continue
            data_sum = 0
            for row in data:
                received = get_field(row, "received", slug="report9")
                if not received:
                    continue
                try:
                    data_sum += int(received)
                except ValueError:
                    pass
            if data_sum and data_sum != total_i:
                out.append(
                    f"report9/{source_id}: cause sum ({data_sum}) != total row ({total_i})"
                )

    comp = sources.reports.get("comprehensive-10-13")
    if comp and comp.available:
        for section_id, rows in comp.section_datasets.items():
            _, total_row = _split_total_row(rows)
            if total_row is None and rows:
                out.append(f"comprehensive-10-13/{section_id}: missing Total row")

    if not sources.run_id:
        out.append("run_id missing from sources")

    return out


def join_summary_sections(*sections: str) -> str:
    parts = [s.rstrip() for s in sections if s and s.strip()]
    return "\n\n".join(parts) + "\n"


def format_train_line(train: TrainLine) -> str:
    return f"{train.train_no}    {train.train_name} {train.complaint_count} complaints"


def _render_bottom_20(section: Bottom20Section, report_date: str) -> list[str]:
    if section.availability == SectionAvailability.MISSING:
        return [f"Report 3 (Top 20 Trains): {_UNAVAILABLE}"]

    if not section.scr_trains:
        return [
            f"In Bottom 20 trains w.r.to maximum Grievances, No SCR based train had come "
            f"as on {report_date}."
        ]

    lines = [
        f"In Bottom 20 trains w.r.to maximum Grievances, the following SCR based trains "
        f"had come as on {report_date}:",
        "",
    ]
    lines.extend(format_train_line(t) for t in section.scr_trains)
    return lines


def _render_cause_wise(section: CauseWiseSection) -> list[str]:
    if section.availability == SectionAvailability.MISSING:
        return [f"Report 5 (Cause Wise): {_UNAVAILABLE}"]

    if section.is_nil:
        return [f"{CAUSE_WISE_HEADER}  *NIL*"]

    lines = [CAUSE_WISE_HEADER, ""]
    current_cause: str | None = None
    for block in section.blocks:
        if block.cause != current_cause:
            current_cause = block.cause
            lines.append(f"*{block.cause}*")
        lines.append(f"*{block.division}*")
        for train in block.trains:
            lines.append(format_train_line(train))
        lines.append("")
    return lines


def _render_territorial(section: TerritorialSection) -> list[str]:
    if section.availability == SectionAvailability.MISSING:
        return [f"Bottom Performed Trains Report: {_UNAVAILABLE}"]

    lines = ["*TERRITORIAL*", ""]
    for cause_block in section.causes:
        lines.append(f"*{cause_block.cause_label}*")
        if not cause_block.divisions:
            message = cause_block.no_division_message or (
                "No Div. has figured with more than 20 complaints"
            )
            lines.append(message)
            lines.append("")
            continue
        for div_block in cause_block.divisions:
            lines.append(f"*{div_block.division_code} DIVISION*")
            if div_block.trains:
                for train in div_block.trains:
                    lines.append(format_train_line(train))
            elif div_block.no_train_message:
                lines.append(div_block.no_train_message)
            lines.append("")
    return lines


def _render_unsatisfactory(section: UnsatisfactoryTrainSection) -> list[str]:
    if section.availability == SectionAvailability.MISSING:
        return [f"Report 6 (SCR Train): {_UNAVAILABLE}"]

    if section.total is None:
        return [f"Report 6 (SCR Train): {_UNAVAILABLE}"]

    if section.total == 0 and section.row_count == 0:
        return ["Total unsatisfactory feedback of trains are 0."]

    if section.percent is not None:
        header = (
            f"Total unsatisfactory feedback of trains are {section.total}, "
            f"{section.percent}%"
        )
    else:
        header = f"Total unsatisfactory feedback of trains are {section.total}"

    lines = [header, ""]
    for cause, count in section.cause_counts:
        lines.append(f"{cause}    {count}")
        lines.append("")

    if section.division_counts:
        lines.append("DIVISION Wise")
        lines.append("")
        div_parts = [f"{name} {count}" for name, count in section.division_counts]
        lines.append("[" + " ".join(div_parts) + "]")
        lines.append("")

    lines.append(REPORT6_REFERENCE)
    return lines


def _render_station(section: StationFeedbackSection) -> list[str]:
    if section.availability == SectionAvailability.MISSING:
        return [f"Report 7 (SCR Station): {_UNAVAILABLE}"]

    if section.count is None:
        return [f"Report 7 (SCR Station): {_UNAVAILABLE}"]

    lines = [f"Unsatisfactory feedback at station are {section.count}", ""]
    for highlight in section.highlights:
        lines.append(highlight.station)
        lines.append("")
        lines.append(highlight.complaint_text)
        lines.append("")
        if highlight.department_tag:
            lines.append(highlight.department_tag)
            lines.append("")
    return lines


def render_summary(data: SummaryData) -> str:
    """Render official Daily Summary text from normalized SummaryData."""
    blocks: list[list[str]] = []

    has_content = any(
        section.availability == SectionAvailability.AVAILABLE
        for section in (
            data.bottom_20,
            data.cause_wise_bottom_10,
            data.territorial,
            data.unsatisfactory_train,
            data.station_feedback,
        )
    )
    if has_content:
        blocks.append([GREETING, ""])

    blocks.append(_render_bottom_20(data.bottom_20, data.report_date))
    blocks.append(_render_cause_wise(data.cause_wise_bottom_10))
    blocks.append(_render_territorial(data.territorial))
    blocks.append(_render_unsatisfactory(data.unsatisfactory_train))
    blocks.append(_render_station(data.station_feedback))

    parts: list[str] = []
    for block in blocks:
        text = "\n".join(line for line in block if line is not None).strip()
        if text:
            parts.append(text)
    return "\n\n".join(parts) + "\n" if parts else ""


def build_full_summary(
    sources: RunSources,
    report_date: str,
    *,
    run_date_from: date | None = None,
) -> tuple[str, dict[str, int], list[str], list[str]]:
    """Return (text, source_row_counts, missing_reports, validation_notes)."""
    data = build_summary_data(sources, report_date)
    notes = validate_summary_data(data, sources, run_date_from=run_date_from)
    data.warnings = notes
    text = render_summary(data)

    row_counts = {
        "train-no": data.bottom_20.top20_count,
        "types": sum(len(b.trains) for b in data.cause_wise_bottom_10.blocks),
        "bottom-report": sum(
            len(div.trains)
            for cause in data.territorial.causes
            for div in cause.divisions
        ),
        "scr-train": data.unsatisfactory_train.row_count,
        "scr-station": data.station_feedback.row_count,
    }
    missing = list(dict.fromkeys(data.missing_sources))
    return text, row_counts, missing, notes
