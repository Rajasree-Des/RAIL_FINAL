"""Generate daily summary from the latest completed CDP run (live acceptance helper).

Usage (from backend/ with venv):
  python -m scripts.generate_daily_summary_from_latest_run
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Ensure backend root on path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.features.daily_summary.service import DailySummaryService
from app.infrastructure.database.models import AutomationRunModel
from app.infrastructure.database.session import SessionLocal


async def main() -> int:
    async with SessionLocal() as session:
        stmt = (
            select(AutomationRunModel)
            .where(
                AutomationRunModel.status.in_(("completed", "failed", "stopped")),
                AutomationRunModel.created_by.is_not(None),
            )
            .order_by(AutomationRunModel.completed_at.desc().nullslast())
            .limit(1)
        )
        result = await session.execute(stmt)
        run = result.scalar_one_or_none()
        if run is None:
            # Fall back to any terminal run + seed admin
            stmt2 = (
                select(AutomationRunModel)
                .where(AutomationRunModel.status.in_(("completed", "failed", "stopped")))
                .order_by(AutomationRunModel.completed_at.desc().nullslast())
                .limit(1)
            )
            result2 = await session.execute(stmt2)
            run = result2.scalar_one_or_none()
            if run is None:
                print("No terminal automation run found.")
                return 1
            from app.infrastructure.database.models import UserModel

            admin = (
                await session.execute(
                    select(UserModel).where(UserModel.role == "admin").limit(1)
                )
            ).scalar_one_or_none()
            user_id = run.created_by or (admin.id if admin else None)
            if not user_id:
                print("No user_id available for summary attribution.")
                return 1
            # Temporarily attribute for generation (do not mutate run.created_by permanently)
        else:
            user_id = run.created_by
        assert user_id
        print(f"Using run_id={run.id} status={run.status} user={user_id}")
        # Bypass ownership check for offline live helper when run has no created_by
        if not run.created_by:
            run.created_by = user_id
            await session.commit()
        service = DailySummaryService(session)
        summary = await service.generate(run.id, user_id, regenerated=True)
        out_dir = ROOT / "storage" / "output" / "summaries"
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = f"Rail_Madad_Daily_Summary_{summary.report_date or 'unknown'}.txt"
        out_path = out_dir / filename
        out_path.write_text(summary.text or "", encoding="utf-8")
        print(json.dumps({
            "summary_id": summary.summary_id,
            "status": summary.status,
            "report_date": summary.report_date,
            "source_reports": summary.source_reports,
            "missing_reports": summary.missing_reports,
            "txt_path": str(out_path),
            "download_url": f"/api/v1/summaries/{summary.summary_id}/download",
        }, indent=2))
        print("--- SUMMARY TEXT ---")
        print(summary.text)
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
