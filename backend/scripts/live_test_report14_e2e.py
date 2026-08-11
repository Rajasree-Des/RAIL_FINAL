"""If admin MIS tab is missing, open home.jsp in the CDP Edge session."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.async_api import async_playwright

from app.automation.handlers.report14_handler import Report14Handler
from app.automation.report14_filters import SOURCE_PREVIOUS, SOURCE_UPCOMING
from app.automation.report14_navigation import navigate_report14_via_menu


ADMIN_HOME = "https://railmadad.indianrailways.gov.in/rmmis/admin/home.jsp"


async def pick_page(browser):
    scored = []
    for ctx in browser.contexts:
        for page in ctx.pages:
            url = page.url or ""
            score = 0
            if "/rmmis/admin/" in url:
                score += 100
            if "mis_reports" in url:
                score += 50
            if "railmadad" in url:
                score += 5
            if "/final/" in url or "/madad/" in url:
                score -= 50
            if "127.0.0.1" in url or "localhost" in url:
                score -= 100
            scored.append((score, page, ctx))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


async def main() -> int:
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
        ranked = await pick_page(browser)
        if not ranked:
            print("FAIL: no CDP pages")
            return 1
        print("Tabs:")
        for s, p, _ in ranked:
            print(f"  {s:4d} {p.url}")

        page = ranked[0][1]
        if "/rmmis/admin/" not in (page.url or ""):
            print(f"Opening admin home in context of {page.url[:80]}...")
            # Use best non-app tab context
            ctx = ranked[0][2]
            page = await ctx.new_page()
            await page.goto(ADMIN_HOME, wait_until="domcontentloaded", timeout=45_000)
            await page.wait_for_timeout(2000)
            print("After goto:", page.url)
            html_len = len(await page.content())
            text = await page.evaluate("() => (document.body.innerText||'').slice(0,500)")
            print("text snippet:", text.replace("\n", " | ")[:400])
            if "MIS Reports" not in text and "Welcome" not in text and "Login" in text:
                print("FAIL: admin session not authenticated (login page).")
                print("ACTION: Log into RailMadad MIS admin in Edge CDP, then re-run this script.")
                return 3

        print("Using:", page.url)
        print("Navigating Report 14 menu...")
        try:
            await navigate_report14_via_menu(page, run_id="live-e2e")
        except Exception as exc:
            print("NAV FAIL:", type(exc).__name__, exc)
            return 4
        print("Form OK, URL=", page.url)

        handler = Report14Handler()
        root = await handler.filter_service.get_report_root(page)
        for cfg in (SOURCE_PREVIOUS, SOURCE_UPCOMING):
            print(f"Applying {cfg.source_id}...")
            applied = await handler._apply_and_verify_filters(
                root, page, cfg=cfg, report_slug="report14"
            )
            print("  applied:", {k: applied.get(k) for k in ("zone", "view", "division", "output")})
        live = await page.evaluate(
            """() => {
              const r = id => {
                const el = document.getElementById(id);
                if (!el || !el.options) return null;
                return (el.options[el.selectedIndex]?.text || '').trim();
              };
              return {zone:r('complaintZoneInput'), view:r('viewType'), division:r('complaintDivInput')};
            }"""
        )
        print("Live DOM:", live)
        print("PASS live Report 14 navigation + filters")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
