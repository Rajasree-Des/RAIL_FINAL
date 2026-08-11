"""Report 18 Vande Bharat — TOTAL Received drill-down and detailed complaint extraction.

After the summary table loads, locate the final grand TOTAL row → Received hyperlink,
open List of Complaints, scrape all paginated HTML table rows, reconcile counts,
and convert to a canonical CSV for the processor.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.automation.config import config
from app.automation.report18_filters import (
    REPORT18_DETAIL_CSV_FILENAME,
    REPORT18_LOG_PREFIX,
)
from app.automation.scr_field_map import canonicalize_scr_row
from app.automation.utils import ensure_directory, log_automation_event
from app.automation.wait_utils import poll_until, tracked_sleep

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page

    from app.automation.filters import ReportRoot

logger = logging.getLogger(__name__)

REPORT18_SUMMARY_META_FILENAME = "vande_bharat_summary_meta.json"
MIN_GRAND_TOTAL_LABELS = 3

REF_HEADER_KEYS = ("Ref. No.", "Ref No", "Ref No.", "Reference No.", "complaintRefNo")

# Final report column order — matches VB RAILMADAD REPORT - SCR reference layout.
REPORT18_FINAL_HEADERS: list[str] = [
    "Sl No",
    "complaintRefNo",
    "createdOn",
    "modifiedOn",
    "trainStation",
    "channelType",
    "compTypeName",
    "ownZoneCode",
    "deptCode",
    "sla",
    "rating",
    "status",
    "feedbackRemarks",
    "restStation",
    "contactNo",
    "physicalCoachNo",
    "trainNameForReport",
    "complaintDesc",
    "remarks",
    "userid",
]

# SCR / portal canonical keys → final report header.
_CANONICAL_TO_FINAL: dict[str, str] = {
    "complaintRefNo": "complaintRefNo",
    "createdOn": "createdOn",
    "modifiedOn": "modifiedOn",
    "trainStation": "trainStation",
    "channelType": "channelType",
    "complaintTypeName": "compTypeName",
    "ownZoneCode": "ownZoneCode",
    "zoneCode": "ownZoneCode",
    "deptCode": "deptCode",
    "sla": "sla",
    "rating": "rating",
    "status": "status",
    "feedbackRemark": "feedbackRemarks",
    "nextStation": "restStation",
    "contactId": "contactNo",
    "physicalCoachNo": "physicalCoachNo",
    "trainNameForReport": "trainNameForReport",
    "complaintDesc": "complaintDesc",
    "remarks": "remarks",
    "userId": "userid",
}

_PORTAL_EXTRA_ALIASES: dict[str, str] = {
    "sla": "sla",
    "sl a": "sla",
    "breach": "sla",
    "channel type": "channelType",
    "comptypename": "complaintTypeName",
    "comp type name": "complaintTypeName",
    "ownzonecode": "ownZoneCode",
    "physical coach no.": "physicalCoachNo",
    "physical coach no": "physicalCoachNo",
    "disposal time": "diff",
    "feedback remark": "feedbackRemark",
    "feedback remarks": "feedbackRemark",
    "next station": "nextStation",
    "rest station": "nextStation",
    "contact id": "contactId",
    "contact no": "contactId",
    "contact no.": "contactId",
    "user id": "userId",
    "user id.": "userId",
}

# Legacy output header ids → current ids (saved column configs / older CSVs).
REPORT18_LEGACY_HEADER_ALIASES: dict[str, str] = {
    "feedbackRemark": "feedbackRemarks",
    "nextStation": "restStation",
    "contactId": "contactNo",
    "userId": "userid",
}


@dataclass
class Report18DetailExtractResult:
    success: bool
    summary_total: int | None = None
    detail_csv_path: Path | None = None
    detail_row_count: int = 0
    source_headers: list[str] | None = None
    error: str | None = None


def _log(message: str, **fields: Any) -> None:
    logger.info("%s %s", REPORT18_LOG_PREFIX, message)
    event = "report18_" + re.sub(r"[^a-z0-9]+", "_", message.lower()).strip("_")
    log_automation_event(logger, event, **fields)


def _detail_stage_error(stage: str, message: str) -> str:
    return f"vande_bharat_{stage}: {message}"


def _normalize_header(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _cell_is_total_label(text: str) -> bool:
    t = _normalize_header(text)
    return t == "total" or t == "total:" or t.startswith("total ")


def count_grand_total_labels(cells: list[str], received_idx: int) -> int:
    """Count TOTAL labels in non-Received cells (testable mirror of JS logic)."""
    count = 0
    for idx, cell in enumerate(cells):
        if idx == received_idx:
            continue
        if _cell_is_total_label(cell):
            count += 1
    return count


def is_grand_total_row(cells: list[str], received_idx: int, *, min_labels: int = MIN_GRAND_TOTAL_LABELS) -> bool:
    return count_grand_total_labels(cells, received_idx) >= min_labels


def _row_ref_no(row: dict[str, str]) -> str:
    for key in REF_HEADER_KEYS:
        value = str(row.get(key) or "").strip()
        if value:
            return value
    for key, value in row.items():
        if _normalize_header(key) in {"ref no", "ref. no.", "ref no.", "reference no"}:
            text = str(value or "").strip()
            if text:
                return text
    return ""


def dedupe_portal_rows_by_ref(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Remove duplicate rows by Ref. No., preserving first-seen order."""
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for row in rows:
        ref = _row_ref_no(row)
        if not ref:
            continue
        if ref in seen:
            continue
        seen.add(ref)
        unique.append(row)
    return unique


