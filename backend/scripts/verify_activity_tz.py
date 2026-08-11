"""Live check: UTC activity timestamps, IST filters, ordering, dashboard consistency."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
IST = timezone(timedelta(hours=5, minutes=30))


async def main() -> None:
    async with httpx.AsyncClient() as c:
        r = await c.post(
            f"{BASE}/auth/login",
            json={"username": "admin", "password": "Admin@123456"},
        )
        r.raise_for_status()

        # 1. Raw timestamps must be timezone-aware UTC
        items = (await c.get(f"{BASE}/activity", params={"limit": 5})).json()["items"]
        for it in items:
            assert it["created_at"].endswith("+00:00"), f"naive ts: {it['created_at']}"
        print("newest 3 (action | utc | ist):")
        for it in items[:3]:
            dt = datetime.fromisoformat(it["created_at"])
            ist_str = dt.astimezone(IST).strftime("%d/%m/%Y %I:%M %p")
            print(" ", it["action"], "|", it["created_at"], "|", ist_str)

        # 2. Newest-first ordering
        ts = [it["created_at"] for it in items]
        assert ts == sorted(ts, reverse=True), "not newest-first"

        # 3. Today's IST day filter must include the newest event
        today = datetime.now(IST).date().isoformat()
        res = (
            await c.get(
                f"{BASE}/activity",
                params={
                    "limit": 200,
                    "from": f"{today}T00:00:00.000+05:30",
                    "to": f"{today}T23:59:59.999+05:30",
                },
            )
        ).json()
        acts = {it["action"] for it in res["items"]}
        expected = {"LOGIN", "AUTOMATION_COMPLETED", "REPORT_COMPLETED"}
        print("today total:", res["total"], "| has", expected, ":", expected <= acts)
        assert items[0]["id"] in {it["id"] for it in res["items"]}, (
            "newest event missing from today filter"
        )

        # 4. Yesterday's filter must NOT include today's newest event
        yday = (datetime.now(IST).date() - timedelta(days=1)).isoformat()
        res_y = (
            await c.get(
                f"{BASE}/activity",
                params={
                    "limit": 200,
                    "from": f"{yday}T00:00:00.000+05:30",
                    "to": f"{yday}T23:59:59.999+05:30",
                },
            )
        ).json()
        assert items[0]["id"] not in {it["id"] for it in res_y["items"]}, (
            "off-by-one: today's event matched yesterday"
        )
        print("yesterday total:", res_y["total"], "(today's event correctly excluded)")

        # 5. Dashboard last_generated_at converts to the same IST clock time
        s = (await c.get(f"{BASE}/dashboard/summary")).json()
        lg = datetime.fromisoformat(s["last_generated_at"])
        print("last_generated_at IST:", lg.astimezone(IST).strftime("%d/%m/%Y %I:%M %p"))

        print("ALL LIVE CHECKS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
