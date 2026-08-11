"""Deep-dump report10 page controls including custom widgets."""

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
from app.automation.reports import REPORT_3_TRAIN_NO
from app.automation.session import SessionManager


async def main() -> None:
    manager = BrowserManager(cdp_url=config.chrome_debug_url)
    session = SessionManager(railmadad_url=config.railmadad_url)
    try:
        browser = await manager.connect()
        page = await session.ensure_authenticated_mis_page(browser)
        await NavigationService().navigate_to_report(page, REPORT_3_TRAIN_NO)
        await page.wait_for_timeout(4000)

        # Screenshot for debug
        shot = ROOT / "storage" / "debug" / "report10_live.png"
        await page.screenshot(path=str(shot), full_page=True)

        data = await page.evaluate(
            """() => {
              const out = {
                title: document.title,
                url: location.href,
                labels: [],
                buttons: [],
                inputs: [],
                selects: [],
                multiselects: [],
                texts: [],
              };
              document.querySelectorAll('label, .control-label, td, th, span, div').forEach(el => {
                const t = (el.innerText||'').trim();
                if (!t || t.length > 60) return;
                const key = t.toLowerCase();
                if (['zone','division','view','type','sub type','department','train','coach'].some(k => key.includes(k))) {
                  out.labels.push({tag: el.tagName, text: t, id: el.id, className: el.className});
                }
              });
              document.querySelectorAll('button, input[type=button], input[type=submit], a.btn').forEach(el => {
                out.buttons.push({
                  tag: el.tagName,
                  id: el.id,
                  text: (el.innerText||el.value||'').trim().slice(0,80),
                  className: el.className,
                });
              });
              document.querySelectorAll('input, select, textarea').forEach(el => {
                const item = {
                  tag: el.tagName,
                  type: el.type,
                  id: el.id,
                  name: el.name,
                  className: el.className,
                  value: el.value,
                };
                if (el.tagName === 'SELECT') out.selects.push(item);
                else out.inputs.push(item);
              });
              document.querySelectorAll('.multiselect, .dropdown-toggle, [data-toggle=dropdown], .select2, .chosen-container').forEach(el => {
                out.multiselects.push({
                  tag: el.tagName,
                  id: el.id,
                  className: el.className,
                  text: (el.innerText||'').trim().slice(0,100),
                });
              });
              // Capture filter panel text
              const body = (document.body.innerText||'').split('\\n').map(s => s.trim()).filter(Boolean);
              out.texts = body.slice(0, 120);
              return out;
            }"""
        )
        dest = ROOT / "storage" / "debug" / "report10_deep.json"
        dest.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print("screenshot", shot)
        print("labels", json.dumps(data["labels"][:40], indent=2))
        print("selects", json.dumps(data["selects"], indent=2))
        print("multiselects", json.dumps(data["multiselects"][:30], indent=2))
        print("buttons", json.dumps(data["buttons"][:20], indent=2))
        print("texts sample", data["texts"][:40])
    finally:
        await manager.close()


if __name__ == "__main__":
    asyncio.run(main())
