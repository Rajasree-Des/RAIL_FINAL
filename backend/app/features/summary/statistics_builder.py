"""Compute all report statistics in Python — AI must never calculate these."""

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

DEFAULT_COLUMN_MAPPING = {
    "status": "status",
    "complaint_type": "complaint_type",
    "division": "division",
    "train_number": "train_number",
    "complaint_count": "complaint_count",
    "resolved_count": "resolved_count",
    "unsatisfactory_count": "unsatisfactory_count",
}


@dataclass
class ReportStatistics:
    """Pre-computed statistics passed to the LLM."""

    total_complaints: int = 0
    resolved_complaints: int = 0
    pending_complaints: int = 0
    resolution_rate: float = 0.0
    unsatisfactory_count: int = 0
    unsatisfactory_rate: float = 0.0
    top_complaint_types: list[dict[str, Any]] = field(default_factory=list)
    top_divisions: list[dict[str, Any]] = field(default_factory=list)
    top_trains: list[dict[str, Any]] = field(default_factory=list)
    bottom_trains: list[dict[str, Any]] = field(default_factory=list)
    scr_train_count: int = 0
    daily_highlights: list[str] = field(default_factory=list)
    key_observations: list[str] = field(default_factory=list)
    report_period: str = ""
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class StatisticsBuilder:
    """Build report statistics from processed dataset rows."""

    RESOLVED_STATUSES = {"resolved", "closed", "completed", "done"}
    PENDING_STATUSES = {"pending", "open", "in progress", "in_progress", "active"}

    def build(
        self,
        rows: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
        column_mapping: dict[str, str] | None = None,
    ) -> ReportStatistics:
        """Compute all statistics from dataset rows."""
        metadata = metadata or {}
        mapping = {**DEFAULT_COLUMN_MAPPING, **(column_mapping or {})}

        if not rows:
            return ReportStatistics(
                report_period=metadata.get("report_period", ""),
                generated_at=datetime.now(UTC).isoformat(),
                daily_highlights=["No data available for the selected period."],
                key_observations=["No observations — dataset is empty."],
            )

        status_col = mapping["status"]
        type_col = mapping["complaint_type"]
        division_col = mapping["division"]
        train_col = mapping["train_number"]
        count_col = mapping["complaint_count"]

        total = len(rows)
        resolved = self._count_by_status(rows, status_col, self.RESOLVED_STATUSES)
        pending = self._count_by_status(rows, status_col, self.PENDING_STATUSES)
        if pending == 0 and resolved < total:
            pending = total - resolved

        resolution_rate = round((resolved / total) * 100, 1) if total else 0.0

        unsatisfactory = self._sum_column(rows, mapping.get("unsatisfactory_count", "unsatisfactory_count"))
        if unsatisfactory == 0:
            unsatisfactory = self._count_unsatisfactory(rows)
        unsatisfactory_rate = round((unsatisfactory / total) * 100, 1) if total else 0.0

        top_types = self._top_by_field(rows, type_col, count_col, limit=5)
        top_divisions = self._top_by_field(rows, division_col, count_col, limit=5)
        top_trains = self._top_by_field(rows, train_col, count_col, limit=20, reverse=True)
        bottom_trains = self._top_by_field(rows, train_col, count_col, limit=20, reverse=False)

        scr_in_bottom = sum(
            1 for t in bottom_trains if "SCR" in str(t.get("name", "")).upper()
        )

        stats = ReportStatistics(
            total_complaints=total,
            resolved_complaints=resolved,
            pending_complaints=pending,
            resolution_rate=resolution_rate,
            unsatisfactory_count=unsatisfactory,
            unsatisfactory_rate=unsatisfactory_rate,
            top_complaint_types=top_types,
            top_divisions=top_divisions,
            top_trains=top_trains[:10],
            bottom_trains=bottom_trains[:20],
            scr_train_count=scr_in_bottom,
            report_period=metadata.get("report_period", metadata.get("period", "")),
            generated_at=datetime.now(UTC).isoformat(),
        )

        stats.daily_highlights = self._build_daily_highlights(stats)
        stats.key_observations = self._build_key_observations(stats, metadata)

        return stats

    @staticmethod
    def _count_by_status(
        rows: list[dict[str, Any]],
        status_col: str,
        statuses: set[str],
    ) -> int:
        count = 0
        for row in rows:
            val = str(row.get(status_col, "")).lower().strip()
            if val in statuses:
                count += 1
        return count

    @staticmethod
    def _sum_column(rows: list[dict[str, Any]], col: str) -> int:
        total = 0
        for row in rows:
            try:
                total += int(float(row.get(col, 0) or 0))
            except (ValueError, TypeError):
                pass
        return total

    @staticmethod
    def _count_unsatisfactory(rows: list[dict[str, Any]]) -> int:
        count = 0
        for row in rows:
            for key, val in row.items():
                if "unsatisf" in key.lower():
                    try:
                        if int(float(val or 0)) > 0:
                            count += 1
                            break
                    except (ValueError, TypeError):
                        pass
        return count

    def _top_by_field(
        self,
        rows: list[dict[str, Any]],
        field_col: str,
        count_col: str,
        limit: int = 5,
        reverse: bool = True,
    ) -> list[dict[str, Any]]:
        """Aggregate by field and return top/bottom entries."""
        totals: Counter[str] = Counter()
        for row in rows:
            name = str(row.get(field_col, "") or "Unknown")
            try:
                val = float(row.get(count_col, 1) or 1)
            except (ValueError, TypeError):
                val = 1
            totals[name] += val

        if not totals:
            return []

        grand_total = sum(totals.values())
        sorted_items = sorted(totals.items(), key=lambda x: x[1], reverse=reverse)
        result = []
        for name, count in sorted_items[:limit]:
            pct = round((count / grand_total) * 100, 1) if grand_total else 0.0
            result.append({"name": name, "count": int(count), "percentage": pct})
        return result

    @staticmethod
    def _build_daily_highlights(stats: ReportStatistics) -> list[str]:
        highlights: list[str] = []

        highlights.append(
            f"Total complaints: {stats.total_complaints}; "
            f"Resolved: {stats.resolved_complaints} ({stats.resolution_rate}%); "
            f"Pending: {stats.pending_complaints}."
        )

        if stats.bottom_trains:
            scr_count = stats.scr_train_count
            if scr_count == 0:
                highlights.append(
                    f"Bottom {len(stats.bottom_trains)} trains contain no SCR trains."
                )
            else:
                highlights.append(
                    f"Bottom {len(stats.bottom_trains)} trains include {scr_count} SCR train(s)."
                )

        if stats.top_complaint_types:
            top = stats.top_complaint_types[0]
            highlights.append(
                f"Highest complaints received in {top['name']} "
                f"({top['count']}, {top['percentage']}%)."
            )

        if stats.unsatisfactory_count > 0:
            highlights.append(
                f"Total unsatisfactory feedback {stats.unsatisfactory_count} "
                f"({stats.unsatisfactory_rate}%)."
            )

        if stats.top_divisions:
            top_div = stats.top_divisions[0]
            highlights.append(
                f"Top division by complaints: {top_div['name']} "
                f"({top_div['count']}, {top_div['percentage']}%)."
            )

        return highlights

    @staticmethod
    def _build_key_observations(
        stats: ReportStatistics,
        metadata: dict[str, Any],
    ) -> list[str]:
        observations: list[str] = []

        if stats.resolution_rate >= 80:
            observations.append(
                f"Resolution rate of {stats.resolution_rate}% indicates strong performance."
            )
        elif stats.resolution_rate < 60:
            observations.append(
                f"Resolution rate of {stats.resolution_rate}% requires immediate attention."
            )

        if stats.pending_complaints > stats.resolved_complaints:
            observations.append(
                f"Pending complaints ({stats.pending_complaints}) exceed resolved "
                f"({stats.resolved_complaints}) — backlog growing."
            )

        report_name = metadata.get("report_name", "")
        if report_name:
            observations.append(f"Report scope: {report_name}.")

        if len(stats.top_complaint_types) >= 2:
            first, second = stats.top_complaint_types[0], stats.top_complaint_types[1]
            observations.append(
                f"{first['name']} leads with {first['count']} complaints, "
                f"followed by {second['name']} with {second['count']}."
            )

        if stats.unsatisfactory_rate > 20:
            observations.append(
                f"Unsatisfactory feedback rate ({stats.unsatisfactory_rate}%) is above threshold."
            )

        if not observations:
            observations.append("No significant anomalies detected in the current dataset.")

        return observations
