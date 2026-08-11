"""Run full live multi-report automation and write JSON result."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Ensure backend root is on path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.automation.run import attach_to_railmadad  # noqa: E402


async def main() -> None:
    result = await attach_to_railmadad()
    out = {
        "success": result.success,
        "connected": result.connected,
        "stopped_early": result.stopped_early,
        "stop_reason": result.stop_reason,
        "error": result.error,
        "error_code": result.error_code,
        "reports": [
            {
                "slug": rep.slug,
                "dataset_key": rep.dataset_key,
                "status": rep.status,
                "source_csv_path": rep.source_csv_path,
                "source_row_count": rep.source_row_count,
                "ingestion_success": rep.ingestion_success,
                "excel_path": rep.excel_path,
                "pdf_path": rep.pdf_path,
                "pdf_download_url": rep.pdf_download_url,
                "error": rep.error,
            }
            for rep in result.reports
        ],
    }
    dest = ROOT / "storage" / "debug" / "live_multi_report_result.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
