"""Find the RailMadad portal URL for tab 7) Mode Wise Cause Wise."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.automation.browser import BrowserManager
from app.automation.config import config
from app.automation.session import SessionManager


async def main() -> None:
    manager = BrowserManager(cdp_url=config.chrome_debug_url)
    session = SessionManager(railmadad_url=config.railmadad_url)
    try:
        browser = await manager.connect()
        page = await session.ensure_authenticated_mis_page(browser)

        mis_btn = page.locator("button:has-text('MIS Reports')")
        if await mis_btn.count() > 0:
            await mis_btn.first.click()
            await page.wait_for_timeout(1000)

        menu = await page.evaluate(
            """() => {
              const items = [];
              document.querySelectorAll('a, span, button, li, div').forEach(el => {
                const t = (el.innerText||'').trim().replace(/\\s+/g,' ');
                if (!t || t.length > 160) return;
                if (/mode\\s*wise|cause\\s*wise|7\\)/i.test(t)) {
                  items.push({
                    tag: el.tagName,
                    text: t.slice(0,160),
                    href: el.getAttribute('href'),
                    onclick: (el.getAttribute('onclick')||'').slice(0,200),
                    id: el.id,
                  });
                }
              });
              return items.slice(0, 100);
            }"""
        )
        print("MENU CANDIDATES:", json.dumps(menu, indent=2))

        target = page.locator("text=/Mode Wise Cause Wise/i").first
        if await target.count() == 0:
            target = page.locator("text=/7\\).*Mode Wise/i").first
        if await target.count() == 0:
            target = page.locator("text=/Mode Wise/i").first
        if await target.count() == 0:
            print("TARGET NOT FOUND")
            return

        await target.click()
        await page.wait_for_timeout(4000)
        print("AFTER CLICK URL:", page.url)

        selects = await page.evaluate(
            """() => Array.from(document.querySelectorAll('select')).map(sel => {
              const tr = sel.closest('tr, .form-group, .row, .col-md-2, .col-md-3, .col-md-4');
              let label = '';
              if (tr) {
                const lab = tr.querySelector('label, td, th, .control-label');
                label = lab ? (lab.innerText||'').trim() : '';
              }
              return {
                id: sel.id,
                name: sel.name,
                label,
                options: Array.from(sel.options).slice(0,15).map(o => o.text.trim()),
              };
            })"""
        )
        headings = await page.evaluate(
            """() => Array.from(document.querySelectorAll('h1,h2,h3,h4,b,strong,.card-title'))
              .map(el => (el.innerText||'').trim().replace(/\\s+/g,' '))
              .filter(t => t && /cause|train|station|grievance/i.test(t))
              .slice(0,40)"""
        )
        dest = ROOT / "storage" / "debug" / "mode_wise_cause_wise_page.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        out = {"url": page.url, "selects": selects, "headings": headings}
        dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(json.dumps(out, indent=2)[:8000])
        print("wrote", dest)
    finally:
        await manager.close()


if __name__ == "__main__":
    asyncio.run(main())
