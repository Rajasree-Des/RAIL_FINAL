"""RailMadad portal automation — login, navigate, download only."""

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from app.config import settings
from app.core.download_validator import validate_download
from app.core.job_manager import job_manager
from app.core.notifier import BackendNotifier
from app.core.retry import retry_async

logger = logging.getLogger(__name__)


class RailMadadRunner:
    """Executes the full download flow without processing Excel."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.run_id = config["run_id"]
        self.notifier = BackendNotifier(
            service_token=config.get("service_token"),
            base_url=config.get("backend_base_url"),
        )
        self.downloads_root = Path(
            config.get("downloads_root") or settings.downloads_root
        )
        self.screenshots_dir = Path(settings.screenshots_dir)

    async def execute(self) -> None:
        self.downloads_root.mkdir(parents=True, exist_ok=True)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

        await self.notifier.log(self.run_id, "Opening browser", "info")

        if settings.demo_mode:
            await self._execute_demo()
            return

        try:
            await self._execute_playwright()
        except Exception as e:
            logger.exception("Playwright run failed")
            screenshot = await self._capture_failure_screenshot(None)
            await self.notifier.report_failure(self.run_id, str(e), screenshot)
            job_manager.update_status(self.run_id, "failed")

    async def _execute_demo(self) -> None:
        """Demo flow when portal is unavailable — creates placeholder downloads."""
        await self.notifier.log(self.run_id, "Demo mode: simulating RailMadad flow", "info")
        reports = self.config.get("report_sequence") or [
            {"name": "Daily Complaints", "report_path": "/reports/daily"},
        ]
        success = 0
        failures = 0

        for idx, report in enumerate(reports):
            if not await job_manager.wait_if_paused(self.run_id):
                await self.notifier.log(self.run_id, "Run stopped", "warning")
                break

            name = report.get("name", f"report-{idx}")
            await self.notifier.log(self.run_id, f"Navigating to {name}", "info")
            await asyncio.sleep(1)

            folder = self.downloads_root / self.config.get("download_folder", "railmadad")
            folder.mkdir(parents=True, exist_ok=True)
            date_str = datetime.now(UTC).strftime("%Y-%m-%d")
            file_path = folder / f"{name.replace(' ', '_').lower()}_{date_str}.xlsx"

            # Placeholder binary — NOT processed, just stored
            file_path.write_bytes(b"PK\x03\x04" + b"\x00" * 200)

            valid, msg = validate_download(file_path)
            if valid:
                await self.notifier.report_download(
                    self.run_id,
                    str(file_path),
                    name,
                    file_path.stat().st_size,
                )
                success += 1
            else:
                await self.notifier.log(self.run_id, f"Validation failed: {msg}", "error")
                failures += 1

            delay = self.config.get("delay_seconds", 5)
            if idx < len(reports) - 1:
                await asyncio.sleep(delay)

        await self.notifier.report_complete(self.run_id, success, failures)
        job_manager.update_status(
            self.run_id, "completed" if failures == 0 else "failed"
        )

    async def _execute_playwright(self) -> None:
        browser_type = self.config.get("browser", "chromium")
        headless = self.config.get("headless", True)
        timeout = self.config.get("timeout_ms", 60000)
        retry_count = self.config.get("retry_count", 3)

        async with async_playwright() as pw:
            launcher = getattr(pw, browser_type, pw.chromium)
            browser: Browser = await launcher.launch(headless=headless)
            context = await self._create_context(browser)
            page = await context.new_page()
            page.set_default_timeout(timeout)

            try:
                await self.notifier.log(self.run_id, "Logging in to portal", "info")
                await retry_async(
                    lambda: self._login(page),
                    max_attempts=retry_count,
                )

                reports = self.config.get("report_sequence") or []
                success = 0
                failures = 0

                for idx, report in enumerate(reports):
                    if not await job_manager.wait_if_paused(self.run_id):
                        break

                    name = report.get("name", f"report-{idx}")
                    try:
                        path = await retry_async(
                            lambda r=report, n=name: self._download_report(
                                page, context, r, n
                            ),
                            max_attempts=retry_count,
                        )
                        valid, msg = validate_download(path)
                        if valid:
                            await self.notifier.report_download(
                                self.run_id,
                                str(path),
                                name,
                                path.stat().st_size,
                            )
                            success += 1
                        else:
                            failures += 1
                            await self.notifier.log(
                                self.run_id, f"{name}: {msg}", "error"
                            )
                    except Exception as e:
                        failures += 1
                        screenshot = await self._capture_failure_screenshot(page)
                        await self.notifier.log(
                            self.run_id, f"{name} failed: {e}", "error"
                        )
                        if screenshot:
                            await self.notifier.callback(
                                {
                                    "run_id": self.run_id,
                                    "status": "running",
                                    "artifact": {
                                        "type": "screenshot",
                                        "file_path": screenshot,
                                    },
                                }
                            )

                    delay = self.config.get("delay_seconds", 5)
                    if idx < len(reports) - 1:
                        await asyncio.sleep(delay)

                session_state = await context.storage_state()
                import json

                session_json = json.dumps(session_state)
                await self.notifier.report_complete(
                    self.run_id, success, failures, session_json
                )
                job_manager.update_status(
                    self.run_id, "completed" if failures == 0 else "failed"
                )
            finally:
                await self.notifier.log(self.run_id, "Logging out", "info")
                await browser.close()

    async def _create_context(self, browser: Browser) -> BrowserContext:
        session = self.config.get("session_state")
        if session:
            import json

            state = json.loads(session) if isinstance(session, str) else session
            return await browser.new_context(storage_state=state)
        return await browser.new_context()

    async def _login(self, page: Page) -> None:
        portal_url = self.config["portal_url"]
        username = self.config["username"]
        password = self.config["password"]

        await page.goto(portal_url, wait_until="networkidle")
        # Generic selectors — configurable via profile filters in production
        await page.fill('input[name="username"], input[type="email"], #username', username)
        await page.fill('input[name="password"], input[type="password"], #password', password)
        await page.click('button[type="submit"], input[type="submit"], .login-btn')
        await page.wait_for_load_state("networkidle")

    async def _download_report(
        self,
        page: Page,
        context: BrowserContext,
        report: dict[str, Any],
        name: str,
    ) -> Path:
        report_path = report.get("report_path", "/reports")
        portal_url = self.config["portal_url"].rstrip("/")
        await page.goto(f"{portal_url}{report_path}", wait_until="networkidle")

        filters = report.get("filters", {})
        for selector, value in filters.items():
            if await page.locator(selector).count() > 0:
                await page.fill(selector, str(value))

        folder = self.downloads_root / self.config.get("download_folder", "railmadad")
        folder.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        dest = folder / f"{name.replace(' ', '_').lower()}_{date_str}.xlsx"

        async with page.expect_download() as download_info:
            await page.click(
                'a[download], button:has-text("Download"), .download-btn, #download'
            )
        download = await download_info.value
        await download.save_as(str(dest))
        return dest

    async def _capture_failure_screenshot(self, page: Page | None) -> str | None:
        try:
            if page is None:
                return None
            path = self.screenshots_dir / f"{self.run_id}_{datetime.now(UTC).strftime('%H%M%S')}.png"
            await page.screenshot(path=str(path), full_page=True)
            return str(path)
        except Exception:
            logger.exception("Screenshot capture failed")
            return None