def reconcile_detail_counts(
    aggregate_total: int | None,
    unique_detail_count: int,
    *,
    modal_total: int | None = None,
) -> tuple[bool, str | None]:
    if aggregate_total is None:
        return True, None
    if aggregate_total == 0:
        return unique_detail_count == 0, None
    if unique_detail_count != aggregate_total:
        msg = (
            f"Vande Bharat detail reconciliation mismatch: "
            f"aggregate={aggregate_total}, details={unique_detail_count}"
        )
        if modal_total is not None and modal_total != unique_detail_count:
            msg += f", modal_entries={modal_total}"
        return False, msg
    if modal_total is not None and modal_total != aggregate_total:
        return False, (
            f"Vande Bharat detail reconciliation mismatch: "
            f"aggregate={aggregate_total}, modal_entries={modal_total}"
        )
    return True, None


def is_aggregate_table_ready(payload: dict[str, Any] | None, *, min_data_rows: int = 1) -> bool:
    """Return True when portal aggregate scan reports enough populated data rows."""
    if not isinstance(payload, dict):
        return False
    if not payload.get("ready"):
        return False
    try:
        count = int(payload.get("dataRowCount") or 0)
    except (TypeError, ValueError):
        count = 0
    return count >= min_data_rows


_WAIT_AGGREGATE_TABLE_JS = """() => {
  const norm = (t) => (t || '').replace(/\\s+/g, ' ').trim();
  const lower = (t) => norm(t).toLowerCase();
  const isReceivedHeader = (h) => {
    const t = lower(h);
    return t === 'received' || t === 'recieved';
  };

  const tables = Array.from(document.querySelectorAll('table'));
  for (const table of tables) {
    let headerRow = table.querySelector('thead tr');
    if (!headerRow) {
      const first = table.querySelector('tr');
      if (first && first.querySelectorAll('th').length > 0) headerRow = first;
    }
    if (!headerRow) continue;

    const headers = [...headerRow.querySelectorAll('th, td')].map((el) => norm(el.textContent));
    if (!headers.some(isReceivedHeader)) continue;

    const headerBlob = headers.map(lower).join('|');
    if (!headerBlob.includes('train') && !headerBlob.includes('complaint')) continue;

    let dataRows = [...table.querySelectorAll('tbody tr')];
    if (!dataRows.length) {
      dataRows = [...table.querySelectorAll('tr')].filter((tr) => tr !== headerRow);
    }

    const populated = dataRows.filter((tr) => {
      const cells = [...tr.querySelectorAll('td')].map((el) => norm(el.textContent));
      return cells.length >= 3 && cells.some((c) => c.length > 0);
    });

    if (populated.length >= 1) {
      return {
        ready: true,
        dataRowCount: populated.length,
        receivedHeader: headers.find(isReceivedHeader) || 'Received',
      };
    }
  }
  return { ready: false, dataRowCount: 0 };
}"""


async def capture_report18_screenshot(page: "Page", name: str) -> str | None:
    try:
        directory = ensure_directory(Path(config.debug_screenshots_dir) / "report18")
        path = directory / f"{name}.png"
        await page.screenshot(path=str(path), full_page=True)
        _log(f"Screenshot saved: {path.name}", path=str(path))
        return str(path)
    except Exception as exc:
        logger.warning("%s screenshot failed name=%s error=%s", REPORT18_LOG_PREFIX, name, exc)
        return None


