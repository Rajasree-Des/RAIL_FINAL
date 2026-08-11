"""Report 9 handler: Mode Wise Cause Wise — ALL + SCR Train/Station tables."""

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
from app.automation.portal_from_date import (
    apply_previous_from_date,
    log_phase1_submit_clicked,
)
from app.automation.report9_filters import (
    ALL_SOURCE_CONFIGS,
    REPORT9_TAB_LABEL,
    SECTION_ORDER,
    SOURCE_A_CONFIGS,
    SOURCE_B_CONFIGS,
    ZONE_ALL,
    ZONE_SCR,
    Report9SourceConfig,
    filters_for_zone,
)
from app.automation.reports import ReportDefinition
from app.automation.run_context import get_run_context
from app.automation.schemas import ReportResult
from app.automation.table_refresh import table_fingerprint
from app.automation.utils import (
    ensure_directory,
    log_automation_event,
    resolve_report_dir,
)
from app.automation.wait_utils import tracked_sleep

from .base import BaseReportHandler

if TYPE_CHECKING:
    from playwright.async_api import Page

    from app.automation.session import SessionManager

logger = logging.getLogger(__name__)

ZONE_SUBMIT_MAX_ATTEMPTS = 2

# Discover cause-wise tables by heading / #tabled1|#tabled2 (ignores pie charts).
_EXTRACT_CAUSE_TABLES_JS = """() => {
  const normalize = (s) => (s || '').replace(/\\s+/g, ' ').trim().toLowerCase();
  const results = [];
  const tables = Array.from(document.querySelectorAll('table'));

  const findHeading = (table) => {
    let el = table;
    for (let depth = 0; depth < 10 && el; depth++) {
      let prev = el.previousElementSibling;
      while (prev) {
        const raw = (prev.innerText || prev.textContent || '').trim();
        const lines = raw.split('\\n').map((l) => l.trim()).filter(Boolean);
        for (const line of lines) {
          if (
            line &&
            /(?:7\\.[12]\\)|train|station).{0,40}cause\\s*wise/i.test(line) &&
            line.length < 220
          ) {
            return line;
          }
        }
        prev = prev.previousElementSibling;
      }
      const parent = el.parentElement;
      if (parent) {
        const kids = Array.from(parent.children || []);
        for (const kid of kids) {
          if (kid === el || kid.contains(table)) break;
          const t = (kid.innerText || '').trim().split('\\n')[0] || '';
          if (/(?:7\\.[12]\\)|train|station).{0,40}cause\\s*wise/i.test(t) && t.length < 220) {
            return t.trim();
          }
        }
      }
      el = el.parentElement;
    }
    // Fallback: look for 7.1 / 7.2 labels in ancestors' text nodes near table ids.
    const wrap = table.closest('#tabled1, #tabled2, .table-responsive') || table;
    const row = wrap.closest('.row') || wrap.parentElement;
    if (row) {
      const text = (row.innerText || '').split('\\n').map((l) => l.trim()).find((l) =>
        /(?:7\\.[12]\\)|train|station).{0,40}cause\\s*wise/i.test(l)
      );
      if (text) return text;
    }
    return '';
  };

  const tableContainerId = (table) => {
    const wrap = table.closest('[id^=\"tabled\"]');
    return wrap ? wrap.id : (table.id || '');
  };

  for (const table of tables) {
    try {
      const style = window.getComputedStyle(table);
      if (style && (style.display === 'none' || style.visibility === 'hidden')) continue;
    } catch (e) {}

    const headerRow =
      table.querySelector('thead tr') ||
      table.querySelector('tr');
    if (!headerRow) continue;
    const headerCells = headerRow.querySelectorAll('th, td');
    if (!headerCells.length) continue;
    const headers = Array.from(headerCells).map((c) =>
      (c.innerText || c.textContent || '').replace(/\\s+/g, ' ').trim()
    );
    const headersNorm = headers.map(normalize);
    const hasCause = headersNorm.some((h) => h === 'cause' || h.includes('cause'));
    const hasReceived = headersNorm.some((h) => h === 'received' || h.includes('received'));
    // Portal Mode Wise tables are Cause|Received only (ignore pie/other grids).
    if (!hasCause || !hasReceived) continue;
    if (headersNorm.length > 4) continue;

    const rows = [];
    const trs = table.querySelectorAll('tr');
    for (const tr of trs) {
      const cells = tr.querySelectorAll('th, td');
      if (!cells.length) continue;
      rows.push(
        Array.from(cells).map((c) =>
          (c.innerText || c.textContent || '').replace(/\\s+/g, ' ').trim()
        )
      );
    }
    if (rows.length < 2) continue;
    results.push({
      heading: findHeading(table),
      tableId: tableContainerId(table),
      headers,
      rows,
    });
  }
  return results;
}"""


