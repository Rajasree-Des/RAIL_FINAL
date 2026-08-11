"""Dashboard analytics aggregated from the latest completed run's report outputs.

Every number is computed from the CSVs the automation actually extracted
(persisted in AutomationRunModel.result_json source paths) — never hardcoded.
Results are cached per run id and recomputed only when a newer run completes.
"""

from __future__ import annotations

import csv
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.automation.run_registry import is_under_storage
from app.features.dashboard.schemas import (
    AnalyticsTotals,
    ComplaintTypeRow,
    DashboardAnalyticsResponse,
    DivisionRow,
    FeedbackDistribution,
    NameCount,
    ReportCardInfo,
    ReportFileMeta,
    ScrEntityRow,
    TrainRow,
    ZoneRow,
)
from app.infrastructure.database.models import (
    AutomationArtifactModel,
    AutomationRunModel,
)

logger = logging.getLogger(__name__)

CDP_TRIGGER = "cdp_in_process"

DISPLAY_NAMES = {
    "report1": "Zone Wise Complaints",
    "division": "Division Bottom 25",
    "train-no": "Top 20 Trains",
    "types": "Cause Wise Analysis",
    "scr-train": "SCR Train Report",
    "scr-station": "SCR Station Report",
    "report9": "All Zones Train/Station Cause Wise on Date",
    "comprehensive-10-13": "Report 10-13 (Comprehensive Reports)",
    "report14": "Watering Complaints",
    "report18": "Report Vande Bharat",
    "bottom-report": "Bottom Performed Trains Report",
}

# Recomputed only when a newer completed run appears
_cache: tuple[str, DashboardAnalyticsResponse] | None = None


def clear_analytics_cache() -> None:
    global _cache
    _cache = None


def _to_int(value: Any) -> int:
    try:
        return int(str(value).replace(",", "").strip() or 0)
    except (ValueError, TypeError):
        return 0


def _to_float(value: Any) -> float | None:
    try:
        text = str(value).replace(",", "").replace("%", "").strip()
        return float(text) if text else None
    except (ValueError, TypeError):
        return None


def _read_csv(path_str: str | None) -> list[dict[str, str]]:
    """Read an extracted CSV (paths recorded by the automation itself)."""
    if not path_str:
        return []
    path = Path(path_str)
    try:
        if not is_under_storage(path) or not path.resolve().is_file():
            return []
        with path.open(encoding="utf-8-sig", newline="") as fh:
            return [dict(row) for row in csv.DictReader(fh)]
    except OSError as exc:
        logger.warning("analytics: cannot read %s: %s", path_str, exc)
        return []


def _is_total_row(name: str) -> bool:
    return not name or "total" in name.lower()


def _base_name(name: str) -> str:
    """'DELHI DIVISION (Northern Railway)' -> 'DELHI DIVISION'."""
    return name.split("(", 1)[0].strip()


def _source_paths(rep: dict[str, Any]) -> list[str]:
    paths = [str(p) for p in (rep.get("source_paths") or [])]
    primary = rep.get("source_csv_path")
    if primary and str(primary) not in paths:
        paths.insert(0, str(primary))
    return paths


def _resolution_pct(resolved: int, received: int) -> float | None:
    if received <= 0:
        return None
    return round(resolved / received * 100, 2)