_FIND_TOTAL_RECEIVED_JS = """() => {
  const MIN_GRAND_TOTAL_LABELS = 3;
  const norm = (t) => (t || '').replace(/\\s+/g, ' ').trim();
  const lower = (t) => norm(t).toLowerCase();

  const isReceivedHeader = (h) => {
    const t = lower(h);
    return t === 'received' || t === 'recieved';
  };

  const cellIsTotalLabel = (text) => {
    const t = lower(text);
    return t === 'total' || t === 'total:' || /^total\\b/.test(t);
  };

  document.querySelectorAll('[data-rail-vb-total-received]').forEach((el) => {
    el.removeAttribute('data-rail-vb-total-received');
  });
  document.querySelectorAll('[data-rail-vb-total-received-cell]').forEach((el) => {
    el.removeAttribute('data-rail-vb-total-received-cell');
  });

  const tables = Array.from(document.querySelectorAll('table'));
  const candidates = [];

  for (let tableIdx = 0; tableIdx < tables.length; tableIdx++) {
    const table = tables[tableIdx];
    let headerRow = table.querySelector('thead tr');
    if (!headerRow) {
      const first = table.querySelector('tr');
      if (first && first.querySelectorAll('th').length > 0) headerRow = first;
    }
    if (!headerRow) continue;

    const headerCells = Array.from(headerRow.querySelectorAll('th, td'));
    const headers = headerCells.map((el) => norm(el.textContent));
    if (!headers.length) continue;

    const receivedIdx = headers.findIndex((h) => isReceivedHeader(h));
    if (receivedIdx < 0) continue;

    const headerBlob = headers.map(lower).join('|');
    let tableScore = 1;
    if (headerBlob.includes('train')) tableScore += 2;
    if (headerBlob.includes('zone')) tableScore += 1;
    if (headerBlob.includes('complaint')) tableScore += 1;

    const bodyRows = Array.from(table.querySelectorAll('tbody tr, tfoot tr'));
    const dataRows = bodyRows.length
      ? bodyRows
      : Array.from(table.querySelectorAll('tr')).filter((tr) => tr !== headerRow);

    for (let r = 0; r < dataRows.length; r++) {
      const row = dataRows[r];
      const cells = Array.from(row.querySelectorAll('td'));
      if (!cells.length || receivedIdx >= cells.length) continue;

      let totalLabelCount = 0;
      for (let c = 0; c < cells.length; c++) {
        if (c === receivedIdx) continue;
        if (cellIsTotalLabel(cells[c].textContent)) totalLabelCount++;
      }
      if (totalLabelCount < MIN_GRAND_TOTAL_LABELS) continue;

      const targetCell = cells[receivedIdx];
      const link = targetCell.querySelector('a');
      const valueText = norm(link ? (link.textContent || '') : (targetCell.textContent || ''));
      const digits = (valueText.match(/\\d+/g) || []).join('');
      const value = digits ? parseInt(digits, 10) : 0;

      candidates.push({
        tableIdx,
        rowIndex: r,
        receivedIdx,
        totalLabelCount,
        value,
        valueText,
        hasLink: !!link,
        href: link ? (link.getAttribute('href') || '') : '',
        receivedHeader: headers[receivedIdx],
        tableScore,
        row,
        targetCell,
        link,
      });
    }
  }

  if (!candidates.length) {
    return { found: false, reason: 'grand TOTAL row not found (need >= 3 TOTAL labels)' };
  }

  candidates.sort((a, b) => {
    const scoreA = (a.tableScore || 0) * 1000 + (a.totalLabelCount || 0) * 10 + (a.rowIndex || 0);
    const scoreB = (b.tableScore || 0) * 1000 + (b.totalLabelCount || 0) * 10 + (b.rowIndex || 0);
    return scoreB - scoreA;
  });

  const best = candidates[0];

  if (best.value > 0 && !best.hasLink) {
    return {
      found: false,
      reason: 'grand TOTAL row Received cell has no hyperlink',
      value: best.value,
      totalLabelCount: best.totalLabelCount,
    };
  }

  if (best.hasLink) {
    best.targetCell.setAttribute('data-rail-vb-total-received-cell', '1');
    best.link.setAttribute('data-rail-vb-total-received', '1');
  }

  return {
    found: true,
    skipClick: best.value === 0 && !best.hasLink,
    value: best.value,
    valueText: best.valueText,
    href: best.href,
    tableIdx: best.tableIdx,
    rowIndex: best.rowIndex,
    receivedIdx: best.receivedIdx,
    totalLabelCount: best.totalLabelCount,
    receivedHeader: best.receivedHeader,
    hasLink: best.hasLink,
  };
}"""


async def _evaluate_in_root(page: "Page", report_root: "ReportRoot", script: str) -> Any:
    try:
        evaluate = getattr(report_root, "evaluate", None)
        if callable(evaluate):
            return await evaluate(script)
    except Exception:
        pass
    try:
        return await report_root.locator("body").first.evaluate(script)
    except Exception:
        return await page.evaluate(script)


async def wait_for_vande_bharat_aggregate_table(
    page: "Page",
    report_root: "ReportRoot",
    *,
    min_data_rows: int = 1,
    timeout_ms: int = 45_000,
) -> bool:
    """Wait until the Vande Bharat summary table has Received header + data rows."""
    timeout_seconds = max(timeout_ms / 1000.0, 1.0)

    async def _ready() -> bool:
        try:
            payload = await _evaluate_in_root(page, report_root, _WAIT_AGGREGATE_TABLE_JS)
        except Exception:
            return False
        return is_aggregate_table_ready(payload, min_data_rows=min_data_rows)

    ok = await poll_until(
        _ready,
        interval_seconds=0.15,
        timeout_seconds=timeout_seconds,
        reason="vande_bharat_aggregate_table",
    )
    if ok:
        _log("Aggregate summary table loaded")
    else:
        _log("Aggregate summary table wait timed out", timeout_ms=timeout_ms)
    return ok


