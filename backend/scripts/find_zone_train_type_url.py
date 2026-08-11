"""Find the real portal URL for Zone/Train Type wise Report via menu click."""

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

        # Expand MIS Reports if needed
        mis_btn = page.locator("button:has-text('MIS Reports')")
        if await mis_btn.count() > 0:
            await mis_btn.first.click()
            await page.wait_for_timeout(1000)

        # Collect menu item texts and hrefs
        menu = await page.evaluate(
            """() => {
              const items = [];
              document.querySelectorAll('a, span, button, li').forEach(el => {
                const t = (el.innerText||'').trim().replace(/\\s+/g,' ');
                if (!t) return;
                if (/zone\\/train type|train type wise|zone.*train/i.test(t) || /^\\d+\\)/.test(t)) {
                  items.push({
                    tag: el.tagName,
                    text: t.slice(0,120),
                    href: el.getAttribute('href'),
                    onclick: el.getAttribute('onclick'),
                    id: el.id,
                    className: el.className,
                  });
                }
              });
              return items.slice(0, 80);
            }"""
        )
        print("MENU CANDIDATES:", json.dumps(menu, indent=2))

        # Click Zone/Train Type wise Report
        target = page.locator("text=Zone/Train Type wise Report").first
        if await target.count() == 0:
            target = page.locator("span:has-text('Zone/Train Type')").first
        await target.click()
        await page.wait_for_timeout(4000)
        print("AFTER CLICK URL:", page.url)

        # Dump selects after click
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
                options: Array.from(sel.options).slice(0,10).map(o => o.text.trim()),
              };
            })"""
        )
        texts = await page.evaluate(
            """() => (document.body.innerText||'').split('\\n').map(s=>s.trim()).filter(Boolean).slice(0,80)"""
        )
        shot = ROOT / "storage" / "debug" / "zone_train_type_live.png"
        await page.screenshot(path=str(shot), full_page=True)
        out = {"url": page.url, "selects": selects, "texts": texts}
        dest = ROOT / "storage" / "debug" / "zone_train_type_page.json"
        dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(json.dumps(out, indent=2)[:6000])
        print("wrote", dest, shot)
    finally:
        await manager.close()


if __name__ == "__main__":
    asyncio.run(main())
