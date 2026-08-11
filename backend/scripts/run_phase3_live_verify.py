"""Phase 3 live verification: run Report 5 or 6 and capture phase3 logs."""
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

from app.automation.date_range import resolve_portal_from_date
from app.automation.run import attach_to_railmadad


class Phase3LogCapture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[dict] = []

    def emit(self, record: logging.LogRecord) -> None:
        event = getattr(record, "automation_event", None)
        msg = record.getMessage()
        if not (event and str(event).startswith("phase3_")) and "phase3_" not in msg:
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
            "to_date_before": getattr(record, "to_date_before", None),
            "to_date_after": getattr(record, "to_date_after", None),
            "selector_used": getattr(record, "selector_used", None),
            "retry_count": getattr(record, "retry_count", None),
            "mode": getattr(record, "mode", None),
            "extracted_count": getattr(record, "extracted_count", None),
            "expected_count": getattr(record, "expected_count", None),
            "status": getattr(record, "status", None),
        }
        self.events.append(entry)


async def run_slug(slug: str) -> dict:
    capture = Phase3LogCapture()
    capture.setLevel(logging.INFO)
    root = logging.getLogger()
    root.addHandler(capture)
    root.setLevel(logging.INFO)

    expected_yesterday = resolve_portal_from_date()
    result = await attach_to_railmadad(report_slugs=[slug])

    phase3_events = [
        e for e in capture.events
        if (e.get("event") or "").startswith("phase3_")
        or "phase3_" in (e.get("message") or "")
    ]

    report_row = next((r for r in result.reports if r.slug == slug), None)
    if report_row is None and result.reports:
        report_row = result.reports[0]

    out = {
        "slug": slug,
        "expected_yesterday_ist": expected_yesterday,
        "today_ist": datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat(),
        "success": result.success,
        "run_id": result.run_id,
        "error": result.error,
        "phase3_events": phase3_events,
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

    dest = ROOT / "storage" / "debug" / f"phase3_live_{slug}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    return out


async def main() -> int:
    slug = sys.argv[1] if len(sys.argv) > 1 else "scr-train"
    if slug == "both":
        r5 = await run_slug("scr-train")
        r6 = await run_slug("scr-station")
        ok = r5.get("success") and r6.get("success")
        print(json.dumps({"scr-train": r5, "scr-station": r6}, indent=2))
        return 0 if ok else 1
    out = await run_slug(slug)
    return 0 if out.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