async def _resolve_marked_total_received_link(
    page: "Page",
    report_root: "ReportRoot",
) -> "Locator | None":
    candidates = [
        report_root.locator(
            "td[data-rail-vb-total-received-cell='1'] a[data-rail-vb-total-received='1']"
        ),
        report_root.locator("a[data-rail-vb-total-received='1']"),
        page.locator(
            "td[data-rail-vb-total-received-cell='1'] a[data-rail-vb-total-received='1']"
        ),
        page.locator("a[data-rail-vb-total-received='1']"),
    ]
    for candidate in candidates:
        try:
            if await candidate.count() > 0:
                return candidate.first
        except Exception:
            continue
    return None


_GRAND_TOTAL_ROW_EVAL = """(receivedIdx) => {
  const norm = (t) => (t || '').replace(/\\s+/g, ' ').trim();
  const lower = (t) => norm(t).toLowerCase();
  const cellIsTotalLabel = (text) => {
    const t = lower(text);
    return t === 'total' || t === 'total:' || /^total\\b/.test(t);
  };
  const MIN = 3;
  const tables = Array.from(document.querySelectorAll('table'));
  let best = null;
  for (const table of tables) {
    let headerRow = table.querySelector('thead tr');
    if (!headerRow) {
      const first = table.querySelector('tr');
      if (first && first.querySelectorAll('th').length > 0) headerRow = first;
    }
    if (!headerRow) continue;
    const headers = [...headerRow.querySelectorAll('th, td')].map(el => norm(el.textContent));
    const rIdx = headers.findIndex(h => lower(h) === 'received' || lower(h) === 'recieved');
    if (rIdx < 0) continue;
    const useIdx = receivedIdx >= 0 ? receivedIdx : rIdx;
    const rows = [...table.querySelectorAll('tbody tr, tfoot tr')];
    for (let ri = 0; ri < rows.length; ri++) {
      const cells = [...rows[ri].querySelectorAll('td')];
      if (!cells.length || useIdx >= cells.length) continue;
      let count = 0;
      for (let c = 0; c < cells.length; c++) {
        if (c === useIdx) continue;
        if (cellIsTotalLabel(cells[c].textContent)) count++;
      }
      if (count < MIN) continue;
      const score = count * 1000 + ri;
      if (!best || score > best.score) {
        best = { rowIndex: ri, score, receivedIdx: useIdx, totalLabelCount: count };
      }
    }
  }
  return best;
}"""


async def _evaluate_grand_total_row(
    page: "Page",
    report_root: "ReportRoot",
    received_idx: int,
) -> dict[str, Any] | None:
    for root in (report_root, page):
        try:
            body = root.locator("body").first
            if await body.count() > 0:
                result = await body.evaluate(_GRAND_TOTAL_ROW_EVAL, received_idx)
                if isinstance(result, dict):
                    return result
        except Exception:
            pass
        try:
            evaluate = getattr(root, "evaluate", None)
            if callable(evaluate):
                result = await evaluate(f"({ _GRAND_TOTAL_ROW_EVAL })({received_idx})")
                if isinstance(result, dict):
                    return result
        except Exception:
            continue
    return None


async def _resolve_structural_total_received_link(
    page: "Page",
    report_root: "ReportRoot",
    *,
    received_idx: int | None,
) -> "Locator | None":
    if received_idx is None or received_idx < 0:
        return None

    idx = received_idx
    best = await _evaluate_grand_total_row(page, report_root, idx)
    if not isinstance(best, dict) or best.get("rowIndex") is None:
        return None

    roots: list[Any] = [report_root, page]
    for root in roots:
        try:
            tables = root.locator("table").filter(
                has=root.locator("th, td").filter(has_text=re.compile(r"^\s*Received\s*$", re.I))
            )
            table_count = await tables.count()
        except Exception:
            continue

        for t in range(table_count):
            table = tables.nth(t)
            try:
                row_index = int(best["rowIndex"])
                total_rows = table.locator("tbody tr, tfoot tr")
                if await total_rows.count() <= row_index:
                    total_rows = table.locator("tr")
                if await total_rows.count() <= row_index:
                    continue
                total_row = total_rows.nth(row_index)
                cell = total_row.locator("td").nth(idx)
                link = cell.locator("a")
                if await link.count() > 0:
                    return link.first
            except Exception:
                continue
    return None


