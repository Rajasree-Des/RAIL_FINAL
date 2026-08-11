"""Probe CDP tabs and optionally run remaining reports only."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.automation.browser import BrowserManager
from app.automation.config import config
from app.automation.handlers import get_handler
from app.automation.reports import (
    REPORT_3_TRAIN_NO,
    REPORT_4_TYPES,
    REPORT_5_SCR_TRAIN,
    REPORT_6_SCR_STATION,
    ReportCatalog,
)
from app.automation.run import attach_to_railmadad
from app.automation.schemas import MultiReportResult, ReportResult
from app.automation.session import MisSessionError, SessionManager
from app.automation.utils import log_automation_event


REMAINING = [
    REPORT_3_TRAIN_NO,
    REPORT_4_TYPES,
    REPORT_5_SCR_TRAIN,
    REPORT_6_SCR_STATION,
]

SCR_ONLY = [
    REPORT_5_SCR_TRAIN,
    REPORT_6_SCR_STATION,
]


async def probe() -> dict:
    manager = BrowserManager(cdp_url=config.chrome_debug_url)
    session = SessionManager(railmadad_url=config.railmadad_url)
    try:
        browser = await manager.connect()
        tabs = await session.discover_tabs(browser)
        info = [
            {
                "url": t.url,
                "title": t.title,
                "is_railmadad": t.is_railmadad,
            }
            for t in tabs
        ]
        try:
            page = await session.ensure_authenticated_mis_page(browser)
            return {
                "connected": True,
                "mis_ok": True,
                "mis_url": page.url,
                "tabs": info,
            }
        except MisSessionError as exc:
            return {
                "connected": True,
                "mis_ok": False,
                "error": str(exc),
                "tabs": info,
            }
    except Exception as exc:
        return {"connected": False, "mis_ok": False, "error": str(exc), "tabs": []}
    finally:
        await manager.close()


async def run_remaining(reports=None) -> MultiReportResult:
    """Run selected reports against live MIS (default: remaining four)."""
    from app.automation.browser import BrowserConnectionError, BrowserManager
    from app.automation.report_keys import canonicalize_report_key

    selected = list(reports or REMAINING)
    manager = BrowserManager(cdp_url=config.chrome_debug_url)
    session = SessionManager(railmadad_url=config.railmadad_url)
    report_results: list[ReportResult] = []

    try:
        browser = await manager.connect()
        page = await session.ensure_authenticated_mis_page(browser)
        print(f"MIS page: {page.url}")

        for report in selected:
            slug = canonicalize_report_key(report.slug)
            print(f"=== starting {slug} ===")
            try:
                page = await session.ensure_authenticated_mis_page(browser, page)
                handler = get_handler(slug)
                handler.bind_browser(browser)
                result = await handler.execute(page, session, report)
                report_results.append(result)
                print(
                    f"=== {slug}: {result.status} "
                    f"rows={result.source_row_count} "
                    f"pdf={result.pdf_path} err={result.error} ==="
                )
                page = await session.ensure_authenticated_mis_page(browser, page)
            except MisSessionError as exc:
                report_results.append(
                    ReportResult(
                        slug=slug,
                        dataset_key=slug,
                        status="failed",
                        error=exc.status.error,
                    )
                )
                return MultiReportResult(
                    success=False,
                    connected=True,
                    reports=report_results,
                    stopped_early=True,
                    stop_reason=exc.status.error_code or "MIS_SESSION_LOST",
                    error=exc.status.error,
                    error_code=exc.status.error_code,
                    session_valid=False,
                )
            except Exception as exc:
                print(f"=== {slug} EXCEPTION: {exc} ===")
                report_results.append(
                    ReportResult(
                        slug=slug,
                        dataset_key=slug,
                        status="failed",
                        error=str(exc),
                    )
                )
                try:
                    page = await session.ensure_authenticated_mis_page(browser, page)
                except MisSessionError as auth_exc:
                    return MultiReportResult(
                        success=False,
                        connected=True,
                        reports=report_results,
                        stopped_early=True,
                        stop_reason=auth_exc.status.error_code or "MIS_SESSION_LOST",
                        error=auth_exc.status.error,
                        error_code=auth_exc.status.error_code,
                        session_valid=False,
                    )

        ok = all(r.status == "success" for r in report_results)
        return MultiReportResult(success=ok, connected=True, reports=report_results)

    finally:
        await manager.close()


async def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "remaining"
    if mode == "probe":
        out = await probe()
    elif mode == "full":
        result = await attach_to_railmadad()
        out = {
            "success": result.success,
            "connected": result.connected,
            "stopped_early": result.stopped_early,
            "stop_reason": result.stop_reason,
            "error": result.error,
            "reports": [r.model_dump() for r in result.reports],
        }
    elif mode == "scr":
        result = await run_remaining(SCR_ONLY)
        out = {
            "success": result.success,
            "connected": result.connected,
            "stopped_early": result.stopped_early,
            "stop_reason": result.stop_reason,
            "error": result.error,
            "reports": [r.model_dump() for r in result.reports],
        }
    else:
        result = await run_remaining()
        out = {
            "success": result.success,
            "connected": result.connected,
            "stopped_early": result.stopped_early,
            "stop_reason": result.stop_reason,
            "error": result.error,
            "reports": [r.model_dump() for r in result.reports],
        }

    dest = ROOT / "storage" / "debug" / "live_remaining_result.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
