"""Report download engine for Phase 6."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from playwright.async_api import (
    Download,
    FrameLocator,
    Locator,
    Page,
    TimeoutError as PlaywrightTimeoutError,
)

from app.automation.config import config
from app.automation.filters import ReportRoot
from app.automation.selectors import selectors
from app.automation.utils import (
    artifact_filename_timestamp,
    ensure_directory,
    log_automation_event,
)
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)

PHASE6_BEFORE_SCREENSHOT = "phase6_before_download.png"
PHASE6_AFTER_SCREENSHOT = "phase6_after_download.png"

VALID_EXTENSIONS = frozenset({".xlsx", ".xls", ".csv", ".zip", ".pdf"})
SPREADSHEET_EXTENSIONS = frozenset({".xlsx", ".xls", ".csv"})
MIN_FILE_SIZE_BYTES = 1

DOWNLOAD_WAIT_TIMEOUT_MS = 60_000
SPREADSHEET_SEARCH_TIMEOUT_MS = 30_000
DOWNLOAD_TIMEOUT_MS = 120_000
POPUP_TIMEOUT_MS = 30_000

SPREADSHEET_BUTTON_TEXTS = (
    "Export to Excel",
    "Export Excel",
    "Excel",
    "Export",
    "Download",
    "Download Excel",
)

PDF_BUTTON_TEXTS = ("PDF",)

EXPORT_NOT_FOUND_ERROR = "Export/Download button not found within timeout"


class DownloadError(AppException):
    """Raised when report download fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="DOWNLOAD_ERROR")


@dataclass
class DownloadResult:
    """Outcome of a download attempt."""

    success: bool
    file_path: Path | None = None
    file_size: int = 0
    error: str | None = None
    export_format: str | None = None


