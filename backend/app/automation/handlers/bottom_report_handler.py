"""Bottom Performed Trains Report handler orchestrator."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.automation.bottom_report_detail_extract import (
    extract_division_detail,
    rematch_division_from_scan,
    scan_division_summary_rows,
    scan_division_summary_table,
)
from app.automation.bottom_report_filters import (
    BOTTOM_COMPREHENSIVE_SECTIONS,
    BOTTOM_REPORT_LOG_PREFIX,
    BOTTOM_WATER_SECTION,
    get_comprehensive_section_config,
)
from app.automation.bottom_report_train_frequency import aggregate_division_trains
from app.automation.config import config
from app.automation.date_range import get_context_date_range
from app.automation.portal_from_date import apply_previous_from_date, log_phase1_submit_clicked
from app.automation.processing.bottom_report_models import (
    BOTTOM_REPORT_SLUG,
    MSG_NO_QUALIFYING_DIVISION,
    RESULT_JSON_FILENAME,
    BottomReportResult,
    DivisionResult,
    SectionResult,
    apply_train_inclusion_filter,
    resolve_no_train_message,
)
from app.automation.report14_filters import SOURCE_PREVIOUS
from app.automation.report14_navigation import Report14NavigationError, navigate_report14_via_menu
from app.automation.reports import ReportDefinition
from app.automation.run_context import get_run_context
from app.automation.schemas import ReportResult
from app.automation.utils import ensure_directory, log_automation_event, resolve_report_dir
from app.automation.page_wait import wait_for_portal_settle

from .base import BaseReportHandler
from .comprehensive1013_handler import Comprehensive1013Handler
from .report14_handler import Report14Handler

if TYPE_CHECKING:
    from playwright.async_api import Page

    from app.automation.session import SessionManager

logger = logging.getLogger(__name__)

COMPREHENSIVE_REPORT = ReportDefinition(
    name="Comprehensive (with drill down)",
    slug="comprehensive-10-13",
    page_path="/mis_reports/report1",
    screenshot_filename="comprehensive.png",
    url_fragment="mis_reports/report1",
)


def _log(message: str, **fields: Any) -> None:
    logger.info("%s %s", BOTTOM_REPORT_LOG_PREFIX, message)
    log_automation_event(logger, "bottom_report_" + message.lower().replace(" ", "_"), **fields)


class BottomReportHandler(BaseReportHandler):
    """Execute Bottom Performed Trains Report workflow."""

    def __init__(self) -> None:
        super().__init__()
        self._comp = Comprehensive1013Handler()
        self._water = Report14Handler()

    def bind_browser(self, browser: Any) -> None:
        super().bind_browser(browser)
        self._comp.bind_browser(browser)
        self._water.bind_browser(browser)

    async def execute(
        self,
        page: "Page",
        session: "SessionManager",
        report: ReportDefinition,
    ) -> ReportResult:
        started_at = datetime.now(UTC).isoformat()
        t0 = time.perf_counter()

        ctx = get_run_context()
        run_id = ctx.run_id if ctx is not None else str(uuid.uuid4())
        if ctx is not None:
            ctx.freeze_report_from_date(report.slug)

        date_range = get_context_date_range()
        date_from = date_range.iso_from()
        date_to = date_range.iso_to()
        extracted_dir = ensure_directory(
            resolve_report_dir(config.extracted_data_dir, report.slug) / run_id
        )

        page = await self.ensure_mis_page(page, session, f"{report.slug}_start", report=COMPREHENSIVE_REPORT)
        await self.navigation.navigate_to_report(page, COMPREHENSIVE_REPORT)
        page = await self.ensure_mis_page(page, session, f"{report.slug}_after_nav", report=COMPREHENSIVE_REPORT)

        section_results: dict[str, SectionResult] = {}
        failed_stages: list[str] = []

        # Generation order: Security → Punctuality → Electrical → Water
        for cfg in BOTTOM_COMPREHENSIVE_SECTIONS:
            page = await self.ensure_mis_page(
                page, session, f"{report.slug}_{cfg.section_id}", report=COMPREHENSIVE_REPORT
            )
            try:
                section_results[cfg.section_id] = await self._run_comprehensive_section(
                    page,
                    session,
                    section_id=cfg.section_id,
                    extracted_dir=extracted_dir,
                    run_id=run_id,
                )
            except Exception as exc:
                failed_stages.append(f"bottom.{cfg.section_id}")
                _log(f"Section failed: {cfg.section_id}", error=str(exc))
                section_results[cfg.section_id] = SectionResult(
                    section_id=cfg.section_id,
                    no_division_message=MSG_NO_QUALIFYING_DIVISION,
                )

        page = await self.ensure_mis_page(page, session, f"{report.slug}_water_nav")
        try:
            section_results["water_availability"] = await self._run_water_section(
                page,
                session,
                report=report,
                extracted_dir=extracted_dir,
                run_id=run_id,
            )
        except Exception as exc:
            failed_stages.append("bottom.water")
            _log("Water section failed", error=str(exc))
            section_results["water_availability"] = SectionResult(
                section_id="water_availability",
                no_division_message=MSG_NO_QUALIFYING_DIVISION,
            )

        result = BottomReportResult(
            report_slug=BOTTOM_REPORT_SLUG,
            date_from=date_from or "",
            date_to=date_to or "",
            sections=section_results,
        )
        result_path = extracted_dir / RESULT_JSON_FILENAME
        result.save(result_path)

        extraction_seconds = time.perf_counter() - t0
        _log("Result saved", path=str(result_path), sections=len(section_results))

        saved_defer: bool | None = None
        if ctx is not None:
            saved_defer = ctx.defer_processing
            ctx.defer_processing = False
        t_proc = time.perf_counter()
        try:
            finalize = await self.finalize_after_extract(
                slug=report.slug,
                csv_path=result_path,
                source_paths=[str(result_path)],
                row_counts={"result": 1},
                source_row_count=1,
                started_at=started_at,
                extraction_seconds=round(extraction_seconds, 3),
                ingest_source="bottom_report_json",
            )
        finally:
            if ctx is not None and saved_defer is not None:
                ctx.defer_processing = saved_defer

        processing_seconds = time.perf_counter() - t_proc
        finalize = finalize.model_copy(
            update={"processing_seconds": round(processing_seconds, 3)}
        )

        if failed_stages and finalize.status == "success":
            finalize = finalize.model_copy(
                update={
                    "status": "partial_success",
                    "error": f"Failed stages: {', '.join(failed_stages)}",
                }
            )
        return finalize

    async def _run_comprehensive_section(
        self,
        page: "Page",
        session: "SessionManager",
        *,
        section_id: str,
        extracted_dir: Path,
        run_id: str,
    ) -> SectionResult:
        section_config = get_comprehensive_section_config(section_id)
        if section_config is None:
            raise ValueError(f"Missing comprehensive config for {section_id}")

        _log(f"Starting comprehensive section", section=section_id)
        report_root = await self._comp._submit_section_once(
            page,
            session,
            COMPREHENSIVE_REPORT,
            section_config,
            attempt=1,
        )
        await self._comp._wait_for_received_header(page, section_config.section_id)
        await self._comp._sort_received(report_root, page, COMPREHENSIVE_REPORT.slug, section_config.section_id)

        payload, scan_err = await scan_division_summary_table(page, report_root)
        if scan_err and not (payload and payload.get("found")):
            raise RuntimeError(scan_err)

        # Every division with Received > 20 — never stop after the first/max row.
        qualifying = scan_division_summary_rows(payload)
        if not qualifying:
            return SectionResult(
                section_id=section_id,
                no_division_message=MSG_NO_QUALIFYING_DIVISION,
            )

        _log(
            "Qualifying divisions",
            section=section_id,
            count=len(qualifying),
            divisions=[f"{d.division_code}:{d.received}" for d in qualifying],
        )

        division_results: list[DivisionResult] = []
        for division in qualifying:
            # Fresh scan between drills so later divisions remain clickable.
            refresh_payload, _ = await scan_division_summary_table(page, report_root)
            current = rematch_division_from_scan(refresh_payload, division) or division

            div_dir = extracted_dir / section_id / current.division_code
            detail = await extract_division_detail(
                page,
                report_root,
                current,
                output_dir=div_dir,
                section_id=section_id,
            )
            if not detail.success:
                raise RuntimeError(detail.error or "division detail extraction failed")

            agg = aggregate_division_trains(
                detail.detail_rows or [],
                division_code=current.division_code,
            )
            div_result = DivisionResult(
                division_name=current.division_name,
                division_code=current.division_code,
                division_received=current.received,
                detail_row_count=detail.detail_row_count,
                qualifying_trains=apply_train_inclusion_filter(agg.trains),
                no_train_message=resolve_no_train_message(agg),
                valid_train_row_count=agg.valid_train_row_count,
                non_train_row_count=agg.non_train_row_count,
                grouped_train_total=agg.grouped_train_total,
            )
            division_results.append(div_result)
            await wait_for_portal_settle(
                report_root,
                page,
                reason="bottom_division_settle",
                report_slug="bottom-report",
            )

        return SectionResult(
            section_id=section_id,
            qualifying_divisions=division_results,
        )

    async def _run_water_section(
        self,
        page: "Page",
        session: "SessionManager",
        *,
        report: ReportDefinition,
        extracted_dir: Path,
        run_id: str,
    ) -> SectionResult:
        section_id = BOTTOM_WATER_SECTION.section_id
        _log("Starting water section", section=section_id)

        try:
            await navigate_report14_via_menu(page, run_id=run_id)
        except Report14NavigationError as exc:
            raise RuntimeError(f"bottom.water.navigation: {exc}") from exc

        page = await self.ensure_mis_page(page, session, f"{report.slug}_water_after_nav")

        outcome = await self._water._extract_source(
            page,
            session,
            report,
            cfg=SOURCE_PREVIOUS,
            extracted_dir=extracted_dir / "water_raw",
            run_id=run_id,
        )
        if outcome.get("status") != "success":
            raise RuntimeError(outcome.get("error") or "water summary extract failed")

        page = outcome.get("page", page)
        report_root = await self.filter_service.get_report_root(page)

        payload, scan_err = await scan_division_summary_table(page, report_root)
        if scan_err and not (payload and payload.get("found")):
            raise RuntimeError(scan_err)

        # Every water division with Received > 20 — process all, not only the first.
        qualifying = scan_division_summary_rows(payload)
        if not qualifying:
            return SectionResult(
                section_id=section_id,
                no_division_message=MSG_NO_QUALIFYING_DIVISION,
            )

        _log(
            "Qualifying water divisions",
            count=len(qualifying),
            divisions=[f"{d.division_code}:{d.received}" for d in qualifying],
        )

        division_results: list[DivisionResult] = []
        for division in qualifying:
            refresh_payload, _ = await scan_division_summary_table(page, report_root)
            current = rematch_division_from_scan(refresh_payload, division) or division

            div_dir = extracted_dir / section_id / current.division_code
            detail = await extract_division_detail(
                page,
                report_root,
                current,
                output_dir=div_dir,
                section_id=section_id,
            )
            if not detail.success:
                raise RuntimeError(detail.error or "water division detail failed")

            agg = aggregate_division_trains(
                detail.detail_rows or [],
                division_code=current.division_code,
            )
            division_results.append(
                DivisionResult(
                    division_name=current.division_name,
                    division_code=current.division_code,
                    division_received=current.received,
                    detail_row_count=detail.detail_row_count,
                    qualifying_trains=apply_train_inclusion_filter(agg.trains),
                    no_train_message=resolve_no_train_message(agg),
                    valid_train_row_count=agg.valid_train_row_count,
                    non_train_row_count=agg.non_train_row_count,
                    grouped_train_total=agg.grouped_train_total,
                )
            )
            await wait_for_portal_settle(
                report_root,
                page,
                reason="bottom_water_division_settle",
                report_slug=report.slug,
            )

        return SectionResult(
            section_id=section_id,
            qualifying_divisions=division_results,
        )
