"""Phase 1 live verification: run one report slug and capture phase1 logs."""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.automation.date_range import resolve_phase1_from_date
from app.automation.run import attach_to_railmadad


class Phase1LogCapture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[dict] = []

    def emit(self, record: logging.LogRecord) -> None:
        event = getattr(record, "automation_event", None)
        msg = record.getMessage()
        if not (event and str(event).startswith("phase1_")) and "phase1_" not in msg:
            return
        entry = {
            "message": msg,
            "event": event,
            "run_id": getattr(record, "run_id", None),
            "report_slug": getattr(record, "report_slug", None),
            "source_name": getattr(record, "source_name", None),
            "expected_from_date": getattr(record, "expected_from_date", None),
            "actual_from_date": getattr(record, "actual_from_date", None),
            "actual_to_date": getattr(record, "actual_to_date", None),
            "selector_used": getattr(record, "selector_used", None),
            "retry_count": getattr(record, "retry_count", None),
        }
        self.events.append(entry)


async def run_slug(slug: str) -> dict:
    capture = Phase1LogCapture()
    capture.setLevel(logging.INFO)
    root = logging.getLogger()
    root.addHandler(capture)
    root.setLevel(logging.INFO)

    expected_yesterday = resolve_phase1_from_date()
    result = await attach_to_railmadad(report_slugs=[slug])

    phase1_events = [
        e for e in capture.events
        if (e.get("event") or "").startswith("phase1_")
        or "phase1_" in (e.get("message") or "")
    ]

    report_row = next((r for r in result.reports if r.slug == slug or slug in (r.slug,)), None)
    if report_row is None and result.reports:
        report_row = result.reports[0]

    out = {
        "slug": slug,
        "expected_yesterday_ist": expected_yesterday,
        "today_ist": datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat(),
        "success": result.success,
        "run_id": result.run_id,
        "error": result.error,
        "phase1_events": phase1_events,
        "report": None,
    }
    if report_row is not None:
        out["report"] = {
            "slug": report_row.slug,
            "status": report_row.status,
            "error": report_row.error,
            "excel_path": report_row.excel_path,
            "pdf_path": report_row.pdf_path,
            "source_paths": report_row.source_paths,
            "row_counts": report_row.row_counts,
        }

    dest = ROOT / "storage" / "debug" / f"phase1_live_{slug}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    return out


async def main() -> int:
    slug = sys.argv[1] if len(sys.argv) > 1 else "report1"
    out = await run_slug(slug)
    return 0 if out.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
