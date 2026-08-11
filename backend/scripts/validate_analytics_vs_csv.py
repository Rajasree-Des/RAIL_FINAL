"""Cross-check every /dashboard/analytics metric against the raw report CSVs."""

from __future__ import annotations

import asyncio
import csv
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import httpx
from sqlalchemy import select

from app.features.dashboard.analytics import DISPLAY_NAMES
from app.infrastructure.database.models import AutomationRunModel
from app.infrastructure.database.session import SessionLocal

BASE = "http://127.0.0.1:8000/api/v1"


def read_csv(p: str) -> list[dict[str, str]]:
    with Path(p).open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def to_int(v: str | None) -> int:
    try:
        return int(str(v or "").replace(",", "").strip() or 0)
    except ValueError:
        return 0


async def main() -> int:
    async with SessionLocal() as session:
        stmt = (
            select(AutomationRunModel)
            .where(
                AutomationRunModel.trigger_type == "cdp_in_process",
                AutomationRunModel.status == "completed",
            )
            .order_by(AutomationRunModel.created_at.desc())
            .limit(1)
        )
        run = (await session.execute(stmt)).scalars().first()
    assert run, "no completed run"
    reports = {r["slug"]: r for r in json.loads(run.result_json)["reports"]}

    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BASE}/auth/login", json={"username": "admin", "password": "Admin@123456"})
        r.raise_for_status()
        api = (await c.get(f"{BASE}/dashboard/analytics")).json()

    checks: list[tuple[str, object, object]] = []

    # KPIs vs zone comprehensive + feedback CSVs
    comp = [row for row in read_csv(reports["report1"]["source_paths"][0])
            if "total" not in (row.get("Organisation") or "").lower()]
    fb = [row for row in read_csv(reports["report1"]["source_paths"][1])
          if "total" not in (row.get("Organisation") or "").lower()]
    checks.append(("complaints_received", api["totals"]["complaints_received"],
                   sum(to_int(r["Received"]) for r in comp)))
    checks.append(("complaints_resolved", api["totals"]["complaints_resolved"],
                   sum(to_int(r["Closed"]) for r in comp)))
    checks.append(("feedback_received", api["totals"]["feedback_received"],
                   sum(to_int(r["Feedback Received"]) for r in fb)))
    expected_rate = round(
        sum(to_int(r["Closed"]) for r in comp) / sum(to_int(r["Received"]) for r in comp) * 100, 2
    )
    checks.append(("resolution_rate", api["totals"]["resolution_rate"], expected_rate))
    checks.append(("zone_count", len(api["zones"]), len(comp)))
    top_zone = max(comp, key=lambda r: to_int(r["Received"]))
    checks.append(("top_zone", api["zones"][0]["zone"], top_zone["Organisation"].strip()))
    checks.append(("top_zone_complaints", api["zones"][0]["complaints"], to_int(top_zone["Received"])))

    # Divisions
    div = [row for row in read_csv(reports["division"]["source_paths"][0])
           if "total" not in (row.get("Division") or "").lower()]
    checks.append(("division_count", len(api["divisions"]), len(div)))
    top_div = max(div, key=lambda r: to_int(r["Received"]))
    checks.append(("top_division", api["divisions"][0]["division"], top_div["Division"].strip()))

    # Trains
    trains = read_csv(reports["train-no"]["source_paths"][0])
    checks.append(("train_count", len(api["trains"]), min(20, len(trains))))
    top_train = max(trains, key=lambda r: to_int(r["Received"]))
    checks.append(("top_train_no", api["trains"][0]["train_no"], top_train["Train No."].strip()))

    # Types
    index_rows = read_csv(reports["types"]["source_csv_path"])
    type_sums = {
        row["type_name"]: sum(to_int(r["Received"]) for r in read_csv(row["csv_path"]))
        for row in index_rows if row["status"] == "success"
    }
    api_types = {t["type_name"]: t["complaints"] for t in api["complaint_types"]}
    checks.append(("complaint_types", api_types, type_sums))
    grand = sum(type_sums.values())
    for t in api["complaint_types"]:
        expected_pct = round(type_sums[t["type_name"]] / grand * 100, 2)
        checks.append((f"pct:{t['type_name']}", t["percentage"], expected_pct))

    # SCR rows
    scr_rows = read_csv(reports["scr-train"]["source_paths"][0])
    checks.append(("scr_train_total_complaints",
                   sum(t["complaints"] for t in api["scr_trains"]),
                   len([r for r in scr_rows if (r.get("Train/Station") or "").lower() not in ("", "null")])))

    # Report cards — one card per configured dashboard report slug
    checks.append(("report_cards", len(api["report_cards"]), len(DISPLAY_NAMES)))
    checks.append(("all_files_sized",
                   all(f["file_size_bytes"] and f["file_size_bytes"] > 0
                       for card in api["report_cards"] for f in card["files"]),
                   True))

    failures = [(name, got, want) for name, got, want in checks if got != want]
    for name, got, want in checks:
        mark = "OK " if got == want else "FAIL"
        print(f"[{mark}] {name}: api={got!r} csv={want!r}")
    print("\nRESULT:", "ALL MATCH" if not failures else f"{len(failures)} MISMATCHES")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