class ReportDownloader:
    """Downloads reports from the portal into local project storage."""

    def __init__(self, downloads_dir: Path | str | None = None) -> None:
        configured = downloads_dir or config.downloads_dir
        self.downloads_dir = ensure_directory(Path(configured).resolve())

    def _generate_filename(self, report_slug: str = "report1", extension: str = ".xlsx") -> str:
        """Generate timestamped filename for the download (previous-day date)."""
        timestamp = artifact_filename_timestamp()
        ext = extension if extension.startswith(".") else f".{extension}"
        return f"{report_slug}_{timestamp}{ext}"

    def _unique_target_path(self, base_path: Path) -> Path:
        """Return a non-existing path, appending _N before the extension if needed."""
        if not base_path.exists():
            return base_path

        stem = base_path.stem
        suffix = base_path.suffix
        counter = 1
        while True:
            candidate = base_path.with_name(f"{stem}_{counter}{suffix}")
            if not candidate.exists():
                return candidate
            counter += 1

    async def capture_before_download(self, page: Page) -> str:
        path = await self._capture(page, PHASE6_BEFORE_SCREENSHOT)
        log_automation_event(logger, "phase6_before_download_screenshot", path=path)
        return path

    async def capture_after_download(self, page: Page) -> str:
        path = await self._capture(page, PHASE6_AFTER_SCREENSHOT)
        log_automation_event(logger, "phase6_after_download_screenshot", path=path)
        return path

    async def _capture(self, page: Page, filename: str) -> str:
        directory = ensure_directory(Path(config.debug_screenshots_dir))
        path = directory / filename
        await page.screenshot(path=str(path), full_page=True)
        return str(path)

    async def wait_for_download_ready(
        self,
        root: ReportRoot,
        page: Page,
        timeout_ms: int = DOWNLOAD_WAIT_TIMEOUT_MS,
    ) -> tuple[Locator | None, str | None]:
        log_automation_event(logger, "report_ready", status="waiting_for_export_button")

        try:
            await page.wait_for_load_state("domcontentloaded", timeout=10_000)
        except PlaywrightTimeoutError:
            logger.debug("domcontentloaded timeout; continuing to look for export button")
        try:
            await page.wait_for_load_state("networkidle", timeout=5_000)
        except PlaywrightTimeoutError:
            logger.debug("Network idle timeout; continuing to look for export button")

        export_button = await self._find_spreadsheet_export_button(
            root,
            page,
            SPREADSHEET_SEARCH_TIMEOUT_MS,
        )
        if export_button is not None:
            log_automation_event(logger, "report_ready", status="export_button_found", format="spreadsheet")
            return export_button, "spreadsheet"

        export_button = await self._find_pdf_export_button(
            root,
            page,
            max(timeout_ms - SPREADSHEET_SEARCH_TIMEOUT_MS, 5_000),
        )
        if export_button is None:
            log_automation_event(logger, "export_button_not_found", timeout_ms=timeout_ms)
            return None, None

        log_automation_event(logger, "report_ready", status="export_button_found", format="pdf")
        return export_button, "pdf"

    async def _find_spreadsheet_export_button(
        self,
        root: ReportRoot,
        page: Page,
        timeout_ms: int,
    ) -> Locator | None:
        return await self._find_export_button(
            root,
            page,
            timeout_ms,
            button_texts=SPREADSHEET_BUTTON_TEXTS,
            include_pdf_selectors=False,
            reject_pdf_labels=True,
        )

    async def _find_pdf_export_button(
        self,
        root: ReportRoot,
        page: Page,
        timeout_ms: int,
    ) -> Locator | None:
        log_automation_event(logger, "export_pdf_fallback", status="searching")
        return await self._find_export_button(
            root,
            page,
            timeout_ms,
            button_texts=PDF_BUTTON_TEXTS,
            include_pdf_selectors=True,
            reject_pdf_labels=False,
        )

    async def _find_export_button(
        self,
        root: ReportRoot,
        page: Page,
        timeout_ms: int,
        *,
        button_texts: tuple[str, ...],
        include_pdf_selectors: bool,
        reject_pdf_labels: bool,
    ) -> Locator | None:
        deadline = asyncio.get_running_loop().time() + (timeout_ms / 1000)
        search_roots: list[ReportRoot] = [root]
        if root is not page:
            search_roots.append(page)

        candidates: list[Locator] = []
        for search_root in search_roots:
            for text in button_texts:
                candidates.extend([
                    search_root.locator(f"a:has-text('{text}')"),
                    search_root.locator(f"button:has-text('{text}')"),
                    search_root.locator(f"input[value*='{text}']"),
                    search_root.locator(f"input[type='button'][value='{text}']"),
                    search_root.locator(f"input[type='submit'][value='{text}']"),
                ])

            candidates.append(search_root.locator(selectors.report1_export))
            candidates.extend([
                search_root.locator("a[href*='export']"),
                search_root.locator("a[href*='download']"),
                search_root.locator("a[href*='xlsx']"),
                search_root.locator("button[onclick*='export']"),
                search_root.locator("a[onclick*='export']"),
                search_root.locator("button[onclick*='excel']"),
                search_root.locator("a[onclick*='excel']"),
                search_root.locator("#exportBtn"),
                search_root.locator("#downloadBtn"),
                search_root.locator(".export-btn"),
                search_root.locator(".download-btn"),
                search_root.locator("img[alt*='Excel']").locator(".."),
                search_root.locator("img[src*='excel']").locator(".."),
            ])

            if include_pdf_selectors:
                candidates.extend([
                    search_root.locator("a[href*='pdf']"),
                    search_root.locator("button[onclick*='pdf']"),
                    search_root.locator("a[onclick*='pdf']"),
                    search_root.locator("#pdfBtn"),
                    search_root.locator("img[alt*='PDF']").locator(".."),
                    search_root.locator("img[src*='pdf']").locator(".."),
                ])

        while asyncio.get_running_loop().time() < deadline:
            for locator in candidates:
                try:
                    count = await locator.count()
                    for index in range(count):
                        candidate = locator.nth(index)
                        if not await candidate.is_visible():
                            continue
                        if not await self._is_enabled(candidate):
                            continue
                        label = await self._get_button_label(candidate)
                        if reject_pdf_labels and self._is_pdf_only_button(label):
                            continue
                        log_automation_event(
                            logger,
                            "export_button_found",
                            button_label=label,
                        )
                        return candidate
                except Exception as exc:
                    logger.debug("Error checking export locator: %s", exc)

            await asyncio.sleep(0.35)

        return None

    @staticmethod
    def _is_pdf_only_button(label: str) -> bool:
        normalized = label.strip().lower()
        return normalized == "pdf" or normalized.endswith(" pdf")

    async def _is_enabled(self, locator: Locator) -> bool:
        try:
            disabled = await locator.get_attribute("disabled")
            if disabled is not None:
                return False
            class_attr = await locator.get_attribute("class") or ""
            if "disabled" in class_attr.lower():
                return False
            return True
        except Exception:
            return True

    async def _get_button_label(self, locator: Locator) -> str:
        try:
            text = (await locator.inner_text()).strip()
            if text:
                return text
        except Exception:
            pass
        try:
            return (await locator.get_attribute("value") or "").strip()
        except Exception:
            return ""

    async def download_report(
        self,
        root: ReportRoot,
        page: Page,
        report_slug: str = "report1",
    ) -> DownloadResult:
        log_automation_event(
            logger,
            "download_directory",
            path=str(self.downloads_dir),
        )

        export_button, export_format = await self.wait_for_download_ready(root, page)
        if export_button is None:
            return DownloadResult(success=False, error=EXPORT_NOT_FOUND_ERROR)

        default_extension = ".pdf" if export_format == "pdf" else ".xlsx"
        target_filename = self._generate_filename(report_slug, default_extension)
        target_path = self._unique_target_path(self.downloads_dir / target_filename)

        log_automation_event(
            logger,
            "download_started",
            target_path=str(target_path),
            export_format=export_format,
        )

        try:
            saved_path = await self._click_and_save(
                page,
                export_button,
                target_path,
                use_popup_capture=export_format == "pdf",
            )
            if saved_path is None:
                return DownloadResult(
                    success=False,
                    error="Could not capture download from button click",
                    export_format=export_format,
                )

            file_size = saved_path.stat().st_size
            log_automation_event(
                logger,
                "download_completed",
                file_path=str(saved_path),
                file_size=file_size,
                export_format=export_format,
            )
            log_automation_event(
                logger,
                "file_saved",
                file_path=str(saved_path),
                file_size=file_size,
            )

            if not await self.validate_download(saved_path):
                return DownloadResult(
                    success=False,
                    file_path=saved_path,
                    error="Downloaded file failed validation (missing, empty, or invalid extension)",
                    export_format=export_format,
                )

            return DownloadResult(
                success=True,
                file_path=saved_path,
                file_size=file_size,
                export_format=export_format,
            )

        except PlaywrightTimeoutError as exc:
            error_msg = f"Download timeout: {exc}"
            log_automation_event(logger, "download_failed", error=error_msg)
            return DownloadResult(success=False, error=error_msg, export_format=export_format)
        except Exception as exc:
            error_msg = f"Download failed: {exc}"
            log_automation_event(logger, "download_failed", error=error_msg)
            return DownloadResult(success=False, error=error_msg, export_format=export_format)

    async def _click_and_save(
        self,
        page: Page,
        export_button: Locator,
        target_path: Path,
        *,
        use_popup_capture: bool,
    ) -> Path | None:
        if use_popup_capture:
            return await self._click_with_download_or_popup(page, export_button, target_path)

        try:
            async with page.expect_download(timeout=DOWNLOAD_TIMEOUT_MS) as download_info:
                await export_button.click()
            download: Download = await download_info.value
            return await self._save_browser_download(download, target_path)
        except PlaywrightTimeoutError:
            logger.debug("No browser download event after spreadsheet export click")
            return None

    async def _click_with_download_or_popup(
        self,
        page: Page,
        export_button: Locator,
        target_path: Path,
    ) -> Path | None:
        """Click once and capture either a browser download or popup export."""
        download_wait = asyncio.create_task(
            page.wait_for_event("download", timeout=POPUP_TIMEOUT_MS)
        )
        popup_wait = asyncio.create_task(
            page.context.wait_for_event("page", timeout=POPUP_TIMEOUT_MS)
        )

        await export_button.click()

        done, pending = await asyncio.wait(
            {download_wait, popup_wait},
            return_when=asyncio.FIRST_COMPLETED,
            timeout=(POPUP_TIMEOUT_MS / 1000) + 5,
        )
        for task in pending:
            task.cancel()

        if download_wait in done:
            try:
                download = download_wait.result()
                if download is not None:
                    return await self._save_browser_download(download, target_path)
            except Exception as exc:
                logger.debug("Download event handling failed: %s", exc)

        if popup_wait in done:
            try:
                popup = popup_wait.result()
                if popup is not None:
                    return await self._save_popup_content(page, popup, target_path)
            except Exception as exc:
                logger.debug("Popup event handling failed: %s", exc)

        return None

    async def _save_browser_download(
        self,
        download: Download,
        target_path: Path,
    ) -> Path:
        suggested_filename = download.suggested_filename
        log_automation_event(
            logger,
            "download_received",
            suggested_filename=suggested_filename,
            method="browser_download",
        )
        final_path = self._resolve_target_path(target_path, suggested_filename)
        final_path = self._unique_target_path(final_path)
        await download.save_as(str(final_path))
        return final_path

    async def _save_popup_content(
        self,
        page: Page,
        popup: Page,
        target_path: Path,
    ) -> Path | None:
        await popup.wait_for_load_state("domcontentloaded", timeout=DOWNLOAD_TIMEOUT_MS)
        popup_url = popup.url
        log_automation_event(
            logger,
            "download_popup_opened",
            popup_url=popup_url,
            method="popup",
        )

        final_path = self._unique_target_path(target_path.with_suffix(".pdf"))

        if popup_url and popup_url not in ("about:blank", ""):
            response = await page.context.request.get(popup_url)
            if response.ok:
                body = await response.body()
                if len(body) >= MIN_FILE_SIZE_BYTES:
                    final_path.write_bytes(body)
                    await popup.close()
                    return final_path

        pdf_bytes = await popup.pdf()
        if pdf_bytes and len(pdf_bytes) >= MIN_FILE_SIZE_BYTES:
            final_path.write_bytes(pdf_bytes)
            await popup.close()
            return final_path

        await popup.close()
        return None

    def _resolve_target_path(self, target_path: Path, suggested_filename: str | None) -> Path:
        if not suggested_filename:
            return target_path

        extension = Path(suggested_filename).suffix.lower()
        if extension in VALID_EXTENSIONS:
            return target_path.with_suffix(extension)
        return target_path

    async def validate_download(self, file_path: Path) -> bool:
        if not file_path.exists():
            log_automation_event(logger, "download_validation_failed", reason="file_not_found")
            return False

        extension = file_path.suffix.lower()
        if extension not in VALID_EXTENSIONS:
            log_automation_event(
                logger,
                "download_validation_failed",
                reason="invalid_extension",
                extension=extension,
            )
            return False

        file_size = file_path.stat().st_size
        if file_size < MIN_FILE_SIZE_BYTES:
            log_automation_event(
                logger,
                "download_validation_failed",
                reason="file_empty",
                file_size=file_size,
            )
            return False

        log_automation_event(
            logger,
            "file_verified",
            file_path=str(file_path),
            file_size=file_size,
            extension=extension,
        )
        return True
