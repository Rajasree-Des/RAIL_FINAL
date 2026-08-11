"""Live check: dashboard analytics derived from the latest completed run."""

from __future__ import annotations

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from app.features.dashboard.analytics import DashboardAnalyticsService
from app.infrastructure.database.session import SessionLocal


async def main() -> None:
    async with SessionLocal() as session:
        res = await DashboardAnalyticsService(session).analytics()
    print("has_data:", res.has_data, "| run:", res.run_id, "| generated_at:", res.generated_at)
    print("totals:", res.totals)
    print("feedback:", res.feedback_distribution)
    print("zones:", len(res.zones), "first:", res.zones[0] if res.zones else None)
    print("divisions:", len(res.divisions), "first:", res.divisions[0] if res.divisions else None)
    print("trains:", len(res.trains), "first:", res.trains[0] if res.trains else None)
    print("types:", [(t.type_name, t.complaints, t.percentage) for t in res.complaint_types])
    print("scr_trains:", len(res.scr_trains), "first:", res.scr_trains[0] if res.scr_trains else None)
    print("scr_stations:", len(res.scr_stations), "first:", res.scr_stations[0] if res.scr_stations else None)
    print("by_report:", [(c.name, c.count) for c in res.complaints_by_report])
    for card in res.report_cards:
        print("card:", card.slug, card.status, card.generated_at, card.duration_seconds,
              [(f.file_type, f.file_size_bytes) for f in card.files])


if __name__ == "__main__":
    asyncio.run(main())
