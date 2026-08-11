"""Debug SCR Unsatisfactory modal DOM after click."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.automation.browser import BrowserManager
from app.automation.config import config
from app.automation.handlers.report5_handler import Report5Handler
from app.automation.report5_filters import REPORT_5_FILTERS
from app.automation.reports import REPORT_5_SCR_TRAIN
from app.automation.session import SessionManager


async def main() -> None:
    manager = BrowserManager(cdp_url=config.chrome_debug_url)
    session = SessionManager(railmadad_url=config.railmadad_url)
    handler = Report5Handler()
    try:
        browser = await manager.connect()
        page = await session.ensure_authenticated_mis_page(browser)
        handler.bind_browser(browser)
        await handler.navigation.navigate_to_report(page, REPORT_5_SCR_TRAIN)
        report_root, applied, _ = await handler.apply_filters_and_submit(
            page, REPORT_5_SCR_TRAIN, filters=REPORT_5_FILTERS, session=session
        )
        print("applied", applied)
        await handler.click_received_twice(report_root, page, feedback=True)

        table = await handler._find_zone_wise_table(report_root)
        expected, row_idx = await handler._get_scr_unsatisfactory_target(table)
        print("expected", expected, "row_idx", row_idx)

        # Dump target row HTML
        rows = table.locator("tbody tr, tfoot tr")
        if await rows.count() == 0:
            rows = table.locator("tr")
        row_html = await rows.nth(row_idx).evaluate("el => el.outerHTML.slice(0, 1500)")
        print("row_html", row_html[:800])

        clicked = await handler._click_unsatisfactory_row(page, table, row_idx)
        print("clicked", clicked)
        await page.wait_for_timeout(3000)

        info = await page.evaluate(
            """() => {
              const modals = [...document.querySelectorAll('.modal, [role=dialog], #complaintListModal')];
              return modals.map(m => ({
                id: m.id,
                className: m.className,
                display: getComputedStyle(m).display,
                visibility: getComputedStyle(m).visibility,
                textLen: (m.innerText||'').length,
                textSnippet: (m.innerText||'').slice(0, 400),
                tables: [...m.querySelectorAll('table')].map(t => ({
                  id: t.id,
                  className: t.className,
                  thead: [...t.querySelectorAll('thead th, thead td')].map(c => c.innerText.trim()),
                  tbodyRows: t.querySelectorAll('tbody tr').length,
                  firstRow: [...(t.querySelector('tbody tr')?.querySelectorAll('td')||[])]
                    .slice(0,6).map(c => c.innerText.trim().slice(0,40)),
                })),
              }));
            }"""
        )
        dest = ROOT / "storage" / "debug" / "scr_modal_debug.json"
        dest.write_text(json.dumps({"expected": expected, "row_idx": row_idx, "modals": info}, indent=2), encoding="utf-8")
        print(json.dumps(info, indent=2)[:6000])
        print("wrote", dest)

        # Try extract
        complaints = await handler._extract_modal_pages(page)
        print("extracted", len(complaints), complaints[:2] if complaints else None)
        await handler._close_modal(page)
    finally:
        await manager.close()


if __name__ == "__main__":
    asyncio.run(main())