async def find_total_received_hyperlink(
    page: "Page",
    report_root: "ReportRoot",
) -> tuple[Any | None, int | None, str | None, bool]:
    """Locate grand TOTAL row × Received hyperlink.

    Returns (locator, total_value, error, skip_click).
    """
    _log("Locating Vande Bharat summary table")
    try:
        payload = await _evaluate_in_root(page, report_root, _FIND_TOTAL_RECEIVED_JS)
    except Exception as exc:
        return None, None, _detail_stage_error("aggregate_table_missing", str(exc)), False

    if not isinstance(payload, dict):
        return None, None, _detail_stage_error("total_row_missing", "invalid summary scan result"), False

    if not payload.get("found"):
        reason = str(payload.get("reason") or "grand TOTAL row not found")
        value = payload.get("value")
        try:
            total_value = int(value) if value is not None else None
        except (TypeError, ValueError):
            total_value = None
        stage = "received_link_missing" if total_value and total_value > 0 else "total_row_missing"
        return None, total_value, _detail_stage_error(stage, reason), False

    _log("Located grand TOTAL row", total_label_count=payload.get("totalLabelCount"))
    _log(
        "Located Received column",
        received_header=payload.get("receivedHeader"),
        received_idx=payload.get("receivedIdx"),
    )
    _log("Target cell = grand TOTAL × Received")

    value = payload.get("value")
    try:
        total_value = int(value) if value is not None else 0
    except (TypeError, ValueError):
        total_value = 0

    skip_click = bool(payload.get("skipClick")) or total_value == 0
    value_text = str(payload.get("valueText") or total_value).strip()
    _log(f"Hyperlink value = {value_text}", total=total_value)

    if skip_click:
        return None, total_value, None, True

    locator = await _resolve_marked_total_received_link(page, report_root)
    if locator is None:
        received_idx = payload.get("receivedIdx")
        try:
            received_idx_int = int(received_idx) if received_idx is not None else None
        except (TypeError, ValueError):
            received_idx_int = None
        locator = await _resolve_structural_total_received_link(
            page,
            report_root,
            received_idx=received_idx_int,
        )

    if locator is None:
        return (
            None,
            total_value,
            _detail_stage_error("received_link_missing", "hyperlink locator could not be resolved"),
            False,
        )

    return locator, total_value, None, False


async def _wait_for_detail_view(page: "Page", *, timeout_ms: int = 30_000) -> tuple[bool, str | None]:
    import asyncio
    import time as time_mod

    deadline = time_mod.monotonic() + (timeout_ms / 1000.0)
    detail_markers = [
        page.locator(".modal.show, .modal.fade.show, #exampleModal.show"),
        page.get_by_text(re.compile(r"List of Complaints", re.I)),
        page.locator("table").filter(
            has=page.locator("th, td").filter(has_text=re.compile(r"^\s*Ref\.?\s*No\.?\s*$", re.I))
        ),
    ]

    opened = False
    last_error: str | None = None
    while time_mod.monotonic() < deadline:
        for marker in detail_markers:
            try:
                if await marker.count() > 0 and await marker.first.is_visible():
                    opened = True
                    break
            except Exception as exc:
                last_error = str(exc)
        if opened:
            break
        await asyncio.sleep(0.2)

    if not opened:
        return False, last_error or "List of Complaints view did not become visible"

    row_markers = [
        page.locator("#exampleModal.show table tbody tr td"),
        page.locator(".modal.show table tbody tr td"),
        page.locator("table").filter(
            has=page.locator("th, td").filter(has_text=re.compile(r"Ref\.?\s*No", re.I))
        ).locator("tbody tr td"),
    ]
    while time_mod.monotonic() < deadline:
        for marker in row_markers:
            try:
                if await marker.count() > 0 and await marker.first.is_visible():
                    return True, None
            except Exception as exc:
                last_error = str(exc)
        await asyncio.sleep(0.2)

    return False, last_error or "detailed complaint rows did not load"


async def click_total_received_and_wait_detail(
    page: "Page",
    link: "Locator",
    *,
    total_value: int | None,
) -> tuple[bool, str | None]:
    _log("Clicking TOTAL/Received hyperlink", total=total_value)
    try:
        await link.click(timeout=15_000)
    except Exception as exc:
        return False, _detail_stage_error("received_link_missing", f"click failed: {exc}")

    ok, wait_err = await _wait_for_detail_view(page, timeout_ms=30_000)
    if not ok:
        return False, _detail_stage_error("detail_modal_not_opened", wait_err or "modal did not open")

    _log("Detailed table loaded", total=total_value)
    return True, None


def _resolve_detail_modal(page: "Page") -> "Locator":
    return page.locator(
        "#exampleModal.show, .modal.show, [role='dialog']"
    ).filter(has=page.get_by_text(re.compile(r"List of Complaints", re.I))).first


async def _resolve_modal_table(page: "Page") -> "Locator":
    modal = _resolve_detail_modal(page)
    try:
        if await modal.count() > 0:
            table = modal.locator("table").first
            if await table.count() > 0:
                return table
    except Exception:
        pass
    return page.locator(
        "#exampleModal.show table, .modal.show table, [role='dialog'] table"
    ).first


