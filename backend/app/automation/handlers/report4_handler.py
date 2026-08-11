"""Report 4 / types handler: 7 complaint Types x Top 10 each."""

from __future__ import annotations

import csv
import logging
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.automation.config import config
from app.automation.generator import ReportGenerationError
from app.automation.table_refresh import table_fingerprint, wait_for_table_refresh
from app.automation.report4_filters import (
    TypeConfig,
    get_report4_filters_for_type,
    get_type_configs,
)
from app.automation.portal_from_date import (
    apply_previous_from_date,
    log_phase2_submit_clicked,
)
from app.automation.reports import ReportDefinition
from app.automation.run_context import get_run_context
from app.automation.schemas import ReportResult
from app.automation.table_extractor import TableExtractor
from app.automation.table_sort import ReceivedSortError
from app.automation.utils import ensure_directory, log_automation_event, resolve_report_dir
from app.automation.wait_utils import tracked_sleep

from .base import BaseReportHandler

if TYPE_CHECKING:
    from playwright.async_api import Page

    from app.automation.session import SessionManager

logger = logging.getLogger(__name__)

# First attempt + one retry
TYPE_SUBMIT_MAX_ATTEMPTS = 2


def type_slug(type_name: str) -> str:
    """Filesystem slug for a complaint type name."""
    return type_name.lower().replace(" ", "_").replace("&", "and")