class _Aggregator:
    """Pure aggregation over parsed result_json report entries."""

    def __init__(self, reports_by_slug: dict[str, dict[str, Any]]) -> None:
        self._reports = reports_by_slug

    def zone_rows(self) -> tuple[list[ZoneRow], AnalyticsTotals | None, FeedbackDistribution | None]:
        rep = self._reports.get("report1")
        if not rep:
            return [], None, None
        paths = _source_paths(rep)
        comprehensive = _read_csv(paths[0]) if paths else []
        feedback = _read_csv(paths[1]) if len(paths) > 1 else []

        fb_by_zone: dict[str, int] = {}
        fb_excellent = fb_satisfactory = fb_unsatisfactory = fb_total = 0
        for row in feedback:
            org = (row.get("Organisation") or "").strip()
            if _is_total_row(org):
                continue
            count = _to_int(row.get("Feedback Received"))
            fb_by_zone[_base_name(org)] = count
            fb_total += count
            fb_excellent += _to_int(row.get("Excellent"))
            fb_satisfactory += _to_int(row.get("Satisfactory"))
            fb_unsatisfactory += _to_int(row.get("Unsatisfactory"))

        zones: list[ZoneRow] = []
        received_total = resolved_total = 0
        for row in comprehensive:
            org = (row.get("Organisation") or "").strip()
            if _is_total_row(org):
                continue
            received = _to_int(row.get("Received"))
            resolved = _to_int(row.get("Closed"))
            received_total += received
            resolved_total += resolved
            zones.append(
                ZoneRow(
                    rank=0,
                    zone=org,
                    complaints=received,
                    feedback=fb_by_zone.get(_base_name(org), 0),
                    resolution_pct=_to_float(row.get("% Disposal"))
                    or _resolution_pct(resolved, received),
                )
            )
        zones.sort(key=lambda z: z.complaints, reverse=True)
        for i, zone in enumerate(zones):
            zone.rank = i + 1

        totals = None
        if zones:
            totals = AnalyticsTotals(
                complaints_received=received_total,
                feedback_received=fb_total,
                complaints_resolved=resolved_total,
                resolution_rate=_resolution_pct(resolved_total, received_total) or 0.0,
            )
        distribution = (
            FeedbackDistribution(
                total=fb_total,
                excellent=fb_excellent,
                satisfactory=fb_satisfactory,
                unsatisfactory=fb_unsatisfactory,
            )
            if fb_total > 0
            else None
        )
        return zones, totals, distribution

    def division_rows(self) -> list[DivisionRow]:
        rep = self._reports.get("division")
        if not rep:
            return []
        paths = _source_paths(rep)
        comprehensive = _read_csv(paths[0]) if paths else []
        feedback = _read_csv(paths[1]) if len(paths) > 1 else []
        fb_by_division = {
            _base_name((row.get("Organisation") or "").strip()): _to_int(
                row.get("Feedback Received")
            )
            for row in feedback
            if not _is_total_row((row.get("Organisation") or "").strip())
        }

        divisions: list[DivisionRow] = []
        for row in comprehensive:
            name = (row.get("Division") or row.get("Organisation") or "").strip()
            if _is_total_row(name):
                continue
            received = _to_int(row.get("Received"))
            divisions.append(
                DivisionRow(
                    rank=0,
                    division=name,
                    complaints=received,
                    feedback=fb_by_division.get(_base_name(name), 0),
                    resolution_pct=_to_float(row.get("% Disposal"))
                    or _resolution_pct(_to_int(row.get("Closed")), received),
                )
            )
        divisions.sort(key=lambda d: d.complaints, reverse=True)
        for i, division in enumerate(divisions):
            division.rank = i + 1
        return divisions

    def train_rows(self) -> list[TrainRow]:
        rep = self._reports.get("train-no")
        if not rep:
            return []
        paths = _source_paths(rep)
        rows = _read_csv(paths[0]) if paths else []
        trains: list[TrainRow] = []
        for row in rows:
            name = (row.get("Train Name") or "").strip()
            train_no = (row.get("Train No.") or "").strip()
            if _is_total_row(name) or not train_no:
                continue
            trains.append(
                TrainRow(
                    rank=0,
                    train_no=train_no,
                    train_name=name,
                    complaints=_to_int(row.get("Received")),
                    resolution_pct=_to_float(row.get("% Closed")),
                )
            )
        trains.sort(key=lambda t: t.complaints, reverse=True)
        trains = trains[:20]
        for i, train in enumerate(trains):
            train.rank = i + 1
        return trains

    def complaint_types(self) -> list[ComplaintTypeRow]:
        rep = self._reports.get("types")
        if not rep:
            return []
        index_rows = _read_csv(rep.get("source_csv_path"))
        counts: list[tuple[str, int]] = []
        for row in index_rows:
            if (row.get("status") or "").strip() != "success":
                continue
            type_rows = _read_csv(row.get("csv_path"))
            total = sum(_to_int(r.get("Received")) for r in type_rows)
            counts.append(((row.get("type_name") or "").strip(), total))
        grand_total = sum(count for _, count in counts)
        if grand_total <= 0:
            return []
        return sorted(
            (
                ComplaintTypeRow(
                    type_name=name,
                    complaints=count,
                    percentage=round(count / grand_total * 100, 2),
                )
                for name, count in counts
            ),
            key=lambda t: t.complaints,
            reverse=True,
        )

    def _scr_rows(self, slug: str) -> list[ScrEntityRow]:
        rep = self._reports.get(slug)
        if not rep:
            return []
        paths = _source_paths(rep)
        rows = _read_csv(paths[0]) if paths else []
        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            key = (row.get("Train/Station") or "").strip()
            if not key or key.lower() == "null":
                continue
            label = (row.get("trainNameForReport/Station Name") or "").strip()
            entry = grouped.setdefault(
                key,
                {
                    "label": label if label.lower() != "null" else None,
                    "complaints": 0,
                    "closed": 0,
                    "types": set(),
                },
            )
            entry["complaints"] += 1
            if (row.get("Status") or "").strip().lower() == "closed":
                entry["closed"] += 1
            ctype = (row.get("Type") or "").strip()
            if ctype and ctype.lower() != "null":
                entry["types"].add(ctype)
        out = [
            ScrEntityRow(
                name=key,
                label=entry["label"],
                complaints=entry["complaints"],
                complaint_types=sorted(entry["types"]),
                resolution_pct=_resolution_pct(entry["closed"], entry["complaints"]),
            )
            for key, entry in grouped.items()
        ]
        out.sort(key=lambda e: e.complaints, reverse=True)
        return out

    def scr_trains(self) -> list[ScrEntityRow]:
        return self._scr_rows("scr-train")

    def scr_stations(self) -> list[ScrEntityRow]:
        return self._scr_rows("scr-station")


