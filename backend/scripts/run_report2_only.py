"""Live Report 2-only acceptance run."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from app.automation.run import attach_to_railmadad


async def main() -> int:
    result = await attach_to_railmadad(report_slugs=["division"])
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
                "row_count": r.row_count,
                "row_counts": r.row_counts,
                "duration_seconds": r.duration_seconds,
                "extraction_seconds": r.extraction_seconds,
                "processing_seconds": r.processing_seconds,
                "error": r.error,
                "source_csv_path": r.source_csv_path,
                "source_paths": r.source_paths,
                "excel_path": r.excel_path,
                "pdf_path": r.pdf_path,
                "pdf_preview_url": r.pdf_preview_url,
                "pdf_download_url": r.pdf_download_url,
                "excel_download_url": r.excel_download_url,
                "ingestion_success": r.ingestion_success,
                "processing_success": r.processing_success,
            }
            for r in result.reports
        ],
    }
    path = Path("storage/debug/report2_only_result.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    timing = Path(f"storage/debug/run_timing_{result.run_id}.json")
    if timing.exists():
        print("---TIMING---")
        print(timing.read_text(encoding="utf-8")[:8000])
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
