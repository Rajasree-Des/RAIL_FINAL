"""Report 3 / train-no handler: Train No. Wise Top 20."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from app.automation.config import config
from app.automation.report3_filters import REPORT_3_FILTERS
from app.automation.reports import ReportDefinition
from app.automation.run_context import get_run_context
from app.automation.schemas import ReportResult
from app.automation.table_extractor import TableExtractor
from app.automation.utils import log_automation_event
from app.automation.workflow import extract_with_retry

from .base import BaseReportHandler

if TYPE_CHECKING:
    from playwright.async_api import Page

    from app.automation.session import SessionManager

logger = logging.getLogger(__name__)


class Report3Handler(BaseReportHandler):
    """Execute Train No. Wise Top 20 workflow (canonical key: train-no)."""

    async def execute(
        self,
        page: "Page",
        session: "SessionManager",
        report: ReportDefinition,
    ) -> ReportResult:
        started_at = datetime.now(UTC).isoformat()
        t0 = time.perf_counter()
        ctx = get_run_context()
        if ctx is not None:
            ctx.freeze_report_from_date(report.slug)
        page = await self.ensure_mis_page(page, session, f"{report.slug}_start", report=report)
        await self.navigation.navigate_to_report(page, report)
        page = await self.ensure_mis_page(page, session, f"{report.slug}_after_nav", report=report)
        try:
            await page.wait_for_selector("#viewType, select", timeout=15000)
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            log_automation_event(
                logger,
                "report3_initial_wait_timeout",
                slug=report.slug,
            )

        report_root, _, row_count = await self.apply_filters_and_submit(
            page,
            report,
            filters=REPORT_3_FILTERS,
            session=session,
            source_name="train_no_wise",
        )
        await self.click_received_twice(report_root, page, report_slug=report.slug)

        extractor = TableExtractor(output_dir=Path(config.extracted_data_dir))
        extraction_result, _, _ = await extract_with_retry(
            page,
            extractor,
            report_root,
            report,
            self.navigation,
            self.filter_service,
            self.discovery_service,
            self.generator,
            session,
            max_retries=2,
        )

        if await self.reject_empty_table(extraction_result) or not extraction_result.csv_path:
            return self.build_failed_result(
                report.slug,
                extraction_result.error or "Extraction failed or empty table",
            )

        if extraction_result.data and len(extraction_result.data) > 21:
            top_data = extraction_result.data[:21]
            csv_path = await extractor.save_as_csv(
                top_data,
                report_slug=report.slug,
            )
            if csv_path:
                extraction_result.csv_path = csv_path
                extraction_result.data = top_data
                extraction_result.row_count = len(top_data)

        await self.archive_pdf(page, report_root, report.slug, session=session)

        extraction_seconds = time.perf_counter() - t0
        log_automation_event(
            logger,
            "report_extraction_completed",
            slug=report.slug,
            row_count=extraction_result.row_count,
            duration_seconds=round(extraction_seconds, 3),
        )
        return await self.finalize_after_extract(
            slug=report.slug,
            csv_path=Path(extraction_result.csv_path),
            source_paths=[str(extraction_result.csv_path)],
            row_counts={"extracted": extraction_result.row_count},
            source_row_count=extraction_result.row_count,
            started_at=started_at,
            extraction_seconds=round(extraction_seconds, 3),
        )
