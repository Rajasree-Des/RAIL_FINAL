"""Discover filter fields on the current MIS report page."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.automation.browser import BrowserManager
from app.automation.config import config
from app.automation.filters import FilterDiscoveryService, FilterService
from app.automation.navigation import NavigationService
from app.automation.reports import REPORT_3_TRAIN_NO, REPORT_10_ZONE_TRAIN_TYPE
from app.automation.session import SessionManager


async def main() -> None:
    manager = BrowserManager(cdp_url=config.chrome_debug_url)
    session = SessionManager(railmadad_url=config.railmadad_url)
    try:
        browser = await manager.connect()
        page = await session.ensure_authenticated_mis_page(browser)
        nav = NavigationService()
        await nav.navigate_to_report(page, REPORT_3_TRAIN_NO)
        await page.wait_for_timeout(3000)
        print("URL:", page.url)
        root = await FilterService.get_report_root(page)
        fields = await FilterDiscoveryService().discover_fields(page)
        print(json.dumps(fields, indent=2, default=str))

        # Dump visible select labels/options sample
        info = await page.evaluate(
            """() => {
              const rows = [];
              document.querySelectorAll('select').forEach((sel, i) => {
                const tr = sel.closest('tr');
                const label = tr ? (tr.querySelector('td,th')||{}).innerText : '';
                const opts = Array.from(sel.options).slice(0, 8).map(o => o.text.trim());
                rows.push({
                  index: i,
                  id: sel.id,
                  name: sel.name,
                  label: (label||'').trim().slice(0, 80),
                  optionCount: sel.options.length,
                  options: opts,
                });
              });
              return rows;
            }"""
        )
        print("SELECTS:", json.dumps(info, indent=2))
        dest = ROOT / "storage" / "debug" / "report10_fields.json"
        dest.write_text(json.dumps({"fields": fields, "selects": info, "url": page.url}, indent=2), encoding="utf-8")
        print("wrote", dest)
    finally:
        await manager.close()


if __name__ == "__main__":
    asyncio.run(main())
