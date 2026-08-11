"""PDF archival handler for Phase 7 automation."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

import shutil

from playwright.async_api import (
    BrowserContext,
    Download,
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

logger = logging.getLogger(__name__)

POPUP_TIMEOUT_MS = 30_000
PAGE_LOAD_TIMEOUT_MS = 60_000
MIN_PDF_SIZE_BYTES = 100

PDF_BUTTON_TEXTS = ("PDF", "Export PDF", "Download PDF")
PRINT_BUTTON_TEXTS = ("Print", "Print Report", "Print Preview")


@dataclass
class PdfArchiveResult:
    """Outcome of a PDF archival attempt."""

    success: bool
    file_path: Path | None = None
    file_size: int = 0
    error: str | None = None
    source: str | None = None


class PdfArchiver:
    """Archives PDFs from export/print pages without affecting the main workflow."""

    def __init__(self, archive_dir: Path | str | None = None) -> None:
        configured = archive_dir or config.pdf_archive_dir
        self.archive_dir = ensure_directory(Path(configured).resolve())

    @staticmethod
    def is_valid_pdf(file_path: Path | str | None) -> bool:
        """Check if file exists, is non-empty, has .pdf extension, and PDF magic bytes."""
        if file_path is None:
            return False
        path = Path(file_path)
        if not path.exists():
            return False
        if path.stat().st_size < MIN_PDF_SIZE_BYTES:
            return False
        if path.suffix.lower() != ".pdf":
            return False
        try:
            with path.open("rb") as handle:
                if handle.read(4) != b"%PDF":
                    return False
        except OSError:
            return False
        return True

    def reuse_existing_pdf(
        self,
        existing_path: Path | str,
        report_slug: str,
    ) -> PdfArchiveResult:
        """Reuse an existing PDF file as the archive (copy if needed)."""
        log_automation_event(
            logger,
            "phase7b_started",
            report_slug=report_slug,
            source="phase6_reuse",
        )

        src_path = Path(existing_path)
        if not self.is_valid_pdf(src_path):
            return PdfArchiveResult(
                success=False,
                error=f"Existing PDF is invalid or missing: {existing_path}",
                source="phase6_reuse",
            )

        log_automation_event(
            logger,
            "phase7b_reusing_phase6_pdf",
            source_path=str(src_path),
        )

        if src_path.parent == self.archive_dir:
            file_size = src_path.stat().st_size
            log_automation_event(
                logger,
                "phase7b_pdf_archived",
                path=str(src_path),
                file_size=file_size,
                source="phase6_reuse",
            )
            log_automation_event(
                logger,
                "phase7b_completed",
                pdf_archived=True,
                source="phase6_reuse",
            )
            return PdfArchiveResult(
                success=True,
                file_path=src_path,
                file_size=file_size,
                source="phase6_reuse",
            )

        filename = self._generate_filename(report_slug)
        target_path = self._unique_path(self.archive_dir / filename)

        try:
            shutil.copy2(src_path, target_path)
            file_size = target_path.stat().st_size
            log_automation_event(
                logger,
                "phase7b_pdf_archived",
                path=str(target_path),
                file_size=file_size,
                source="phase6_reuse",
            )
            log_automation_event(
                logger,
                "phase7b_completed",
                pdf_archived=True,
                source="phase6_reuse",
            )
            return PdfArchiveResult(
                success=True,
                file_path=target_path,
                file_size=file_size,
                source="phase6_reuse",
            )
        except Exception as exc:
            error_msg = f"Failed to copy PDF: {exc}"
            log_automation_event(logger, "phase7b_error", error=error_msg)
            return PdfArchiveResult(
                success=False,
                error=error_msg,
                source="phase6_reuse",
            )

    def _generate_filename(self, report_slug: str) -> str:
        """Generate timestamped PDF filename (previous-day date + current time)."""
        timestamp = artifact_filename_timestamp()
        return f"{report_slug}_{timestamp}.pdf"

    def _unique_path(self, base_path: Path) -> Path:
        """Return a non-existing path, appending _N if needed."""
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

    async def find_pdf_button(
        self,
        root: ReportRoot,
        page: Page,
        timeout_ms: int = 10_000,
    ) -> Locator | None:
        """Find PDF export button in the page."""
        return await self._find_button(
            root,
            page,
            button_texts=PDF_BUTTON_TEXTS,
            additional_selectors=[
                "a[href*='pdf']",
                "button[onclick*='pdf']",
                "a[onclick*='pdf']",
                "#pdfBtn",
                "img[alt*='PDF']",
                "img[src*='pdf']",
            ],
            timeout_ms=timeout_ms,
        )

    async def find_print_button(
        self,
        root: ReportRoot,
        page: Page,
        timeout_ms: int = 10_000,
    ) -> Locator | None:
        """Find Print button in the page."""
        return await self._find_button(
            root,
            page,
            button_texts=PRINT_BUTTON_TEXTS,
            additional_selectors=[
                selectors.report_print_button,
                "a[onclick*='print']",
                "button[onclick*='print']",
                "#printBtn",
                ".print-btn",
            ],
            timeout_ms=timeout_ms,
        )

    async def _find_button(
        self,
        root: ReportRoot,
        page: Page,
        *,
        button_texts: tuple[str, ...],
        additional_selectors: list[str],
        timeout_ms: int,
    ) -> Locator | None:
        """Generic button finder."""
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
                ])

            for selector in additional_selectors:
                try:
                    candidates.append(search_root.locator(selector))
                except Exception:
                    pass

        while asyncio.get_running_loop().time() < deadline:
            for locator in candidates:
                try:
                    count = await locator.count()
                    for index in range(count):
                        candidate = locator.nth(index)
                        if await candidate.is_visible():
                            return candidate
                except Exception:
                    continue
            await asyncio.sleep(0.2)

        return None

    async def archive_from_export(
        self,
        page: Page,
        root: ReportRoot,
        report_slug: str,
    ) -> PdfArchiveResult:
        """Click PDF export button, capture PDF from new page, close, return to original."""
        log_automation_event(
            logger,
            "phase7b_fallback_export_started",
            report_slug=report_slug,
        )

        pdf_button = await self.find_pdf_button(root, page)
        if pdf_button is None:
            log_automation_event(logger, "pdf_button_not_found", source="export")
            return PdfArchiveResult(
                success=False,
                error="PDF export button not found",
                source="export",
            )

        return await self._click_and_capture(
            page=page,
            button=pdf_button,
            report_slug=report_slug,
        )

    async def archive_from_print(
        self,
        page: Page,
        root: ReportRoot,
        report_slug: str,
    ) -> PdfArchiveResult:
        """Click Print button, capture PDF from print page, close, return to original."""
        log_automation_event(
            logger,
            "phase7b_fallback_export_started",
            report_slug=report_slug,
            source="print",
        )

        print_button = await self.find_print_button(root, page)
        if print_button is None:
            log_automation_event(logger, "print_button_not_found", source="print")
            return PdfArchiveResult(
                success=False,
                error="Print button not found",
                source="print",
            )

        return await self._click_and_capture(
            page=page,
            button=print_button,
            report_slug=report_slug,
        )

    async def _try_download_capture(
        self,
        download: Download,
        target_path: Path,
    ) -> PdfArchiveResult | None:
        """Save a download event and return result if it is a valid PDF."""
        log_automation_event(
            logger,
            "phase7b_download_detected",
            suggested_filename=download.suggested_filename,
        )
        await download.save_as(str(target_path))
        if self.is_valid_pdf(target_path):
            file_size = target_path.stat().st_size
            log_automation_event(
                logger,
                "phase7b_pdf_archived",
                path=str(target_path),
                file_size=file_size,
                source="download",
            )
            log_automation_event(
                logger,
                "phase7b_completed",
                pdf_archived=True,
                source="download",
            )
            return PdfArchiveResult(
                success=True,
                file_path=target_path,
                file_size=file_size,
                source="download",
            )
        if target_path.exists():
            target_path.unlink(missing_ok=True)
        return None

    async def _try_popup_capture(
        self,
        page: Page,
        popup: Page,
        target_path: Path,
    ) -> PdfArchiveResult | None:
        """Capture PDF from a popup page."""
        log_automation_event(
            logger,
            "phase7b_popup_detected",
            popup_url=popup.url,
        )
        saved_path = await self._capture_pdf_from_page(popup, target_path)
        await self._close_popup_safely(popup)
        await self._restore_original_tab(page)

        if saved_path and self.is_valid_pdf(saved_path):
            file_size = saved_path.stat().st_size
            log_automation_event(
                logger,
                "phase7b_pdf_archived",
                path=str(saved_path),
                file_size=file_size,
                source="popup",
            )
            log_automation_event(
                logger,
                "phase7b_completed",
                pdf_archived=True,
                source="popup",
            )
            return PdfArchiveResult(
                success=True,
                file_path=saved_path,
                file_size=file_size,
                source="popup",
            )
        if saved_path and saved_path.exists():
            saved_path.unlink(missing_ok=True)
        return None

    async def _click_and_capture(
        self,
        page: Page,
        button: Locator,
        report_slug: str,
    ) -> PdfArchiveResult:
        """Click button and capture PDF from download event or popup."""
        filename = self._generate_filename(report_slug)
        target_path = self._unique_path(self.archive_dir / filename)

        try:
            download_task = asyncio.create_task(
                page.wait_for_event("download", timeout=POPUP_TIMEOUT_MS)
            )
            popup_task = asyncio.create_task(
                page.context.wait_for_event("page", timeout=POPUP_TIMEOUT_MS)
            )

            log_automation_event(logger, "pdf_button_click")
            await button.click()

            done, pending = await asyncio.wait(
                {download_task, popup_task},
                return_when=asyncio.FIRST_COMPLETED,
                timeout=(POPUP_TIMEOUT_MS / 1000) + 5,
            )

            if download_task in done:
                try:
                    download: Download = download_task.result()
                    result = await self._try_download_capture(download, target_path)
                    if result is not None:
                        for task in pending:
                            task.cancel()
                        return result
                except Exception as exc:
                    logger.debug("Download handling failed: %s", exc)

            if popup_task not in done:
                try:
                    await asyncio.wait_for(
                        popup_task,
                        timeout=(POPUP_TIMEOUT_MS / 1000) + 5,
                    )
                except TimeoutError:
                    logger.debug("Popup wait timed out after invalid download")

            if popup_task.done() and not popup_task.cancelled():
                try:
                    popup = popup_task.result()
                    result = await self._try_popup_capture(page, popup, target_path)
                    if result is not None:
                        return result
                except Exception as exc:
                    logger.debug("Popup handling failed: %s", exc)

            for task in (download_task, popup_task):
                if not task.done():
                    task.cancel()

            log_automation_event(
                logger,
                "phase7b_no_event",
                note="No valid download or popup PDF captured after button click",
            )
            return PdfArchiveResult(
                success=False,
                error="No valid download or popup PDF captured after clicking export button",
                source="fallback",
            )

        except Exception as exc:
            error_msg = f"PDF archive failed: {exc}"
            log_automation_event(logger, "phase7b_error", error=error_msg)
            await self._restore_original_tab(page)
            return PdfArchiveResult(
                success=False,
                error=error_msg,
                source="fallback",
            )

    async def _capture_pdf_from_page(
        self,
        popup: Page,
        target_path: Path,
    ) -> Path | None:
        """Capture PDF content from a page using multiple strategies."""
        try:
            await popup.wait_for_load_state("domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            logger.debug("Popup load timeout, continuing with capture attempt")

        popup_url = popup.url
        log_automation_event(
            logger,
            "pdf_capture_attempt",
            popup_url=popup_url,
        )

        if popup_url and popup_url.lower().endswith(".pdf"):
            saved = await self._fetch_pdf_from_url(popup, popup_url, target_path)
            if saved:
                return saved

        if popup_url and "pdf" in popup_url.lower() and popup_url not in ("about:blank", ""):
            saved = await self._fetch_pdf_from_url(popup, popup_url, target_path)
            if saved:
                return saved

        return await self._render_page_as_pdf(popup, target_path)

    async def _fetch_pdf_from_url(
        self,
        popup: Page,
        url: str,
        target_path: Path,
    ) -> Path | None:
        """Try to fetch PDF content directly from URL."""
        try:
            response = await popup.context.request.get(url)
            if response.ok:
                body = await response.body()
                if len(body) >= MIN_PDF_SIZE_BYTES:
                    target_path.write_bytes(body)
                    log_automation_event(
                        logger,
                        "pdf_fetched_from_url",
                        url=url,
                        size=len(body),
                    )
                    return target_path
        except Exception as exc:
            logger.debug("URL fetch failed: %s", exc)

        return None

    async def _render_page_as_pdf(
        self,
        popup: Page,
        target_path: Path,
    ) -> Path | None:
        """Render the page as PDF using Playwright's pdf() method."""
        try:
            pdf_bytes = await popup.pdf(
                format="A4",
                print_background=True,
                margin={"top": "0.5in", "bottom": "0.5in", "left": "0.5in", "right": "0.5in"},
            )
            if pdf_bytes and len(pdf_bytes) >= MIN_PDF_SIZE_BYTES:
                target_path.write_bytes(pdf_bytes)
                log_automation_event(
                    logger,
                    "pdf_rendered",
                    size=len(pdf_bytes),
                )
                return target_path
        except Exception as exc:
            logger.debug("Page PDF render failed: %s", exc)

        return None

    async def _close_popup_safely(self, popup: Page) -> None:
        """Close popup page safely."""
        try:
            if not popup.is_closed():
                await popup.close()
                log_automation_event(logger, "pdf_popup_closed")
        except Exception as exc:
            logger.debug("Error closing popup: %s", exc)

    async def _restore_original_tab(self, page: Page) -> bool:
        """Bring the original page back to focus."""
        try:
            await page.bring_to_front()
            log_automation_event(
                logger,
                "original_tab_restored",
                url=page.url,
            )
            return True
        except Exception as exc:
            log_automation_event(
                logger,
                "original_tab_restore_failed",
                error=str(exc),
            )
            return False

    async def archive_pdf(
        self,
        page: Page,
        root: ReportRoot,
        report_slug: str,
        *,
        use_print: bool = False,
        existing_pdf_path: Path | str | None = None,
    ) -> PdfArchiveResult:
        """
        Main entry point for PDF archival.
        
        Reuses existing Phase 6 PDF if valid; otherwise falls back to export/print.
        
        Args:
            page: The main browser page
            root: Report root (page or frame)
            report_slug: Report identifier for naming
            use_print: If True, use Print button instead of PDF export
            existing_pdf_path: Path to PDF from Phase 6 download (reuse if valid)
        
        Returns:
            PdfArchiveResult with success status and file path
        """
        if existing_pdf_path and self.is_valid_pdf(existing_pdf_path):
            return self.reuse_existing_pdf(existing_pdf_path, report_slug)

        log_automation_event(
            logger,
            "phase7b_started",
            report_slug=report_slug,
            source="fallback",
            reason="no_valid_phase6_pdf" if existing_pdf_path else "no_existing_pdf",
        )

        if use_print:
            return await self.archive_from_print(page, root, report_slug)
        return await self.archive_from_export(page, root, report_slug)
