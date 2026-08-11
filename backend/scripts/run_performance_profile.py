"""Run all six reports and write performance_after_<run_id>.json."""

from __future__ import annotations

import asyncio
import os
import sys

# Ensure backend app is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.automation.run import attach_to_railmadad


async def main() -> None:
    os.environ.setdefault("AUTOMATION_PERF_LABEL", "after")
    slugs = [
        "report1",
        "division",
        "train-no",
        "types",
        "scr-train",
        "scr-station",
    ]
    print(f"Starting performance run for: {slugs}")
    result = await attach_to_railmadad(report_slugs=slugs)
    print(f"Run {result.run_id}: success={result.success} duration={result.total_duration_seconds}s")
    for rep in result.reports:
        print(
            f"  {rep.slug}: {rep.status} "
            f"duration={rep.duration_seconds}s "
            f"rows={rep.row_count}"
        )
    if not result.success:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
