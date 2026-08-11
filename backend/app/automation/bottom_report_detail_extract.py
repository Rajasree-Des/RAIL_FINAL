"""Per-division Received drill-down and paginated modal extraction for Bottom Report."""

from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.automation.bottom_report_divisions import (
    division_code_from_name,
    is_total_division_row,
    parse_received_count,
)
from app.automation.processing.bottom_report_models import (
    DIVISION_RECEIVED_THRESHOLD,
    division_meets_received_threshold,
)
from app.automation.report18_detail_extract import (
    _close_detail_modal,
    _evaluate_in_root,
    _extract_all_modal_pages,
    click_total_received_and_wait_detail,
    dedupe_portal_rows_by_ref,
    is_grand_total_row,
    reconcile_detail_counts,
)
from app.automation.utils import ensure_directory, log_automation_event

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page

    from app.automation.filters import ReportRoot

logger = logging.getLogger(__name__)

LOG_PREFIX = "[BottomReportDetail]"


@dataclass
class DivisionSummaryRow:
    division_name: str
    division_code: str
    received: int
    row_index: int
    received_idx: int
    table_idx: int
    has_link: bool


@dataclass
class DivisionDetailExtractResult:
    success: bool
    division_name: str = ""
    division_code: str = ""
    division_received: int = 0
    detail_rows: list[dict[str, str]] | None = None
    detail_csv_path: Path | None = None
    detail_row_count: int = 0
    error: str | None = None


def _log(message: str, **fields: Any) -> None:
    logger.info("%s %s", LOG_PREFIX, message)
    event = "bottom_report_" + re.sub(r"[^a-z0-9]+", "_", message.lower()).strip("_")
    log_automation_event(logger, event, **fields)


def _stage_error(stage: str, message: str) -> str:
    return f"bottom_{stage}: {message}"


_FIND_DIVISION_ROWS_JS = """() => {
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

  const divisionHeaderMatch = (h) => {
    const t = lower(h);
    return t.includes('div') || t === 'organisation' || t === 'organization';
  };

  document.querySelectorAll('[data-rail-bottom-div-received]').forEach((el) => {
    el.removeAttribute('data-rail-bottom-div-received');
  });

  const tables = Array.from(document.querySelectorAll('table'));
  for (let tableIdx = 0; tableIdx < tables.length; tableIdx++) {
    const table = tables[tableIdx];
    let headerRow = table.querySelector('thead tr');
    if (!headerRow) {
      const first = table.querySelector('tr');
      if (first && first.querySelectorAll('th').length > 0) headerRow = first;
    }
    if (!headerRow) continue;

    const headers = [...headerRow.querySelectorAll('th, td')].map((el) => norm(el.textContent));
    if (!headers.length) continue;

    const receivedIdx = headers.findIndex((h) => isReceivedHeader(h));
    if (receivedIdx < 0) continue;

    let divisionIdx = headers.findIndex((h) => divisionHeaderMatch(h));
    if (divisionIdx < 0) {
      for (let i = 0; i < headers.length; i++) {
        if (i !== receivedIdx && lower(headers[i]).includes('division')) {
          divisionIdx = i;
          break;
        }
      }
    }

    const bodyRows = Array.from(table.querySelectorAll('tbody tr, tfoot tr'));
    const dataRows = bodyRows.length
      ? bodyRows
      : Array.from(table.querySelectorAll('tr')).filter((tr) => tr !== headerRow);

    const divisions = [];
    for (let r = 0; r < dataRows.length; r++) {
      const row = dataRows[r];
      const cells = Array.from(row.querySelectorAll('td'));
      if (!cells.length || receivedIdx >= cells.length) continue;

      let totalLabelCount = 0;
      for (let c = 0; c < cells.length; c++) {
        if (c === receivedIdx) continue;
        if (cellIsTotalLabel(cells[c].textContent)) totalLabelCount++;
      }
      if (totalLabelCount >= MIN_GRAND_TOTAL_LABELS) continue;

      const divisionName = divisionIdx >= 0 && divisionIdx < cells.length
        ? norm(cells[divisionIdx].textContent)
        : norm(cells[0]?.textContent || '');

      if (!divisionName || cellIsTotalLabel(divisionName)) continue;
      if (lower(divisionName) === 'total' || lower(divisionName).startsWith('total ')) continue;

      const targetCell = cells[receivedIdx];
      const link = targetCell.querySelector('a');
      const valueText = norm(link ? (link.textContent || '') : (targetCell.textContent || ''));
      const digits = (valueText.match(/\\d+/g) || []).join('');
      const received = digits ? parseInt(digits, 10) : 0;

      const marker = `div-${tableIdx}-${r}`;
      if (link) {
        link.setAttribute('data-rail-bottom-div-received', marker);
      } else if (received > 0) {
        targetCell.setAttribute('data-rail-bottom-div-received', marker);
      }

      divisions.push({
        divisionName,
        received,
        rowIndex: r,
        receivedIdx,
        tableIdx,
        hasLink: !!link,
        marker,
        valueText,
      });
    }

    if (divisions.length) {
      return {
        found: true,
        tableIdx,
        receivedIdx,
        divisionIdx,
        receivedHeader: headers[receivedIdx],
        divisions,
      };
    }
  }
  return { found: false, reason: 'division summary table not found' };
}"""


