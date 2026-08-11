"""Live CDP smoke test: Report 14 menu nav + filter apply/verify.

Usage (from backend/, venv active):
  python scripts/live_test_report14_filters.py

Requires Edge CDP on 127.0.0.1:9222 with an authenticated RailMadad MIS tab.
Does not start a new login or full extract.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow `python scripts/...` from backend root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.async_api import async_playwright

from app.automation.handlers.report14_handler import Report14Handler
from app.automation.report14_filters import SOURCE_PREVIOUS, SOURCE_UPCOMING
from app.automation.report14_navigation import navigate_report14_via_menu


async def _find_mis_page(browser):
    candidates = []
    for ctx in browser.contexts:
        for page in ctx.pages:
            url = page.url or ""
            if "railmadad.indianrailways.gov.in" not in url:
                continue
            score = 0
            if "/rmmis/admin/" in url:
                score += 100
            if "mis_reports" in url or "report" in url:
                score += 50
            if "/rmmis/" in url:
                score += 10
            if "/madad/final/" in url or "/rmmis/final/" in url:
                score -= 80
            candidates.append((score, page))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1] if candidates[0][0] > 0 else candidates[0][1]


async def main() -> int:
    cdp = "http://127.0.0.1:9222"
    print(f"Connecting to CDP {cdp} ...")
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(cdp)
        page = await _find_mis_page(browser)
        if page is None:
            print("FAIL: No RailMadad MIS tab found. Open authenticated home.jsp first.")
            return 1
        print(f"Attached: {page.url}")

        print("Navigating MIS Reports -> 11) Train Watering Complaints ...")
        await navigate_report14_via_menu(page, run_id="live-filter-test")
        print(f"Form ready. URL={page.url}")

        handler = Report14Handler()
        root = await handler.filter_service.get_report_root(page)

        results: dict[str, dict] = {}
        for cfg in (SOURCE_PREVIOUS, SOURCE_UPCOMING):
            print(f"\nApplying filters for {cfg.source_id} ({cfg.watering_point}) ...")
            applied = await handler._apply_and_verify_filters(
                root, page, cfg=cfg, report_slug="report14"
            )
            results[cfg.source_id] = applied
            zone = applied.get("zone", "")
            view = applied.get("view", "")
            output = applied.get("output", "")
            print(f"  zone={zone!r}")
            print(f"  view={view!r}")
            print(f"  division={applied.get('division')!r}")
            print(f"  output={output!r}")
            ok_zone = "south central" in zone.lower() or zone.lower() == "scr"
            ok_view = "division" in view.lower()
            ok_out = (
                ("previous" in output.lower() and "previous" in cfg.watering_point.lower())
                or ("upcoming" in output.lower() and "upcoming" in cfg.watering_point.lower())
            )
            if not (ok_zone and ok_view and ok_out):
                print(f"FAIL: verification incomplete for {cfg.source_id}")
                return 2
            print(f"  OK {cfg.source_id}")

        # Live DOM snapshot of currently selected filters
        live = await page.evaluate(
            """() => {
              const r = (id) => {
                const el = document.querySelector(id);
                if (!el || !el.options) return null;
                return (el.options[el.selectedIndex]?.text || '').trim();
              };
              return {
                zone: r('#complaintZoneInput'),
                division: r('#complaintDivInput'),
                view: r('#viewType'),
                sub_type: r('#complaintSubTypeInput'),
                heading: (document.body.innerText || '').includes('Train Watering Wise'),
              };
            }"""
        )
        print("\nLive DOM after Source B:")
        print(f"  {live}")
        if not live.get("heading"):
            print("WARN: heading text not found, but selects were verified.")

        print("\nPASS: Report 14 navigation + filter apply/verify OK for both sources.")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