class Report4Handler(BaseReportHandler):
    """Execute cause-wise Top 10 per Type workflow (canonical key: types)."""

    async def execute(
        self,
        page: "Page",
        session: "SessionManager",
        report: ReportDefinition,
    ) -> ReportResult:
        started_at = datetime.now(UTC).isoformat()
        t0 = time.perf_counter()
        page = await self.ensure_mis_page(page, session, f"{report.slug}_start", report=report)
        type_configs = get_type_configs()

        ctx = get_run_context()
        run_id = ctx.run_id if ctx is not None else str(uuid.uuid4())
        if ctx is not None:
            ctx.freeze_report_from_date(report.slug)
        extracted_dir = ensure_directory(
            resolve_report_dir(config.extracted_data_dir, report.slug) / run_id
        )

        source_paths: list[str] = []
        row_counts: dict[str, int] = {}
        total_rows = 0
        type_results: list[dict[str, Any]] = []
        failed_types: list[str] = []

        await self.navigation.navigate_to_report(page, report)
        page = await self.ensure_mis_page(page, session, f"{report.slug}_after_nav", report=report)
        try:
            await page.wait_for_selector("#complaintTypeInput, #viewType", timeout=15_000)
        except Exception:
            pass

        for type_config in type_configs:
            page = await self.ensure_mis_page(
                page, session, f"{report.slug}_{type_config.name}", report=report
            )
            outcome = await self._run_type_with_retry(
                page,
                session,
                report,
                type_config,
                extracted_dir,
            )
            page = outcome.get("page", page)
            type_results.append(outcome)

            if outcome.get("status") == "success" and outcome.get("csv_path"):
                source_paths.append(str(outcome["csv_path"]))
                rows = int(outcome.get("row_count") or 0)
                row_counts[type_config.name] = rows
                total_rows += rows
            else:
                failed_types.append(type_config.name)

        if not source_paths:
            return self.build_failed_result(
                report.slug,
                "No complaint type data extracted",
                row_counts=row_counts,
            )

        combined_path = extracted_dir / "types_combined_index.csv"
        self._write_combined_index(combined_path, type_results)
        log_automation_event(
            logger,
            "report4_index_saved",
            path=str(combined_path),
            success_count=len(source_paths),
            failed_types=failed_types,
            run_id=run_id,
        )

        extraction_seconds = time.perf_counter() - t0
        log_automation_event(
            logger,
            "report_extraction_completed",
            slug=report.slug,
            type_count=len(source_paths),
            total_rows=total_rows,
            failed_types=failed_types,
            duration_seconds=round(extraction_seconds, 3),
        )

        # Run ingest/process inline so we can set partial_success after artifacts.
        saved_defer: bool | None = None
        if ctx is not None:
            saved_defer = ctx.defer_processing
            ctx.defer_processing = False
        t_proc = time.perf_counter()
        try:
            result = await self.finalize_after_extract(
                slug=report.slug,
                csv_path=combined_path,
                source_paths=source_paths,
                row_counts=row_counts,
                source_row_count=total_rows,
                started_at=started_at,
                extraction_seconds=round(extraction_seconds, 3),
            )
        finally:
            if ctx is not None and saved_defer is not None:
                ctx.defer_processing = saved_defer
        processing_seconds = time.perf_counter() - t_proc
        result = result.model_copy(
            update={"processing_seconds": round(processing_seconds, 3)}
        )

        log_automation_event(
            logger,
            "ingestion:types",
            path=str(combined_path),
            ingestion_success=result.ingestion_success,
        )
        log_automation_event(
            logger,
            "processing:types",
            excel_path=result.excel_path,
            pdf_path=result.pdf_path,
            processing_success=result.processing_success,
            duration_seconds=round(processing_seconds, 3),
        )
        if ctx is not None:
            ctx.timing.spans["processing:types"] = round(processing_seconds, 3)
            ctx.timing.record_report_span("types", "processing", processing_seconds)

        if failed_types and result.status == "success":
            result = result.model_copy(
                update={
                    "status": "partial_success",
                    "error": f"Failed types: {', '.join(failed_types)}",
                }
            )
            if ctx is not None:
                ctx.merge_result(result)

        if result.pdf_preview_url or result.excel_download_url:
            log_automation_event(
                logger,
                "report4_artifacts_registered",
                pdf_preview_url=result.pdf_preview_url,
                pdf_download_url=result.pdf_download_url,
                excel_download_url=result.excel_download_url,
                excel_path=result.excel_path,
                pdf_path=result.pdf_path,
            )

        return result

    def _write_combined_index(
        self,
        combined_path: Path,
        type_results: list[dict[str, Any]],
    ) -> None:
        with combined_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["type_name", "csv_path", "row_count", "status", "error"])
            for outcome in type_results:
                writer.writerow(
                    [
                        outcome.get("type_name", ""),
                        outcome.get("csv_path") or "",
                        outcome.get("row_count") or 0,
                        outcome.get("status", "failed"),
                        outcome.get("error") or "",
                    ]
                )

    async def _run_type_with_retry(
        self,
        page: "Page",
        session: "SessionManager",
        report: ReportDefinition,
        type_config: TypeConfig,
        extracted_dir: Path,
    ) -> dict[str, Any]:
        """Submit/sort/extract one Type; retry once with full reacquire on failure."""
        log_automation_event(
            logger,
            "report4_type_started",
            type_name=type_config.name,
        )
        last_error: str | None = None

        for attempt in range(1, TYPE_SUBMIT_MAX_ATTEMPTS + 1):
            try:
                if attempt > 1:
                    log_automation_event(
                        logger,
                        "report4_type_retry",
                        type_name=type_config.name,
                        attempt=attempt,
                    )
                    page = await self.ensure_mis_page(
                        page,
                        session,
                        f"{report.slug}_{type_config.name}_retry_{attempt}",
                    )
                    await self.navigation.navigate_to_report(page, report)
                    page = await self.ensure_mis_page(
                        page,
                        session,
                        f"{report.slug}_{type_config.name}_retry_nav",
                    )
                    try:
                        await page.wait_for_selector(
                            "#complaintTypeInput, #viewType",
                            timeout=15_000,
                        )
                    except Exception:
                        pass

                report_root = await self._submit_type_once(
                    page, session, report, type_config, attempt=attempt
                )
                await self._wait_for_received_header(page, type_config.name)
                await self._sort_received(report_root, page, report.slug, type_config.name)
                csv_path, row_count = await self._extract_type(
                    report_root, report, type_config, extracted_dir
                )
                log_automation_event(
                    logger,
                    "report4_type_completed",
                    type_name=type_config.name,
                    row_count=row_count,
                    csv_path=str(csv_path),
                    attempt=attempt,
                )
                return {
                    "type_name": type_config.name,
                    "csv_path": str(csv_path),
                    "row_count": row_count,
                    "status": "success",
                    "error": "",
                    "page": page,
                }
            except Exception as exc:
                last_error = str(exc)
                log_automation_event(
                    logger,
                    "report4_type_failed",
                    type_name=type_config.name,
                    attempt=attempt,
                    error=last_error,
                )
                await self._save_type_failure_artifacts(
                    page, type_config.name, attempt, last_error
                )
                await tracked_sleep(0.4 * attempt, reason="report4_type_retry")

        return {
            "type_name": type_config.name,
            "csv_path": "",
            "row_count": 0,
            "status": "failed",
            "error": last_error or "unknown",
            "page": page,
        }

    async def _submit_type_once(
        self,
        page: "Page",
        session: "SessionManager",
        report: ReportDefinition,
        type_config: TypeConfig,
        *,
        attempt: int,
    ) -> Any:
        """Apply full filters, submit, wait for genuine table refresh."""
        page = await self.ensure_mis_page(
            page, session, f"{report.slug}_{type_config.name}_before_submit"
        )
        report_root = await self.filter_service.get_report_root(page)
        filters = get_report4_filters_for_type(type_config.name)

        applied_values = await self.filter_service.apply_filters(
            report_root,
            filters,
            page=page,
        )
        await self.filter_service.validate_mandatory(
            report_root, filters, applied_values
        )
        self._assert_core_filters(applied_values, type_config)

        ctx = get_run_context()
        run_id = ctx.run_id if ctx is not None else ""
        await apply_previous_from_date(
            page,
            run_id,
            report.slug,
            type_config.name,
            filter_service=self.filter_service,
        )
        log_phase2_submit_clicked(
            run_id,
            report.slug,
            type_config.name,
        )

        old_fp = await table_fingerprint(report_root)
        log_automation_event(
            logger,
            "report4_type_submit",
            type_name=type_config.name,
            attempt=attempt,
            old_fingerprint=old_fp[:120] if old_fp else "",
        )

        await self.generator.generate_report(report_root, page)

        # generate_report may soft-succeed while the previous type's table is still
        # visible (Coach Cleanliness AJAX is often slow). Keep polling for a real
        # fingerprint change before extracting — do NOT trust the Type dropdown
        # alone (it is set before Submit).
        refreshed = await wait_for_table_refresh(
            report_root,
            page,
            old_fp,
            report_slug=report.slug,
            timeout_seconds=30.0,
        )
        new_fp = await table_fingerprint(report_root)
        if old_fp and (not refreshed) and new_fp == old_fp:
            raise ReportGenerationError(
                f"Report {report.slug} table did not refresh after generate"
            )

        if not await self._wait_for_report_displayed(report_root, page):
            raise ReportGenerationError(
                f"Report {report.slug} did not display after generate"
            )

        if not await self._verify_type_selected(report_root, type_config.portal_value):
            await tracked_sleep(0.5, reason="report4_type_verify_settle")
            if not await self._verify_type_selected(report_root, type_config.portal_value):
                raise ReportGenerationError(
                    f"Type mismatch after refresh: expected {type_config.portal_value}"
                )

        log_automation_event(
            logger,
            "report4_new_table_verified",
            type_name=type_config.name,
            attempt=attempt,
            refreshed=bool(refreshed or (new_fp != old_fp)),
        )
        return report_root

    async def _wait_for_report_displayed(
        self,
        report_root: Any,
        page: "Page",
        *,
        timeout_seconds: float = 12.0,
    ) -> bool:
        """Poll until the results table/grid is visible after submit redraw."""
        from app.automation.wait_utils import poll_until

        async def _visible() -> bool:
            return await self.generator.verify_report_displayed(report_root)

        return await poll_until(
            _visible,
            interval_seconds=0.15,
            timeout_seconds=timeout_seconds,
            reason="report4_display_poll",
        )

    @staticmethod
    def _assert_core_filters(applied_values: dict[str, str], type_config: TypeConfig) -> None:
        date_applied = applied_values.get("dateRange") or ""
        for name, value in applied_values.items():
            if "date" in name.lower() and "range" in name.lower():
                date_applied = value
                break
        if date_applied and "previous day" not in str(date_applied).lower():
            raise ReportGenerationError(
                f"Date Range must be Previous Day before Submit, got: {date_applied}"
            )

        view_applied = str(applied_values.get("view") or "")
        if view_applied and "train" not in view_applied.lower():
            raise ReportGenerationError(
                f"View must be Train No. Wise before Submit, got: {view_applied}"
            )

        type_applied = str(applied_values.get("type") or "")
        expected = type_config.portal_value.lower()
        if type_applied and expected not in type_applied.lower() and type_applied.lower() not in expected:
            # Portal may shorten labels; require a meaningful overlap on key tokens.
            tokens = [t for t in expected.replace("-", " ").split() if len(t) > 3]
            if tokens and not any(t in type_applied.lower() for t in tokens):
                raise ReportGenerationError(
                    f"Type not applied before Submit, got: {type_applied}, expected: {type_config.portal_value}"
                )

    async def _verify_type_selected(self, report_root: Any, portal_value: str) -> bool:
        try:
            selected = await report_root.locator("#complaintTypeInput").evaluate(
                "el => el.options[el.selectedIndex]?.text ?? el.value ?? ''"
            )
        except Exception:
            return False
        selected_text = str(selected or "").strip().lower()
        expected = portal_value.strip().lower()
        if not selected_text:
            return False
        if expected in selected_text or selected_text in expected:
            return True
        tokens = [t for t in expected.replace("-", " ").split() if len(t) > 3]
        return bool(tokens) and any(t in selected_text for t in tokens)

    async def _wait_for_received_header(self, page: "Page", type_name: str) -> None:
        try:
            await page.locator(
                "th:has-text('Received'), td:has-text('Received')"
            ).first.wait_for(state="visible", timeout=15_000)
        except Exception:
            log_automation_event(
                logger,
                "types_received_header_wait_timeout",
                type_name=type_name,
            )

    async def _sort_received(
        self,
        report_root: Any,
        page: "Page",
        report_slug: str,
        type_name: str,
    ) -> None:
        try:
            await self.click_received_twice(
                report_root, page, report_slug=report_slug
            )
        except ReceivedSortError as exc:
            raise ReportGenerationError(
                f"Received descending sort failed for {type_name}: {exc}"
            ) from exc

    async def _extract_type(
        self,
        report_root: Any,
        report: ReportDefinition,
        type_config: TypeConfig,
        extracted_dir: Path,
    ) -> tuple[Path, int]:
        from app.automation.table_extractor import ExtractionResult

        extractor = TableExtractor(output_dir=extracted_dir)
        # Extract data only — never append slug again (avoids types/types/).
        data = await extractor.extract_table_data(report_root)
        if not data:
            raise ReportGenerationError(
                f"Could not extract table data for {type_config.name}"
            )

        html = await extractor.extract_table_html(report_root)
        extraction_result = ExtractionResult(
            success=True,
            data=data,
            html=html,
            row_count=len(data),
            column_count=len(data[0]) if data else 0,
        )
        if await self.reject_empty_table(extraction_result):
            raise ReportGenerationError(
                f"Empty table for {type_config.name}"
            )

        csv_path = extracted_dir / f"report4_{type_slug(type_config.name)}_raw.csv"
        self._save_type_csv(data, csv_path)
        return csv_path, max(len(data) - 1, 0)

    async def _save_type_failure_artifacts(
        self,
        page: "Page",
        type_name: str,
        attempt: int,
        error: str,
    ) -> None:
        dest = ensure_directory(Path(config.screenshots_dir) / "report4_type_failures")
        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        slug = type_slug(type_name)
        meta = dest / f"failure_{stamp}_{slug}_attempt{attempt}.txt"
        meta.write_text(error, encoding="utf-8")
        try:
            html_path = dest / f"failure_{stamp}_{slug}_attempt{attempt}.html"
            html_path.write_text(await page.content(), encoding="utf-8")
        except Exception:
            pass
        try:
            shot = dest / f"failure_{stamp}_{slug}_attempt{attempt}.png"
            await page.screenshot(path=str(shot), full_page=True)
        except Exception:
            pass

    @staticmethod
    def _save_type_csv(data: list[list[str]], csv_path: Path) -> None:
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            for row in data:
                writer.writerow(row)