class Report9Handler(BaseReportHandler):
    """Execute Report 9 dual-zone Train/Station Cause Wise workflow."""

    async def execute(
        self,
        page: "Page",
        session: "SessionManager",
        report: ReportDefinition,
    ) -> ReportResult:
        started_at = datetime.now(UTC).isoformat()
        t0 = time.perf_counter()
        page = await self.ensure_mis_page(page, session, f"{report.slug}_start", report=report)

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
        section_results: list[dict[str, Any]] = []
        failed_sources: list[str] = []

        await self.navigation.navigate_to_report(page, report)
        page = await self.ensure_mis_page(page, session, f"{report.slug}_after_nav", report=report)
        try:
            await page.wait_for_selector("#complaintZoneInput", timeout=15_000)
        except Exception:
            pass

        zone_passes = (
            (ZONE_ALL, SOURCE_A_CONFIGS),
            (ZONE_SCR, SOURCE_B_CONFIGS),
        )

        for zone, configs in zone_passes:
            page = await self.ensure_mis_page(
                page, session, f"{report.slug}_zone_{zone}", report=report
            )
            zone_outcome = await self._run_zone_pass(
                page,
                session,
                report,
                zone=zone,
                configs=configs,
                extracted_dir=extracted_dir,
            )
            page = zone_outcome.get("page", page)
            for outcome in zone_outcome.get("sections", []):
                section_results.append(outcome)
                if outcome.get("status") == "success" and outcome.get("csv_path"):
                    source_paths.append(str(outcome["csv_path"]))
                    rows = int(outcome.get("row_count") or 0)
                    row_counts[outcome["source_id"]] = rows
                    total_rows += rows
                else:
                    failed_sources.append(str(outcome.get("source_id") or "unknown"))

        if failed_sources or len(source_paths) < len(ALL_SOURCE_CONFIGS):
            missing_errors = [
                o.get("error") or o.get("missing_error") or "REPORT9_TABLE_MISSING"
                for o in section_results
                if o.get("status") != "success"
            ]
            error_code = missing_errors[0] if missing_errors else "REPORT9_TABLE_MISSING"
            return self.build_failed_result(
                report.slug,
                error_code,
                source_paths=source_paths,
                row_counts=row_counts,
            )

        combined_path = extracted_dir / "report9_combined_index.csv"
        self._write_combined_index(combined_path, section_results)
        log_automation_event(
            logger,
            "report9_index_saved",
            path=str(combined_path),
            success_count=len(source_paths),
            run_id=run_id,
            tab=REPORT9_TAB_LABEL,
        )

        extraction_seconds = time.perf_counter() - t0
        log_automation_event(
            logger,
            "report_extraction_completed",
            slug=report.slug,
            section_count=len(source_paths),
            total_rows=total_rows,
            duration_seconds=round(extraction_seconds, 3),
        )

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

        if not result.ingestion_success:
            return self.build_failed_result(
                report.slug,
                "REPORT9_INGESTION_FAILED",
                source_paths=source_paths,
                row_counts=row_counts,
                source_csv_path=str(combined_path),
                source_row_count=total_rows,
            )

        if not result.processing_success:
            err = (result.error or "").upper()
            if "PDF" in err:
                code = "REPORT9_PDF_FAILED"
            elif "XLSX" in err or "EXCEL" in err:
                code = "REPORT9_XLSX_FAILED"
            else:
                code = result.error or "REPORT9_XLSX_FAILED"
            return self.build_failed_result(
                report.slug,
                code,
                source_paths=source_paths,
                row_counts=row_counts,
                ingestion_success=True,
                source_csv_path=str(combined_path),
                source_row_count=total_rows,
            )

        log_automation_event(
            logger,
            "ingestion:report9",
            path=str(combined_path),
            ingestion_success=result.ingestion_success,
        )
        log_automation_event(
            logger,
            "processing:report9",
            excel_path=result.excel_path,
            pdf_path=result.pdf_path,
            processing_success=result.processing_success,
            duration_seconds=round(processing_seconds, 3),
        )
        if ctx is not None:
            ctx.timing.spans["processing:report9"] = round(processing_seconds, 3)
            ctx.timing.record_report_span("report9", "processing", processing_seconds)

        return result

    def _write_combined_index(
        self,
        combined_path: Path,
        section_results: list[dict[str, Any]],
    ) -> None:
        with combined_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "source_id",
                    "section_title",
                    "zone",
                    "csv_path",
                    "row_count",
                    "status",
                    "error",
                    "heading",
                ]
            )
            # Stable section order for the processor.
            by_id = {r.get("source_id"): r for r in section_results}
            for cfg in SECTION_ORDER:
                outcome = by_id.get(cfg.source_id) or {
                    "source_id": cfg.source_id,
                    "section_title": cfg.section_title,
                    "zone": cfg.zone,
                    "csv_path": "",
                    "row_count": 0,
                    "status": "failed",
                    "error": cfg.missing_error,
                    "heading": "",
                }
                writer.writerow(
                    [
                        outcome.get("source_id", cfg.source_id),
                        outcome.get("section_title", cfg.section_title),
                        outcome.get("zone", cfg.zone),
                        outcome.get("csv_path") or "",
                        outcome.get("row_count") or 0,
                        outcome.get("status", "failed"),
                        outcome.get("error") or "",
                        outcome.get("heading") or "",
                    ]
                )

    async def _run_zone_pass(
        self,
        page: "Page",
        session: "SessionManager",
        report: ReportDefinition,
        *,
        zone: str,
        configs: tuple[Report9SourceConfig, ...],
        extracted_dir: Path,
    ) -> dict[str, Any]:
        last_error: str | None = None
        for attempt in range(1, ZONE_SUBMIT_MAX_ATTEMPTS + 1):
            try:
                if attempt > 1:
                    page = await self.ensure_mis_page(
                        page,
                        session,
                        f"{report.slug}_{zone}_retry_{attempt}",
                        report=report,
                    )
                    await self.navigation.navigate_to_report(page, report)
                    page = await self.ensure_mis_page(
                        page,
                        session,
                        f"{report.slug}_{zone}_retry_nav",
                        report=report,
                    )
                    try:
                        await page.wait_for_selector("#complaintZoneInput", timeout=15_000)
                    except Exception:
                        pass

                report_root = await self._submit_zone_once(
                    page, session, report, zone=zone, attempt=attempt
                )
                # Portal Mode Wise tables are not reliably DataTables-sortable;
                # Received descending sort is applied in Report9Processor.
                log_automation_event(
                    logger,
                    "report9_portal_sort_deferred_to_processor",
                    zone=zone,
                )

                tables = await self._discover_cause_tables(page)
                sections: list[dict[str, Any]] = []
                for cfg in configs:
                    matched = self._match_table(tables, cfg, zone=zone)
                    if matched is None:
                        sections.append(
                            {
                                "source_id": cfg.source_id,
                                "section_title": cfg.section_title,
                                "zone": zone,
                                "csv_path": "",
                                "row_count": 0,
                                "status": "failed",
                                "error": cfg.missing_error,
                                "missing_error": cfg.missing_error,
                                "heading": "",
                            }
                        )
                        continue

                    csv_path = extracted_dir / cfg.filename
                    self._save_csv(matched["rows"], csv_path)
                    data_rows = max(len(matched["rows"]) - 1, 0)
                    log_automation_event(
                        logger,
                        "report9_source_extracted",
                        source_id=cfg.source_id,
                        zone=zone,
                        heading=matched.get("heading"),
                        row_count=data_rows,
                        csv_path=str(csv_path),
                        tab=REPORT9_TAB_LABEL,
                        date_from=self._ctx_date_from(),
                        date_to=self._ctx_date_to(),
                    )
                    sections.append(
                        {
                            "source_id": cfg.source_id,
                            "section_title": cfg.section_title,
                            "zone": zone,
                            "csv_path": str(csv_path),
                            "row_count": data_rows,
                            "status": "success",
                            "error": "",
                            "heading": matched.get("heading") or "",
                        }
                    )

                if any(s.get("status") != "success" for s in sections):
                    missing = [
                        s.get("error") for s in sections if s.get("status") != "success"
                    ]
                    raise ReportGenerationError(
                        missing[0] if missing else "REPORT9_TABLE_MISSING"
                    )

                return {"page": page, "sections": sections}
            except Exception as exc:
                last_error = str(exc)
                log_automation_event(
                    logger,
                    "report9_zone_pass_failed",
                    zone=zone,
                    attempt=attempt,
                    error=last_error,
                )
                await tracked_sleep(0.4 * attempt, reason="report9_zone_retry")

        # Exhausted retries — return failed section stubs.
        err = last_error or "REPORT9_TABLE_REFRESH_FAILED"
        if "REFRESH" in err.upper() or "did not refresh" in err.lower():
            err = "REPORT9_TABLE_REFRESH_FAILED"
        sections = [
            {
                "source_id": cfg.source_id,
                "section_title": cfg.section_title,
                "zone": zone,
                "csv_path": "",
                "row_count": 0,
                "status": "failed",
                "error": cfg.missing_error if "MISSING" not in err else err,
                "missing_error": cfg.missing_error,
                "heading": "",
            }
            for cfg in configs
        ]
        # Prefer refresh code when refresh failed.
        if err == "REPORT9_TABLE_REFRESH_FAILED":
            for s in sections:
                s["error"] = err
        return {"page": page, "sections": sections}

    async def _submit_zone_once(
        self,
        page: "Page",
        session: "SessionManager",
        report: ReportDefinition,
        *,
        zone: str,
        attempt: int,
    ) -> Any:
        page = await self.ensure_mis_page(
            page, session, f"{report.slug}_{zone}_before_submit", report=report
        )
        report_root = await self.filter_service.get_report_root(page)
        filters = filters_for_zone(zone)
        applied_values = await self.filter_service.apply_filters(
            report_root,
            filters,
            page=page,
        )
        await self.filter_service.validate_mandatory(
            report_root, filters, applied_values
        )

        actual_zone = await self._read_zone(report_root)
        if not self._zone_matches(actual_zone, zone):
            # Fallback JS set + re-read
            await self._set_zone_js(report_root, zone)
            actual_zone = await self._read_zone(report_root)
        if not self._zone_matches(actual_zone, zone):
            raise ReportGenerationError(
                f"Zone mismatch before Submit: expected={zone!r} actual={actual_zone!r}"
            )

        ctx = get_run_context()
        run_id = ctx.run_id if ctx is not None else ""
        await apply_previous_from_date(
            page,
            run_id,
            report.slug,
            zone,
            filter_service=self.filter_service,
        )
        log_phase1_submit_clicked(run_id, report.slug, zone)

        old_fp = await table_fingerprint(report_root)
        log_automation_event(
            logger,
            "report9_zone_submit",
            zone=zone,
            expected_zone=zone,
            actual_zone=actual_zone,
            attempt=attempt,
            tab=REPORT9_TAB_LABEL,
            date_from=self._ctx_date_from(),
            date_to=self._ctx_date_to(),
            old_fingerprint=old_fp[:120] if old_fp else "",
        )

        await self.generator.generate_report(report_root, page)

        new_fp = await table_fingerprint(report_root)
        if old_fp and new_fp == old_fp:
            # Idempotent re-submit (same Zone/dates) may not change fingerprint.
            if not await self.generator.verify_report_displayed(report_root):
                raise ReportGenerationError("REPORT9_TABLE_REFRESH_FAILED")
            log_automation_event(
                logger,
                "report9_refresh_unchanged_accepted",
                zone=zone,
                fingerprint=new_fp[:120] if new_fp else "",
            )
        elif not await self.generator.verify_report_displayed(report_root):
            raise ReportGenerationError("REPORT9_TABLE_REFRESH_FAILED")

        actual_after = await self._read_zone(report_root)
        if not self._zone_matches(actual_after, zone):
            raise ReportGenerationError(
                f"Zone mismatch after refresh: expected={zone!r} actual={actual_after!r}"
            )

        log_automation_event(
            logger,
            "report9_zone_verified",
            zone=zone,
            actual_zone=actual_after,
            attempt=attempt,
        )
        return report_root

    async def _discover_cause_tables(self, page: "Page") -> list[dict[str, Any]]:
        try:
            raw = await page.evaluate(_EXTRACT_CAUSE_TABLES_JS)
        except Exception as exc:
            log_automation_event(
                logger,
                "report9_table_discover_failed",
                error=str(exc),
            )
            return []
        if not isinstance(raw, list):
            return []
        tables: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            rows = item.get("rows") or []
            if not rows:
                continue
            tables.append(
                {
                    "heading": str(item.get("heading") or ""),
                    "headers": list(item.get("headers") or []),
                    "rows": [list(r) for r in rows],
                }
            )
        log_automation_event(
            logger,
            "report9_tables_discovered",
            count=len(tables),
            headings=[t.get("heading") for t in tables],
        )
        return tables

    def _match_table(
        self,
        tables: list[dict[str, Any]],
        cfg: Report9SourceConfig,
        *,
        zone: str,
    ) -> dict[str, Any] | None:
        want_station = "station" in cfg.source_id
        scored: list[tuple[int, dict[str, Any]]] = []
        for table in tables:
            heading = str(table.get("heading") or "").lower()
            table_id = str(table.get("tableId") or "").lower()
            headers = [str(h).lower() for h in (table.get("headers") or [])]
            header_blob = " ".join(headers)
            if "cause" not in header_blob or "received" not in header_blob:
                continue

            score = 0
            if table_id in {tid.lower() for tid in cfg.table_ids}:
                score += 20

            for phrase in cfg.heading_match:
                if phrase in heading:
                    score += 10 + min(len(phrase), 40)

            has_station = "station" in heading
            has_train = "train" in heading and "station" not in heading
            # 7.1 train / 7.2 station markers
            if "7.1" in heading:
                has_train = True
                has_station = False
            if "7.2" in heading:
                has_station = True
                has_train = False

            if want_station and (has_station or table_id == "tabled2"):
                score += 8
            elif not want_station and (has_train or table_id == "tabled1"):
                score += 8
            elif want_station and has_train:
                score -= 6
            elif not want_station and has_station:
                score -= 6

            if score > 0:
                scored.append((score, table))

        if not scored:
            # Positional fallback when headings missing: first=train, second=station.
            cause_tables = [
                t
                for t in tables
                if "cause" in " ".join(str(h).lower() for h in (t.get("headers") or []))
                and "received" in " ".join(str(h).lower() for h in (t.get("headers") or []))
            ]
            if len(cause_tables) >= 2:
                return cause_tables[1] if want_station else cause_tables[0]
            if len(cause_tables) == 1 and not want_station:
                return cause_tables[0]
            return None

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    @staticmethod
    def _save_csv(data: list[list[str]], csv_path: Path) -> None:
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            for row in data:
                writer.writerow(row)

    async def _read_zone(self, report_root: Any) -> str:
        try:
            return str(
                await report_root.locator("#complaintZoneInput").evaluate(
                    "el => el.options[el.selectedIndex]?.text ?? el.value ?? ''"
                )
                or ""
            ).strip()
        except Exception:
            return ""

    async def _set_zone_js(self, report_root: Any, zone: str) -> None:
        await report_root.evaluate(
            """(zone) => {
              const el = document.querySelector('#complaintZoneInput');
              if (!el || el.tagName !== 'SELECT') return false;
              const target = (zone || '').toLowerCase().trim();
              for (let i = 0; i < el.options.length; i++) {
                const text = (el.options[i].text || '').trim();
                if (text.toLowerCase() === target) {
                  el.selectedIndex = i;
                  el.dispatchEvent(new Event('change', { bubbles: true }));
                  return true;
                }
              }
              for (let i = 0; i < el.options.length; i++) {
                const text = (el.options[i].text || '').trim();
                if (text.toLowerCase().includes(target)) {
                  el.selectedIndex = i;
                  el.dispatchEvent(new Event('change', { bubbles: true }));
                  return true;
                }
              }
              return false;
            }""",
            zone,
        )
        await tracked_sleep(0.05, reason="report9_zone_settle")

    @staticmethod
    def _zone_matches(actual: str, expected: str) -> bool:
        a = (actual or "").strip().lower()
        e = (expected or "").strip().lower()
        if not a or not e:
            return False
        if a == e:
            return True
        if e == "all" and a in {"all", "all zones"}:
            return True
        return e in a or a in e

    @staticmethod
    def _ctx_date_from() -> str | None:
        ctx = get_run_context()
        if ctx is None or ctx.date_range is None:
            return None
        return ctx.date_range.iso_from()

    @staticmethod
    def _ctx_date_to() -> str | None:
        ctx = get_run_context()
        if ctx is None or ctx.date_range is None:
            return None
        return ctx.date_range.iso_to()
