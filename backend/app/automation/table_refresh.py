"""Condition-based table refresh detection after Submit."""



from __future__ import annotations



import asyncio

import logging

from typing import Any



from playwright.async_api import Page



from app.automation.config import config

from app.automation.railmadad_wait import (
    RailMadadWaitResult,
    detect_terminal_portal_error,
    wait_for_railmadad_result,
)
from app.automation.report_errors import ReportStageError

from app.automation.selectors import selectors

from app.automation.utils import log_automation_event

from app.automation.wait_utils import poll_until



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





async def table_fingerprint(report_root: Any) -> str:

    """Lightweight fingerprint: headers, row count, first row snippet, draw counter."""

    try:

        fp = await report_root.locator("body").first.evaluate(FINGERPRINT_SCRIPT)

        return str(fp or "")

    except Exception:

        return ""





async def is_portal_loading(report_root: Any, page: Page) -> bool:

    """True when visible loading/processing indicators are present."""

    for selector in LOADING_SELECTORS:

        for scope in (report_root, page):

            try:

                loader = scope.locator(selector)

                if await loader.count() > 0 and await loader.first.is_visible():

                    return True

            except Exception:

                continue

    return False





async def wait_for_loaders(report_root: Any, page: Page, *, timeout_ms: int = 8_000) -> None:

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





async def wait_for_table_stable(

    report_root: Any,

    page: Page,

    *,

    old_fingerprint: str = "",

    report_slug: str = "",

    stage: str = "table_stable",

) -> bool:

    """Confirm fingerprint is non-empty and unchanged across a short stability window."""



    async def _stable() -> bool:

        await wait_for_loaders(report_root, page, timeout_ms=1_500)

        current = await table_fingerprint(report_root)

        if not current:

            return False

        if old_fingerprint and current == old_fingerprint:

            return False

        await asyncio.sleep(config.railmadad_stability_interval_ms / 1000.0)

        confirm = await table_fingerprint(report_root)

        if not confirm or confirm != current:

            return False

        if old_fingerprint and confirm == old_fingerprint:

            return False

        return True



    ok = await poll_until(

        _stable,

        interval_seconds=config.railmadad_poll_interval_ms / 1000.0,

        timeout_seconds=min(config.railmadad_normal_load_timeout, 15.0),

        reason=stage,

    )

    if report_slug:

        log_automation_event(

            logger,

            "table_stable_wait_completed",

            report_slug=report_slug,

            stage=stage,

            success=ok,

        )

    return ok





async def wait_for_table_refresh(

    report_root: Any,

    page: Page,

    old_fingerprint: str,

    *,

    report_slug: str = "",

    timeout_seconds: float | None = None,

) -> bool:

    """Wait until loaders finish and table fingerprint differs from pre-Submit value."""

    max_timeout = float(

        timeout_seconds

        if timeout_seconds is not None

        else config.railmadad_slow_load_timeout

    )

    result = await wait_for_adaptive_table_refresh(

        report_root,

        page,

        old_fingerprint,

        report_slug=report_slug,

        stage="result_table",

        max_timeout=max_timeout,

    )

    return result.success





async def wait_for_adaptive_table_refresh(

    report_root: Any,

    page: Page,

    old_fingerprint: str,

    *,

    report_slug: str = "",

    stage: str = "result_table",

    normal_timeout: float | None = None,

    max_timeout: float | None = None,

) -> RailMadadWaitResult:

    """Adaptive wait for post-submit table change + stability."""

    log_automation_event(

        logger,

        "table_refresh_wait_started",

        report_slug=report_slug,

        stage=stage,

        old_fingerprint=(old_fingerprint or "")[:120],

    )



    async def _ready() -> bool:

        return await wait_for_table_stable(

            report_root,

            page,

            old_fingerprint=old_fingerprint,

            report_slug=report_slug,

            stage=stage,

        )



    async def _loading() -> bool:

        if await is_portal_loading(report_root, page):

            return True

        current = await table_fingerprint(report_root)

        if not current:

            return True

        if old_fingerprint and current == old_fingerprint:

            return True

        return False



    result = await wait_for_railmadad_result(

        stage=stage,

        report_slug=report_slug or "unknown",

        ready_check=_ready,

        is_loading=_loading,

        is_terminal_error=lambda: detect_terminal_portal_error(page),

        normal_timeout=normal_timeout,

        max_timeout=max_timeout,

    )

    log_automation_event(

        logger,

        "table_refresh_wait_completed",

        report_slug=report_slug,

        stage=stage,

        refreshed=result.success,

        elapsed_seconds=result.elapsed_seconds,

        entered_extended=result.entered_extended,

        new_fingerprint=(await table_fingerprint(report_root))[:120],

    )

    return result





def require_fingerprint_changed(old_fingerprint: str, new_fingerprint: str, *, report_slug: str) -> None:

    """Block stale-data extraction when the table never changed after Submit."""

    if old_fingerprint and new_fingerprint == old_fingerprint:

        raise ReportStageError(

            code=f"{report_slug}.stale_table_data",

            message=f"Report {report_slug} table did not change after submit",

            stage="extract",

            report_slug=report_slug,

        )





async def _count_table_rows(report_root: Any) -> int:

    """Best-effort row count without importing generator (avoids circular imports)."""

    table = report_root.locator(selectors.report1_table).first

    if await table.count() == 0:

        table = report_root.locator(selectors.report1_grid).first

    if await table.count() == 0:

        return 0

    rows = table.locator("tbody tr")

    if await rows.count() == 0:

        rows = table.locator("tr")

    return await rows.count()





async def wait_for_table_data_rows(

    report_root: Any,

    page: Page,

    *,

    min_rows: int = 1,

    report_slug: str = "",

    timeout_seconds: float | None = None,

) -> bool:

    """Poll until the report table has at least ``min_rows`` populated data rows."""



    async def _has_data() -> bool:

        await wait_for_loaders(report_root, page, timeout_ms=1_500)

        fp = await table_fingerprint(report_root)

        if not fp:

            return False

        parts = fp.split("##")

        if len(parts) >= 2:

            try:

                row_count = int(parts[1])

            except (TypeError, ValueError):

                row_count = 0

            if row_count > min_rows:

                return True

            if row_count == min_rows and len(parts) > 2 and parts[2].strip():

                return True

        return await _count_table_rows(report_root) >= min_rows



    ok = await poll_until(

        _has_data,

        interval_seconds=0.08,

        timeout_seconds=float(

            timeout_seconds if timeout_seconds is not None else config.railmadad_normal_load_timeout

        ),

        reason="table_data_rows_poll",

    )

    if report_slug:

        log_automation_event(

            logger,

            "table_data_rows_wait_completed",

            report_slug=report_slug,

            success=ok,

            min_rows=min_rows,

        )

    return ok


