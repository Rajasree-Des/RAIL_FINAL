"""Debug SCR feedback Zone Wise table after applying filters."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.automation.browser import BrowserManager
from app.automation.config import config
from app.automation.handlers.base import BaseReportHandler
from app.automation.handlers.report5_handler import Report5Handler
from app.automation.navigation import NavigationService
from app.automation.report5_filters import REPORT_5_FILTERS
from app.automation.reports import REPORT_5_SCR_TRAIN
from app.automation.session import SessionManager
from app.automation.table_sort import ReceivedColumnService


async def main() -> None:
    manager = BrowserManager(cdp_url=config.chrome_debug_url)
    session = SessionManager(railmadad_url=config.railmadad_url)
    handler = Report5Handler()
    try:
        browser = await manager.connect()
        page = await session.ensure_authenticated_mis_page(browser)
        handler.bind_browser(browser)
        await handler.navigation.navigate_to_report(page, REPORT_5_SCR_TRAIN)
        await page.wait_for_timeout(2000)
        report_root, applied, rows = await handler.apply_filters_and_submit(
            page, REPORT_5_SCR_TRAIN, filters=REPORT_5_FILTERS, session=session
        )
        print("applied", applied, "rows", rows, "url", page.url)
        await handler.click_received_twice(report_root, page, feedback=True)

        tables_info = []
        tables = report_root.locator("table")
        count = await tables.count()
        for idx in range(min(count, 8)):
            table = tables.nth(idx)
            headers = await handler._extract_table_headers(table)
            sample_rows = []
            body_rows = table.locator("tbody tr")
            rcount = await body_rows.count()
            for r in range(min(rcount, 5)):
                cells = body_rows.nth(r).locator("td")
                ccount = await cells.count()
                vals = []
                for c in range(min(ccount, 8)):
                    vals.append((await cells.nth(c).inner_text()).strip()[:60])
                sample_rows.append(vals)
            tables_info.append(
                {
                    "index": idx,
                    "headers": headers,
                    "row_count": rcount,
                    "sample_rows": sample_rows,
                    "is_zone": handler._is_zone_wise_table(headers),
                }
            )

        # Also dump page text snippet for South Central
        html_snip = await page.evaluate(
            """() => {
              const t = document.body.innerText;
              const i = t.toLowerCase().indexOf('south central');
              if (i < 0) return {found:false, len:t.length};
              return {found:true, snippet:t.slice(Math.max(0,i-80), i+200)};
            }"""
        )
        out = {"tables": tables_info, "south_central": html_snip, "url": page.url}
        dest = ROOT / "storage" / "debug" / "scr_train_debug.json"
        dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(json.dumps(out, indent=2)[:5000])
        print("wrote", dest)
    finally:
        await manager.close()


if __name__ == "__main__":
    asyncio.run(main())