def _division_row_from_scan_item(item: dict[str, Any]) -> DivisionSummaryRow | None:
    name = str(item.get("divisionName") or "").strip()
    if not name or is_total_division_row(name):
        return None
    received = int(item.get("received") or 0)
    if not item.get("hasLink") and received > 0:
        return None
    return DivisionSummaryRow(
        division_name=name,
        division_code=division_code_from_name(name),
        received=received,
        row_index=int(item.get("rowIndex") or 0),
        received_idx=int(item.get("receivedIdx") or 0),
        table_idx=int(item.get("tableIdx") or 0),
        has_link=bool(item.get("hasLink")),
    )


def scan_division_summary_rows(
    payload: dict[str, Any] | None,
    *,
    threshold: int = DIVISION_RECEIVED_THRESHOLD,
) -> list[DivisionSummaryRow]:
    """Parse JS scan result into ALL division rows meeting Received > threshold.

    Never truncates to the first/max division — every qualifying row is returned
    so the handler can drill SC, then HYB, then any later division that qualifies.
    """
    if not isinstance(payload, dict) or not payload.get("found"):
        return []

    rows: list[DivisionSummaryRow] = []
    for item in payload.get("divisions") or []:
        if not isinstance(item, dict):
            continue
        row = _division_row_from_scan_item(item)
        if row is None:
            continue
        # Strictly more than threshold (Received == 20 must not drill).
        if not division_meets_received_threshold(row.received, threshold=threshold):
            continue
        rows.append(row)
    return rows


def rematch_division_from_scan(
    payload: dict[str, Any] | None,
    target: DivisionSummaryRow,
) -> DivisionSummaryRow | None:
    """Re-locate a known division after modal close (fresh markers / row indices)."""
    if not isinstance(payload, dict) or not payload.get("found"):
        return None
    target_code = (target.division_code or "").strip().upper()
    target_name = (target.division_name or "").strip().lower()
    for item in payload.get("divisions") or []:
        if not isinstance(item, dict):
            continue
        row = _division_row_from_scan_item(item)
        if row is None:
            continue
        if target_code and row.division_code == target_code:
            return row
        if target_name and row.division_name.strip().lower() == target_name:
            return row
    return None