def _report_status(rep: dict[str, Any] | None) -> str:
    raw = str((rep or {}).get("status") or "pending")
    return raw if raw in {"success", "partial_success", "failed", "skipped"} else "pending"


def _iso_or_none(value: Any) -> str | None:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=UTC)
        return dt.astimezone(UTC).isoformat()
    return str(value)


def _card_row_metadata(slug: str, rep: dict[str, Any] | None) -> tuple[int | None, int | None]:
    """Return optional (sections_total, row_count) for dashboard report cards."""
    if slug != "comprehensive-10-13" or not rep:
        return None, None
    row_count = rep.get("row_count")
    if row_count is None:
        row_count = rep.get("processed_row_count")
    if row_count is None:
        row_count = rep.get("source_row_count")
    try:
        parsed_row_count = int(row_count) if row_count is not None else None
    except (TypeError, ValueError):
        parsed_row_count = None
    return 4, parsed_row_count


class DashboardAnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _latest_completed_run(self) -> AutomationRunModel | None:
        stmt = (
            select(AutomationRunModel)
            .where(
                AutomationRunModel.trigger_type == CDP_TRIGGER,
                AutomationRunModel.status == "completed",
                AutomationRunModel.result_json.is_not(None),
            )
            .order_by(AutomationRunModel.created_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def _report_cards(
        self,
        run: AutomationRunModel,
        reports_by_slug: dict[str, dict[str, Any]],
    ) -> list[ReportCardInfo]:
        stmt = select(AutomationArtifactModel).where(
            AutomationArtifactModel.run_id == run.id,
            AutomationArtifactModel.artifact_type.in_(["pdf", "excel"]),
            AutomationArtifactModel.status == "ready",
        )
        artifacts = list((await self._session.execute(stmt)).scalars().all())
        files_by_slug: dict[str, list[ReportFileMeta]] = {}
        for art in artifacts:
            files_by_slug.setdefault(art.report_slug or "", []).append(
                ReportFileMeta(
                    file_type=art.artifact_type,
                    file_size_bytes=art.file_size_bytes,
                    download_url=f"/api/v1/automation/artifacts/{art.id}/download",
                    preview_url=(
                        f"/api/v1/automation/artifacts/{art.id}/preview"
                        if art.artifact_type == "pdf"
                        else None
                    ),
                )
            )
        cards: list[ReportCardInfo] = []
        for slug, name in DISPLAY_NAMES.items():
            rep = reports_by_slug.get(slug)
            sections_total, row_count = _card_row_metadata(slug, rep)
            cards.append(
                ReportCardInfo(
                    slug=slug,
                    name=name,
                    status=_report_status(rep),  # type: ignore[arg-type]
                    generated_at=_iso_or_none((rep or {}).get("completed_at")),
                    duration_seconds=(rep or {}).get("duration_seconds"),
                    sections_total=sections_total,
                    row_count=row_count,
                    files=sorted(
                        files_by_slug.get(slug, []), key=lambda f: f.file_type
                    ),
                )
            )
        return cards

    async def analytics(self) -> DashboardAnalyticsResponse:
        global _cache
        run = await self._latest_completed_run()
        if run is None:
            return DashboardAnalyticsResponse(has_data=False)
        if _cache is not None and _cache[0] == run.id:
            return _cache[1]

        try:
            result = json.loads(run.result_json or "{}")
        except json.JSONDecodeError:
            return DashboardAnalyticsResponse(has_data=False)
        reports_by_slug: dict[str, dict[str, Any]] = {
            str(rep["slug"]): rep
            for rep in result.get("reports", [])
            if isinstance(rep, dict) and rep.get("slug")
        }
        if not reports_by_slug:
            return DashboardAnalyticsResponse(has_data=False)

        agg = _Aggregator(reports_by_slug)
        zones, totals, feedback_distribution = agg.zone_rows()
        divisions = agg.division_rows()
        trains = agg.train_rows()
        complaint_types = agg.complaint_types()
        scr_trains = agg.scr_trains()
        scr_stations = agg.scr_stations()

        complaints_by_report = [
            NameCount(name=DISPLAY_NAMES["report1"], count=totals.complaints_received)
            if totals
            else None,
            NameCount(
                name=DISPLAY_NAMES["division"],
                count=sum(d.complaints for d in divisions),
            )
            if divisions
            else None,
            NameCount(
                name=DISPLAY_NAMES["train-no"],
                count=sum(t.complaints for t in trains),
            )
            if trains
            else None,
            NameCount(
                name=DISPLAY_NAMES["types"],
                count=sum(t.complaints for t in complaint_types),
            )
            if complaint_types
            else None,
            NameCount(
                name=DISPLAY_NAMES["scr-train"],
                count=sum(t.complaints for t in scr_trains),
            )
            if scr_trains
            else None,
            NameCount(
                name=DISPLAY_NAMES["scr-station"],
                count=sum(s.complaints for s in scr_stations),
            )
            if scr_stations
            else None,
        ]

        completed_at = run.completed_at
        if completed_at is not None and completed_at.tzinfo is None:
            completed_at = completed_at.replace(tzinfo=UTC)

        report_cards = await self._report_cards(run, reports_by_slug)
        has_report_files = any(card.files for card in report_cards)

        response = DashboardAnalyticsResponse(
            has_data=bool(zones or divisions or trains or complaint_types or has_report_files),
            run_id=run.id,
            generated_at=completed_at.isoformat() if completed_at else None,
            totals=totals,
            zones=zones,
            divisions=divisions,
            trains=trains,
            scr_trains=scr_trains,
            scr_stations=scr_stations,
            complaint_types=complaint_types,
            feedback_distribution=feedback_distribution,
            top_causes=[
                NameCount(name=t.type_name, count=t.complaints)
                for t in complaint_types[:10]
            ],
            complaints_by_report=[c for c in complaints_by_report if c is not None],
            report_cards=report_cards,
        )
        _cache = (run.id, response)
        return response
