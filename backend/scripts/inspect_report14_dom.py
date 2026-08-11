"""Inspect live RailMadad Report 14 form controls over CDP."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.async_api import async_playwright


async def main() -> int:
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
        pages = []
        for ctx in browser.contexts:
            for p in ctx.pages:
                url = p.url or ""
                if "railmadad" not in url:
                    continue
                score = 0
                if "/rmmis/admin/" in url:
                    score += 100
                if "mis_reports" in url:
                    score += 50
                if "/final/" in url:
                    score -= 80
                pages.append((score, p))
        pages.sort(key=lambda x: x[0], reverse=True)
        if not pages:
            print("NO_MIS_PAGE")
            return 1
        page = pages[0][1]
        print("score", pages[0][0], "URL:", page.url)
        for s, p in pages:
            print(" candidate", s, p.url[:120])
        data = await page.evaluate(
            """() => {
              const ids = [
                'complaintZoneInput','complaintDivInput','viewType',
                'complaintSubTypeInput','fromInput','toInput',
                'outputTypeInput','outputInput','complaintDeptInput'
              ];
              const fields = {};
              for (const id of ids) {
                const el = document.getElementById(id);
                if (!el) { fields[id] = null; continue; }
                const tag = el.tagName;
                let selected = '';
                let opts = [];
                if (tag === 'SELECT') {
                  selected = (el.options[el.selectedIndex]?.text || '').trim();
                  opts = Array.from(el.options).slice(0, 20).map(o => (o.text||'').trim());
                } else {
                  selected = el.value || '';
                }
                fields[id] = { tag, selected, optionCount: el.options ? el.options.length : 0, options: opts };
              }
              // all selects with id/name containing output/view/zone
              const extras = [];
              document.querySelectorAll('select').forEach((el, i) => {
                if (i > 40) return;
                const id = el.id || '';
                const name = el.name || '';
                const labelNear = (el.closest('tr')?.innerText || el.parentElement?.innerText || '').slice(0, 80);
                extras.push({
                  id, name,
                  selected: (el.options[el.selectedIndex]?.text || '').trim(),
                  opts: Array.from(el.options).slice(0, 12).map(o => (o.text||'').trim()),
                  near: labelNear.replace(/\\s+/g, ' ').trim()
                });
              });
              const bodyText = (document.body.innerText || '').slice(0, 1500);
              return {
                title: document.title,
                hasHeading: bodyText.includes('Train Watering'),
                bodySnippet: bodyText.slice(0, 400),
                fields,
                selectCount: document.querySelectorAll('select').length,
                inputCount: document.querySelectorAll('input').length,
                iframeCount: document.querySelectorAll('iframe').length,
                extras: extras.slice(0, 25),
              };
            }"""
        )
        print(json.dumps(data, indent=2, ensure_ascii=True))
        # also check frames
        print("frames:", len(page.frames))
        for fr in page.frames:
            print(" frame", fr.name, fr.url[:120] if fr.url else "")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
