"""Live run: train-no, scr-train, scr-station only."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from app.automation.run import attach_to_railmadad


async def main() -> int:
    result = await attach_to_railmadad(
        report_slugs=["train-no", "scr-train", "scr-station"]
    )
    out = {
        "success": result.success,
        "run_id": result.run_id,
        "total_duration_seconds": result.total_duration_seconds,
        "reports_successful": result.reports_successful,
        "reports_failed": result.reports_failed,
        "error": result.error,
        "error_code": result.error_code,
        "download_pdf_all_url": result.download_pdf_all_url,
        "download_excel_all_url": result.download_excel_all_url,
        "reports": [
            {
                "slug": r.slug,
                "status": r.status,
                "error": r.error,
                "row_count": r.row_count,
                "ingestion_success": r.ingestion_success,
                "processing_success": r.processing_success,
                "source_csv_path": r.source_csv_path,
                "excel_path": r.excel_path,
                "pdf_path": r.pdf_path,
                "pdf_preview_url": r.pdf_preview_url,
                "pdf_download_url": r.pdf_download_url,
                "excel_download_url": r.excel_download_url,
            }
            for r in result.reports
        ],
    }
    path = Path("storage/debug/train_scr_only_result.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0 if result.success and all(
        r.status == "success" and not r.error for r in result.reports
    ) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
