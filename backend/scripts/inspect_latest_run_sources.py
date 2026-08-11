"""Print the latest completed run's per-report source CSV paths and headers."""

from __future__ import annotations

import asyncio
import csv
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from sqlalchemy import select

from app.infrastructure.database.models import AutomationRunModel
from app.infrastructure.database.session import SessionLocal

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def resolve(p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else BACKEND_ROOT / path


async def main() -> None:
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
        if not run:
            print("NO COMPLETED RUN")
            return
        print("run:", run.id, run.status, run.success_count, run.failure_count, run.completed_at)
        data = json.loads(run.result_json or "{}")
        for rep in data.get("reports", []):
            print("\n=== slug:", rep.get("slug"), "| status:", rep.get("status"),
                  "| rows:", rep.get("row_count"), "| row_counts:", rep.get("row_counts"))
            paths = list(rep.get("source_paths") or [])
            if rep.get("source_csv_path") and rep["source_csv_path"] not in paths:
                paths.insert(0, rep["source_csv_path"])
            for p in paths:
                fp = resolve(p)
                print("  src:", p, "| exists:", fp.exists())
                if fp.exists() and fp.suffix == ".csv":
                    with fp.open(encoding="utf-8-sig", newline="") as f:
                        rows = list(csv.reader(f))
                    print("    header:", rows[0] if rows else None)
                    if len(rows) > 1:
                        print("    row1:", rows[1])
                    if len(rows) > 2:
                        print("    last:", rows[-1])
                    print("    n_rows:", len(rows) - 1)


if __name__ == "__main__":
    asyncio.run(main())