async def _extract_modal_page_rows(
    page: "Page",
    modal_table: "Locator",
    headers: list[str],
) -> list[dict[str, str]]:
    try:
        handle = await modal_table.element_handle()
        if handle is None:
            return []
        payload = await page.evaluate(
            """(tableEl) => {
              if (!tableEl) return { headers: [], rows: [] };
              const norm = (t) => (t || '').replace(/\\s+/g, ' ').trim();
              const headerEls = tableEl.querySelectorAll('thead th, thead td');
              let headers = [...headerEls].map(el => norm(el.textContent)).filter(Boolean);
              if (!headers.length) {
                const first = tableEl.querySelector('tr');
                if (first) {
                  headers = [...first.querySelectorAll('th, td')]
                    .map(el => norm(el.textContent)).filter(Boolean);
                }
              }
              const rows = [];
              tableEl.querySelectorAll('tbody tr').forEach(tr => {
                const cells = [...tr.querySelectorAll('td')].map(el => norm(el.textContent));
                if (cells.length >= 3) rows.push(cells);
              });
              return { headers, rows };
            }""",
            handle,
        )
    except Exception:
        return []

    if not isinstance(payload, dict):
        return []

    js_headers = list(payload.get("headers") or [])
    effective_headers = js_headers if js_headers else headers
    page_rows: list[dict[str, str]] = []
    for cells in payload.get("rows") or []:
        if not isinstance(cells, list):
            continue
        row_data: dict[str, str] = {}
        for col_idx, value in enumerate(cells):
            header = (
                effective_headers[col_idx]
                if col_idx < len(effective_headers)
                else f"Col{col_idx}"
            )
            row_data[header] = str(value or "").strip()
        if row_data and _row_ref_no(row_data):
            page_rows.append(row_data)
    return page_rows


async def _read_modal_entry_total(page: "Page") -> int | None:
    try:
        text = await page.evaluate(
            """() => {
              const el = document.querySelector(
                '.modal.show .dataTables_info, #exampleModal .dataTables_info, ' +
                '.modal .dataTables_info, .dataTables_info'
              );
              return el ? (el.textContent || '') : '';
            }"""
        )
    except Exception:
        return None
    if not text:
        return None
    match = re.search(r"of\s+([\d,]+)\s+entries", str(text), flags=re.IGNORECASE)
    if not match:
        return None
    try:
        return int(match.group(1).replace(",", ""))
    except ValueError:
        return None


async def _get_first_ref_on_page(page: "Page", modal_table: "Locator") -> str:
    rows = await _extract_modal_page_rows(page, modal_table, [])
    if not rows:
        return ""
    return _row_ref_no(rows[0])


async def _wait_for_modal_page_change(page: "Page", prev_first_ref: str) -> bool:
    async def _changed() -> bool:
        table = await _resolve_modal_table(page)
        current = await _get_first_ref_on_page(page, table)
        return bool(current) and current != prev_first_ref

    return await poll_until(_changed, interval_seconds=0.08, timeout_seconds=5.0, reason="vb_modal_pagination")


async def _extract_all_modal_pages(page: "Page") -> tuple[list[dict[str, str]], list[str], int | None, str | None]:
    all_rows: list[dict[str, str]] = []
    seen_refs: set[str] = set()
    source_headers: list[str] = []
    seen_header_set: set[str] = set()
    modal_total = await _read_modal_entry_total(page)
    page_num = 0

    while True:
        modal_table = await _resolve_modal_table(page)
        try:
            await modal_table.wait_for(state="visible", timeout=5000)
        except Exception:
            if not all_rows:
                return [], source_headers, modal_total, _detail_stage_error(
                    "detail_table_missing", "complaint table not visible in modal"
                )
            break

        headers: list[str] = []
        try:
            handle = await modal_table.element_handle()
            if handle is not None:
                headers = await page.evaluate(
                    """(tableEl) => {
                      const norm = (t) => (t || '').replace(/\\s+/g, ' ').trim();
                      const els = tableEl.querySelectorAll('thead th, thead td');
                      return [...els].map(el => norm(el.textContent)).filter(Boolean);
                    }""",
                    handle,
                )
        except Exception:
            headers = []

        try:
            await page.wait_for_function(
                """() => {
                  const t = document.querySelector('#exampleModal.show table tbody, .modal.show table tbody');
                  return t && t.querySelectorAll('tr').length > 0;
                }""",
                timeout=10_000,
            )
        except Exception:
            pass

        page_rows = await _extract_modal_page_rows(page, modal_table, headers)
        if not page_rows:
            if page_num == 0:
                return [], source_headers, modal_total, _detail_stage_error(
                    "detail_table_missing", "no complaint rows on first modal page"
                )
            break

        page_num += 1
        for row in page_rows:
            for key in row:
                if key and key not in seen_header_set:
                    seen_header_set.add(key)
                    source_headers.append(key)
            ref = _row_ref_no(row)
            if ref and ref not in seen_refs:
                seen_refs.add(ref)
                all_rows.append(row)

        _log(
            f"Modal page {page_num} extracted",
            page=page_num,
            page_rows=len(page_rows),
            total_so_far=len(all_rows),
        )

        if modal_total is not None and len(all_rows) >= modal_total:
            break

        next_button = page.locator(
            ".modal.show .dataTables_paginate .next:not(.disabled), "
            "#exampleModal.show .dataTables_paginate .next:not(.disabled), "
            ".pagination .next:not(.disabled), "
            "button:has-text('Next'):not([disabled]), "
            "a:has-text('Next'):not(.disabled)"
        )
        if await next_button.count() == 0 or not await next_button.first.is_visible():
            break

        prev_ref = await _get_first_ref_on_page(page, modal_table)
        try:
            await next_button.first.click()
        except Exception as exc:
            return all_rows, source_headers, modal_total, _detail_stage_error(
                "pagination_failed", f"Next click failed: {exc}"
            )

        advanced = await _wait_for_modal_page_change(page, prev_ref)
        if not advanced:
            await tracked_sleep(0.15, reason="vb_modal_pagination_fallback")
            new_ref = await _get_first_ref_on_page(page, await _resolve_modal_table(page))
            if new_ref == prev_ref:
                break

    return all_rows, source_headers, modal_total, None


