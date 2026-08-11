"""Discover report6 (Feedback) filter IDs and Zone Wise table structure."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.automation.browser import BrowserManager
from app.automation.config import config
from app.automation.navigation import NavigationService
from app.automation.reports import REPORT_5_SCR_TRAIN
from app.automation.session import SessionManager


async def main() -> None:
    manager = BrowserManager(cdp_url=config.chrome_debug_url)
    session = SessionManager(railmadad_url=config.railmadad_url)
    try:
        browser = await manager.connect()
        page = await session.ensure_authenticated_mis_page(browser)
        await NavigationService().navigate_to_report(page, REPORT_5_SCR_TRAIN)
        await page.wait_for_timeout(2500)
        print("URL", page.url)

        selects = await page.evaluate(
            """() => Array.from(document.querySelectorAll('select')).map(sel => {
              const wrap = sel.closest('.form-group, .row, tr, .col-md-2, .col-md-3, .col-md-4, .col-md-6');
              let label = '';
              if (wrap) {
                const lab = wrap.querySelector('label, td, th');
                label = lab ? (lab.innerText||'').trim().slice(0,80) : '';
              }
              return {
                id: sel.id,
                name: sel.name,
                label,
                value: sel.value,
                options: Array.from(sel.options).slice(0, 15).map(o => o.text.trim()),
              };
            })"""
        )
        print(json.dumps(selects, indent=2))

        # Apply Previous Day + Zone SCR + Mode Train + Submit via page evaluate-ish
        await page.select_option("#dateRange", label="Previous Day")
        # try common ids
        for sel_id, label in [
            ("complaintZoneInput", "South Central Railway"),
            ("zoneInput", "South Central Railway"),
            ("modeInput", "Train"),
            ("complaintModeInput", "Train"),
            ("viewType", "Zone Wise / Dept. Wise"),
            ("viewInput", "Zone Wise / Dept. Wise"),
        ]:
            loc = page.locator(f"#{sel_id}")
            if await loc.count() > 0:
                try:
                    await loc.select_option(label=label)
                    print(f"set #{sel_id} -> {label}")
                except Exception as exc:
                    print(f"fail #{sel_id}: {exc}")

        if await page.locator("#submitbtn").count() > 0:
            await page.locator("#submitbtn").click()
            await page.wait_for_timeout(5000)

        tables = await page.evaluate(
            """() => Array.from(document.querySelectorAll('table')).slice(0,6).map((table, idx) => {
              const headers = Array.from(table.querySelectorAll('thead th, tr:first-child th, tr:first-child td'))
                .map(c => (c.innerText||'').trim());
              const rows = Array.from(table.querySelectorAll('tbody tr')).slice(0,8).map(tr =>
                Array.from(tr.querySelectorAll('td')).slice(0,8).map(td => (td.innerText||'').trim().slice(0,50))
              );
              return {idx, headers, rows, rowCount: table.querySelectorAll('tbody tr').length};
            })"""
        )
        out = {"url": page.url, "selects": selects, "tables": tables}
        dest = ROOT / "storage" / "debug" / "report6_scr_debug.json"
        dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
        await page.screenshot(path=str(ROOT / "storage" / "debug" / "report6_scr_live.png"), full_page=True)
        print(json.dumps(tables, indent=2)[:5000])
        print("wrote", dest)
    finally:
        await manager.close()


if __name__ == "__main__":
    asyncio.run(main())
