"""Condition-based table refresh detection after Submit."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from playwright.async_api import Page

from app.automation.filters import ReportRoot
from app.automation.utils import log_automation_event
from app.automation.wait_utils import poll_until, tracked_sleep

logger = logging.getLogger(__name__)

LOADING_SELECTORS = (
    ".loading",
    ".loader",
    "[class*='loading']",
    "[class*='spinner']",
    "[class*='Loader']",
    "#loading",
    "#loader",
    "text=/Loading\\.?\\.?/i",
    ".dataTables_processing",
)

FINGERPRINT_SCRIPT = """
() => {
  const table = document.querySelector('table.dataTable, table:has(tbody tr), #reportData table, table');
  if (!table) return '';
  const headers = Array.from(table.querySelectorAll('thead th, tr:first-child th')).map(
    (h) => (h.textContent || '').trim()
  ).filter(Boolean).join('|');
  const firstRow = table.querySelector('tbody tr, tr:nth-child(2)');
  const firstText = firstRow ? (firstRow.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 120) : '';
  const rowCount = table.querySelectorAll('tbody tr').length || table.querySelectorAll('tr').length;
  let draw = '';
  try {
    const $ = window.jQuery || window.$;
    if ($ && $.fn && $.fn.dataTable && $.fn.dataTable.isDataTable(table)) {
      const info = $(table).DataTable().page.info();
      draw = String(info.recordsDisplay || info.recordsTotal || '');
    }
  } catch (_) {}
  return [headers, rowCount, firstText, draw].join('##');
}
"""


async def table_fingerprint(report_root: ReportRoot) -> str:
    """Lightweight fingerprint: headers, row count, first row snippet, draw counter."""
    try:
        fp = await report_root.locator("body").first.evaluate(FINGERPRINT_SCRIPT)
        return str(fp or "")
    except Exception:
        return ""


async def wait_for_loaders(report_root: ReportRoot, page: Page, *, timeout_ms: int = 8_000) -> None:
    for selector in LOADING_SELECTORS:
        try:
            loader = report_root.locator(selector)
            if await loader.count() == 0:
                loader = page.locator(selector)
            if await loader.count() == 0:
                continue
            await loader.first.wait_for(state="hidden", timeout=timeout_ms)
        except Exception:
            continue


async def wait_for_table_refresh(
    report_root: ReportRoot,
    page: Page,
    old_fingerprint: str,
    *,
    report_slug: str = "",
    timeout_seconds: float = 45.0,
) -> bool:
    """Wait until loaders finish and table fingerprint differs from pre-Submit value."""
    log_automation_event(
        logger,
        "table_refresh_wait_started",
        report_slug=report_slug,
        old_fingerprint=(old_fingerprint or "")[:120],
    )

    async def _refreshed() -> bool:
        await wait_for_loaders(report_root, page, timeout_ms=2_000)
        current = await table_fingerprint(report_root)
        if not current:
            return False
        if old_fingerprint and current == old_fingerprint:
            return False
        # Stable confirm: fingerprint unchanged on immediate re-read
        confirm = await table_fingerprint(report_root)
        return bool(confirm) and confirm == current and (
            not old_fingerprint or confirm != old_fingerprint
        )

    ok = await poll_until(
        _refreshed,
        interval_seconds=0.08,
        timeout_seconds=timeout_seconds,
        reason="table_refresh_poll",
    )
    log_automation_event(
        logger,
        "table_refresh_wait_completed",
        report_slug=report_slug,
        refreshed=ok,
        new_fingerprint=(await table_fingerprint(report_root))[:120],
    )
    return ok