async def _close_detail_modal(page: "Page") -> None:
    close_buttons = page.locator(
        ".modal.show .close, .modal.show .btn-close, "
        "[role='dialog'] button[aria-label='Close'], "
        ".modal button:has-text('Close')"
    )
    if await close_buttons.count() > 0:
        try:
            await close_buttons.first.click()
            await page.wait_for_selector(".modal.show, #exampleModal.show", state="hidden", timeout=5000)
        except Exception:
            pass
    _log("Detail modal closed")


def _normalize_portal_key(header: str) -> str:
    return re.sub(r"\s+", " ", str(header or "").strip().lower())


def _enrich_portal_row(portal_row: dict[str, str]) -> dict[str, str]:
    enriched = dict(portal_row)
    for key, value in list(portal_row.items()):
        norm = _normalize_portal_key(key)
        extra = _PORTAL_EXTRA_ALIASES.get(norm)
        if extra and extra not in enriched:
            enriched[extra] = value
        if key in REPORT18_FINAL_HEADERS and key not in {"Sl No"}:
            enriched.setdefault(key, value)
    return enriched


def transform_detail_rows_to_final(
    portal_rows: list[dict[str, str]],
) -> tuple[list[str], list[list[str]], list[str]]:
    source_headers: list[str] = []
    seen_headers: set[str] = set()
    final_rows: list[list[str]] = []

    for idx, portal_row in enumerate(portal_rows, start=1):
        for key in portal_row:
            if key and key not in seen_headers:
                seen_headers.add(key)
                source_headers.append(key)

        enriched = _enrich_portal_row(portal_row)
        canonical = canonicalize_scr_row(enriched)

        for final_header in REPORT18_FINAL_HEADERS:
            if final_header == "Sl No":
                continue
            if final_header in enriched and not canonical.get(final_header):
                text = str(enriched.get(final_header) or "").strip()
                if text.lower() == "null":
                    text = ""
                if text:
                    canonical[final_header] = text

        for portal_key, value in enriched.items():
            norm = _normalize_portal_key(portal_key)
            extra = _PORTAL_EXTRA_ALIASES.get(norm)
            if not extra:
                continue
            text = str(value or "").strip()
            if text.lower() == "null":
                text = ""
            if text and not canonical.get(extra):
                canonical[extra] = text

        if not canonical.get("ownZoneCode") and canonical.get("zoneCode"):
            canonical["ownZoneCode"] = canonical["zoneCode"]

        out: dict[str, str] = {header: "" for header in REPORT18_FINAL_HEADERS}
        out["Sl No"] = str(idx)
        for canon_key, final_header in _CANONICAL_TO_FINAL.items():
            if final_header == "ownZoneCode" and canon_key == "zoneCode":
                if out.get("ownZoneCode"):
                    continue
            value = str(canonical.get(canon_key) or "").strip()
            if value.lower() == "null":
                value = ""
            if value and not out.get(final_header):
                out[final_header] = value

        for final_header in REPORT18_FINAL_HEADERS:
            if final_header == "Sl No":
                continue
            if out.get(final_header):
                continue
            value = str(canonical.get(final_header) or "").strip()
            if value.lower() == "null":
                value = ""
            if value:
                out[final_header] = value

        final_rows.append([out[h] for h in REPORT18_FINAL_HEADERS])

    return list(REPORT18_FINAL_HEADERS), final_rows, source_headers


def write_final_csv(csv_path: Path, headers: list[str], rows: list[list[str]]) -> None:
    import csv

    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


async def _save_empty_detail_csv(extracted_dir: Path, summary_total: int) -> Report18DetailExtractResult:
    final_headers = list(REPORT18_FINAL_HEADERS)
    csv_path = extracted_dir / REPORT18_DETAIL_CSV_FILENAME
    write_final_csv(csv_path, final_headers, [])
    _log("Zero aggregate Received — empty detail dataset saved", total=summary_total)
    return Report18DetailExtractResult(
        success=True,
        summary_total=summary_total,
        detail_csv_path=csv_path,
        detail_row_count=0,
        source_headers=[],
    )