async def scan_division_summary_table(
    page: "Page",
    report_root: "ReportRoot",
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = await _evaluate_in_root(page, report_root, _FIND_DIVISION_ROWS_JS)
    except Exception as exc:
        return None, _stage_error("table_load", str(exc))
    if not isinstance(payload, dict):
        return None, _stage_error("table_load", "invalid summary scan result")
    if not payload.get("found"):
        reason = str(payload.get("reason") or "summary table not found")
        return payload, _stage_error("table_load", reason)
    return payload, None


async def _resolve_division_received_link(
    page: "Page",
    report_root: "ReportRoot",
    division: DivisionSummaryRow,
) -> "Locator | None":
    marker = f"div-{division.table_idx}-{division.row_index}"
    selectors = [
        f"a[data-rail-bottom-div-received='{marker}']",
        f"td[data-rail-bottom-div-received='{marker}'] a",
    ]
    for selector in selectors:
        for root in (report_root, page):
            try:
                loc = root.locator(selector)
                if await loc.count() > 0:
                    return loc.first
            except Exception:
                continue

    for root in (report_root, page):
        try:
            tables = root.locator("table").filter(
                has=root.locator("th, td").filter(has_text=re.compile(r"^\s*Received\s*$", re.I))
            )
            for t in range(await tables.count()):
                table = tables.nth(t)
                rows = table.locator("tbody tr, tfoot tr")
                if await rows.count() <= division.row_index:
                    rows = table.locator("tr")
                if await rows.count() <= division.row_index:
                    continue
                row = rows.nth(division.row_index)
                row_text = (await row.inner_text()).lower()
                if division.division_name.lower()[:8] not in row_text:
                    continue
                cell = row.locator("td").nth(division.received_idx)
                link = cell.locator("a")
                if await link.count() > 0:
                    return link.first
        except Exception:
            continue
    return None


async def _extract_and_reconcile_division(
    page: "Page",
    expected_received: int,
) -> tuple[list[dict[str, str]], str | None]:
    portal_rows, _, modal_total, err = await _extract_all_modal_pages(page)
    if err:
        return portal_rows, err
    unique_rows = dedupe_portal_rows_by_ref(portal_rows)
    ok, reconcile_err = reconcile_detail_counts(
        expected_received,
        len(unique_rows),
        modal_total=modal_total,
    )
    if ok:
        return unique_rows, None
    return unique_rows, _stage_error(
        "detail_pagination",
        reconcile_err or "detail reconciliation mismatch",
    )


def write_detail_csv(csv_path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            handle.write("")
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key and key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


async def extract_division_detail(
    page: "Page",
    report_root: "ReportRoot",
    division: DivisionSummaryRow,
    *,
    output_dir: Path,
    section_id: str,
) -> DivisionDetailExtractResult:
    """Click one division's Received link, paginate modal, save detail CSV.

    Callers must iterate *all* qualifying divisions; this helper handles a single
    division only and always closes the modal so the next division can be drilled.
    """
    output_dir = ensure_directory(output_dir)
    csv_path = output_dir / "details.csv"

    # Re-mark the summary table so markers/row indices stay valid after prior drills.
    payload, _ = await scan_division_summary_table(page, report_root)
    division = rematch_division_from_scan(payload, division) or division

    link = await _resolve_division_received_link(page, report_root, division)
    if link is None:
        return DivisionDetailExtractResult(
            success=False,
            division_name=division.division_name,
            division_code=division.division_code,
            division_received=division.received,
            error=_stage_error(
                "division_drilldown",
                f"Received link not found for {division.division_name}",
            ),
        )

    _log(
        "Clicking division Received",
        section=section_id,
        division=division.division_code,
        received=division.received,
    )

    ok, click_err = await click_total_received_and_wait_detail(
        page, link, total_value=division.received
    )
    if not ok:
        return DivisionDetailExtractResult(
            success=False,
            division_name=division.division_name,
            division_code=division.division_code,
            division_received=division.received,
            error=click_err or _stage_error("division_drilldown", "modal did not open"),
        )

    detail_rows, extract_err = await _extract_and_reconcile_division(page, division.received)
    if extract_err:
        _log("Retrying division detail extraction after mismatch", division=division.division_code)
        await _close_detail_modal(page)
        link = await _resolve_division_received_link(page, report_root, division)
        if link is not None:
            ok, click_err = await click_total_received_and_wait_detail(
                page, link, total_value=division.received
            )
            if ok:
                detail_rows, extract_err = await _extract_and_reconcile_division(
                    page, division.received
                )
        if extract_err:
            await _close_detail_modal(page)
            return DivisionDetailExtractResult(
                success=False,
                division_name=division.division_name,
                division_code=division.division_code,
                division_received=division.received,
                error=extract_err,
            )

    write_detail_csv(csv_path, detail_rows)
    await _close_detail_modal(page)
    _log(
        "Division detail extracted",
        section=section_id,
        division=division.division_code,
        rows=len(detail_rows),
    )
    return DivisionDetailExtractResult(
        success=True,
        division_name=division.division_name,
        division_code=division.division_code,
        division_received=division.received,
        detail_rows=detail_rows,
        detail_csv_path=csv_path,
        detail_row_count=len(detail_rows),
    )


def parse_summary_table_from_csv(
    headers: list[str],
    rows: list[list[str]],
    *,
    threshold: int = DIVISION_RECEIVED_THRESHOLD,
) -> list[DivisionSummaryRow]:
    """Offline/test helper: find qualifying divisions from extracted summary CSV."""
    norm_headers = [re.sub(r"\s+", " ", h.strip()).lower() for h in headers]
    received_idx = next(
        (i for i, h in enumerate(norm_headers) if h in {"received", "recieved"}),
        -1,
    )
    division_idx = next(
        (i for i, h in enumerate(norm_headers) if "div" in h or h == "organisation"),
        0 if received_idx != 0 else 1,
    )
    if received_idx < 0:
        return []

    qualifying: list[DivisionSummaryRow] = []
    for row_idx, cells in enumerate(rows):
        if received_idx >= len(cells):
            continue
        div_name = cells[division_idx].strip() if division_idx < len(cells) else ""
        if is_total_division_row(div_name):
            continue
        cell_texts = [c.strip() for c in cells]
        if is_grand_total_row(cell_texts, received_idx):
            continue
        received = parse_received_count(cells[received_idx])
        # Strictly more than threshold (Received == 20 must not drill).
        if not division_meets_received_threshold(received, threshold=threshold):
            continue
        qualifying.append(
            DivisionSummaryRow(
                division_name=div_name,
                division_code=division_code_from_name(div_name),
                received=received,
                row_index=row_idx,
                received_idx=received_idx,
                table_idx=0,
                has_link=True,
            )
        )
    return qualifying
