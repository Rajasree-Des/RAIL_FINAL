"""Deterministic text builders for Daily Summary sections."""

from __future__ import annotations

from collections import Counter, defaultdict

from app.automation.comprehensive1013_filters import COMPREHENSIVE_1013_SECTION_IDS
from app.automation.report4_filters import COMPLAINT_TYPES_ORDERED
from app.automation.formatting.text_safe import normalize_report_text
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

_DIVISION_ABBREVS: dict[str, str] = {
    "secunderabad": "SC",
    "hyderabad": "HYB",
    "nanded": "NED",
    "vijayawada": "BZA",
    "guntur": "GNT",
    "guntakal": "GTL",
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


def _is_total_row(row: dict[str, str], *keys: str) -> bool:
    for key in keys:
        val = (row.get(key) or "").strip().lower()
        if "total" in val:
            return True
    joined = " ".join((row.get(k) or "") for k in row).lower()
    return "total" in joined and any(
        (row.get(k) or "").strip().lower().startswith("total")
        or (row.get(k) or "").strip().lower() == "total"
        for k in (
            "Train No.",
            "Train Name",
            "Owning Zone",
            "Organisation",
            "Division",
            "Cause",
            "cause",
        )
        if k in row
    )


def _top_n(rows: list[dict[str, str]], n: int) -> list[dict[str, str]]:
    data = [
        r
        for r in rows
        if not _is_total_row(r, "Train No.", "Train Name", "Owning Zone", "Division", "Cause")
    ]
    return data[:n]


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


def _division_abbrev(value: str) -> str:
    text = value.strip()
    if not text:
        return text
    if len(text) <= 4 and text.isupper():
        return text
    lowered = text.casefold()
    for pattern, abbr in _DIVISION_ABBREVS.items():
        if pattern in lowered:
            return abbr
    return text


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


def _safe_complaint_desc(row: dict[str, str]) -> str:
    val = get_field(row, "complaint_desc", slug="scr-station")
    if val:
        return normalize_report_text(val, field_kind="text", column_name="complaint_desc")
    return ""


def _station_label(row: dict[str, str]) -> str | None:
    val = get_field(row, "station", slug="scr-station")
    if val:
        return normalize_report_text(val, field_kind="text", column_name="station")
    return None


def _dept_div_tag(row: dict[str, str]) -> str | None:
    dept = get_field(row, "department", slug="scr-station")
    div = get_field(row, "division", slug="scr-station")
    if dept and div:
        return f"[{dept}-{_division_abbrev(div)}]"
    if dept:
        return f"[{dept}]"
    if div:
        return f"[{_division_abbrev(div)}]"
    return None


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


def build_full_summary(
    sources: RunSources,
    report_date: str,
) -> tuple[str, dict[str, int], list[str], list[str]]:
    """Return (text, source_row_counts, missing_reports, validation_notes)."""
    r1 = sources.reports.get("report1")
    r2 = sources.reports.get("division")
    r3 = sources.reports.get("train-no")
    r4 = sources.reports.get("types")
    r5 = sources.reports.get("scr-train")
    r6 = sources.reports.get("scr-station")
    r9 = sources.reports.get("report9")
    r1013 = sources.reports.get("comprehensive-10-13")

    text3, count3 = build_report3_section(r3 if r3 and r3.available else None, report_date)
    text4, count4 = build_report4_section(r4 if r4 and r4.available else None, report_date)
    text5, count5, notes5 = build_report5_section(r5 if r5 and r5.available else None, report_date)
    text6, count6 = build_report6_section(r6 if r6 and r6.available else None, report_date)
    text1, count1 = build_report1_section(r1 if r1 and r1.available else None, report_date)
    text2, count2 = build_report2_section(r2 if r2 and r2.available else None, report_date)
    text9, count9 = build_report9_section(r9 if r9 and r9.available else None, report_date)
    text1013, count1013 = build_comprehensive_section(
        r1013 if r1013 and r1013.available else None, report_date
    )

    row_counts = {
        "report1": count1,
        "division": count2,
        "train-no": count3,
        "types": count4,
        "scr-train": count5,
        "scr-station": count6,
        "report9": count9,
        "comprehensive-10-13": count1013,
    }
    notes = list(sources.validation_notes) + notes5
    notes = reconcile_summary(sources, row_counts, notes)
    missing = list(dict.fromkeys(sources.missing_reports))
    text = join_summary_sections(text3, text4, text5, text6, text1, text2, text9, text1013)
    return text, row_counts, missing, notes