async def _extract_and_reconcile(
    page: "Page",
    summary_total: int | None,
) -> tuple[list[dict[str, str]], list[str], int | None, str | None]:
    portal_rows, source_headers, modal_total, err = await _extract_all_modal_pages(page)
    if err:
        return portal_rows, source_headers, modal_total, err

    unique_rows = dedupe_portal_rows_by_ref(portal_rows)
    ok, reconcile_err = reconcile_detail_counts(summary_total, len(unique_rows), modal_total=modal_total)
    if ok:
        return unique_rows, source_headers, modal_total, None
    return unique_rows, source_headers, modal_total, _detail_stage_error(
        "detail_reconciliation_failed", reconcile_err or "count mismatch"
    )


async def extract_vande_bharat_detail(
    page: "Page",
    report_root: "ReportRoot",
    extracted_dir: Path,
) -> Report18DetailExtractResult:
    """Full drill-down: grand TOTAL Received → List of Complaints → paginated HTML → CSV."""
    extracted_dir = ensure_directory(extracted_dir)
    await capture_report18_screenshot(page, "01_summary_report")
    _log("Summary report loaded")

    link, summary_total, err, skip_click = await find_total_received_hyperlink(page, report_root)
    if err:
        return Report18DetailExtractResult(success=False, summary_total=summary_total, error=err)

    if skip_click or summary_total == 0:
        return await _save_empty_detail_csv(extracted_dir, summary_total or 0)

    if link is None:
        return Report18DetailExtractResult(
            success=False,
            summary_total=summary_total,
            error=_detail_stage_error("received_link_missing", "hyperlink not found for non-zero total"),
        )

    try:
        if not await link.is_visible():
            return Report18DetailExtractResult(
                success=False,
                summary_total=summary_total,
                error=_detail_stage_error("received_link_missing", "hyperlink is not visible"),
            )
    except Exception as exc:
        return Report18DetailExtractResult(
            success=False,
            summary_total=summary_total,
            error=_detail_stage_error("received_link_missing", str(exc)),
        )

    _log(f"Total complaints = {summary_total}", total=summary_total)
    _log("Opening detailed complaints", total=summary_total)

    ok, click_err = await click_total_received_and_wait_detail(page, link, total_value=summary_total)
    if not ok:
        await capture_report18_screenshot(page, "02_detail_open_failed")
        return Report18DetailExtractResult(success=False, summary_total=summary_total, error=click_err)

    await capture_report18_screenshot(page, "02_detailed_complaint_list")

    portal_rows, source_headers, modal_total, extract_err = await _extract_and_reconcile(
        page, summary_total
    )

    if extract_err:
        _log("Retrying pagination extraction after reconciliation mismatch")
        await _close_detail_modal(page)
        ok, click_err = await click_total_received_and_wait_detail(page, link, total_value=summary_total)
        if not ok:
            await capture_report18_screenshot(page, "03_detail_retry_open_failed")
            return Report18DetailExtractResult(success=False, summary_total=summary_total, error=click_err)
        portal_rows, source_headers, modal_total, extract_err = await _extract_and_reconcile(
            page, summary_total
        )

    if extract_err or not portal_rows:
        await capture_report18_screenshot(page, "03_detail_extract_failed")
        return Report18DetailExtractResult(
            success=False,
            summary_total=summary_total,
            source_headers=source_headers,
            error=extract_err or _detail_stage_error("detail_table_missing", "no rows extracted"),
        )

    _log(
        f"Source rows = {len(portal_rows)}",
        source_rows=len(portal_rows),
        modal_total=modal_total,
        headers=source_headers,
    )

    _log("Transforming data", source_rows=len(portal_rows))
    final_headers, final_rows, _ = transform_detail_rows_to_final(portal_rows)
    csv_path = extracted_dir / REPORT18_DETAIL_CSV_FILENAME
    write_final_csv(csv_path, final_headers, final_rows)
    _log(f"Final rows = {len(final_rows)}", final_rows=len(final_rows), csv_path=str(csv_path))

    try:
        import json

        meta_path = extracted_dir / REPORT18_SUMMARY_META_FILENAME
        meta_path.write_text(
            json.dumps(
                {
                    "summary_total": summary_total,
                    "unique_detail_count": len(portal_rows),
                    "modal_entry_total": modal_total,
                    "final_rows": len(final_rows),
                    "source_headers": source_headers,
                    "detail_csv_path": str(csv_path),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass

    await _close_detail_modal(page)
    await capture_report18_screenshot(page, "04_after_modal_close")

    return Report18DetailExtractResult(
        success=True,
        summary_total=summary_total,
        detail_csv_path=csv_path,
        detail_row_count=len(final_rows),
        source_headers=source_headers,
    )
