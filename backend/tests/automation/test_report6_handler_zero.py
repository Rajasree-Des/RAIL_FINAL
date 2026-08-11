"""Tests for Report 6 scr-station zero / not-found Unsatisfactory handling."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.automation.handlers.report6_handler import (
    SCR_STATION_UNSATISFACTORY_NOT_FOUND,
    Report6Handler,
    _TargetStatus,
)
from app.automation.processing.report6_processor import Report6Processor
from app.automation.reports import REPORT_6_SCR_STATION


ZONE_HEADERS = [
    "S.No.",
    "Organisation",
    "Feedback Received",
    "% Feedback",
    "Excellent",
    "Satisfactory",
    "Unsatisfactory",
    "% Unsatisfactory",
]


def test_zone_wise_requires_full_header_set():
    assert Report6Handler._is_zone_wise_table(ZONE_HEADERS) is True


def test_report6_scr_filters_use_sc_zone_and_station_mode():
    from app.automation.report6_scr_filters import REPORT_6_SCR_FILTERS

    by_name = {f.name: f for f in REPORT_6_SCR_FILTERS}
    assert by_name["zone"].value == "SC"
    assert by_name["mode"].value == "Station"


def test_wrong_table_skipped():
    dept_headers = ["S.No.", "Organisation", "Department", "Received"]
    assert Report6Handler._is_zone_wise_table(dept_headers) is False
    partial = ["Organisation", "Feedback Received", "Unsatisfactory"]
    assert Report6Handler._is_zone_wise_table(partial) is False


def test_exact_unsatisfactory_column_not_percent():
    idx = Report6Handler._exact_column_index(ZONE_HEADERS, "Unsatisfactory")
    assert idx == 6
    assert Report6Handler._exact_column_index(ZONE_HEADERS, "% Unsatisfactory") == 7
    # Must not return % column when looking for Unsatisfactory
    assert idx != Report6Handler._exact_column_index(ZONE_HEADERS, "% Unsatisfactory")


@pytest.mark.asyncio
async def test_extract_count_zero_no_modal():
    handler = Report6Handler()
    page = AsyncMock()
    report_root = MagicMock()
    table = MagicMock()

    with (
        patch.object(handler, "_find_zone_wise_table", AsyncMock(return_value=table)),
        patch.object(
            handler,
            "_get_station_unsatisfactory_target",
            AsyncMock(return_value=(_TargetStatus.FOUND, 0, 3)),
        ),
        patch.object(handler, "_click_unsatisfactory_row_exact", AsyncMock()) as click,
    ):
        count, complaints, error = await handler._extract_scr_complaints(
            page, report_root, "scr-station"
        )

    assert error is None
    assert count == 0
    assert complaints == []
    click.assert_not_called()


@pytest.mark.asyncio
async def test_extract_blank_count_treated_as_zero_when_cell_found():
    handler = Report6Handler()
    # blank digits already parsed to 0 inside target helper — FOUND + 0
    with (
        patch.object(handler, "_find_zone_wise_table", AsyncMock(return_value=MagicMock())),
        patch.object(
            handler,
            "_get_station_unsatisfactory_target",
            AsyncMock(return_value=(_TargetStatus.FOUND, 0, 2)),
        ),
        patch.object(handler, "_click_unsatisfactory_row_exact", AsyncMock()) as click,
    ):
        count, complaints, error = await handler._extract_scr_complaints(
            AsyncMock(), MagicMock(), "scr-station"
        )
    assert error is None
    assert count == 0
    assert complaints == []
    click.assert_not_called()


@pytest.mark.asyncio
async def test_extract_count_positive_opens_modal():
    handler = Report6Handler()
    modal_rows = [
        {"Ref. No.": "R1", "Mode": "Station"},
        {"Ref. No.": "R2", "Mode": "Station"},
    ]
    with (
        patch.object(handler, "_find_zone_wise_table", AsyncMock(return_value=MagicMock())),
        patch.object(
            handler,
            "_get_station_unsatisfactory_target",
            AsyncMock(return_value=(_TargetStatus.FOUND, 2, 5)),
        ),
        patch.object(handler, "_click_unsatisfactory_row_exact", AsyncMock(return_value=True)),
        patch.object(handler, "_read_modal_portal_total", AsyncMock(return_value=2)),
        patch.object(handler, "_extract_modal_pages", AsyncMock(return_value=modal_rows)),
        patch.object(handler, "_close_modal", AsyncMock()),
    ):
        count, complaints, error = await handler._extract_scr_complaints(
            AsyncMock(), MagicMock(), "scr-station"
        )
    assert error is None
    assert count == 2
    assert len(complaints) == 2


@pytest.mark.asyncio
async def test_extract_not_found_returns_clear_code():
    handler = Report6Handler()
    with patch.object(handler, "_find_zone_wise_table", AsyncMock(return_value=None)):
        count, complaints, error = await handler._extract_scr_complaints(
            AsyncMock(), MagicMock(), "scr-station"
        )
    assert count == 0
    assert complaints == []
    assert error == SCR_STATION_UNSATISFACTORY_NOT_FOUND


@pytest.mark.asyncio
async def test_execute_retries_once_then_fails_not_found(tmp_path: Path, monkeypatch):
    handler = Report6Handler()
    page = AsyncMock()
    page.url = "https://example/rmmis/admin/home.jsp?page=/mis_reports/report6"
    session = AsyncMock()
    report_root = MagicMock()

    extract = AsyncMock(
        side_effect=[
            (0, [], SCR_STATION_UNSATISFACTORY_NOT_FOUND),
            (0, [], SCR_STATION_UNSATISFACTORY_NOT_FOUND),
        ]
    )
    save_art = AsyncMock()

    with (
        patch.object(handler, "ensure_mis_page", AsyncMock(return_value=page)),
        patch.object(handler, "_apply_station_filters", AsyncMock(return_value=report_root)),
        patch.object(handler, "click_received_twice", AsyncMock()),
        patch.object(handler, "_extract_scr_complaints", extract),
        patch.object(handler, "_save_not_found_artifacts", save_art),
        patch.object(
            handler,
            "build_failed_result",
            side_effect=lambda slug, err, **kw: MagicMock(slug=slug, status="failed", error=err),
        ),
    ):
        result = await handler.execute(page, session, REPORT_6_SCR_STATION)

    assert result.status == "failed"
    assert result.error == SCR_STATION_UNSATISFACTORY_NOT_FOUND
    assert extract.await_count == 2
    save_art.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_zero_count_success_empty_csv(tmp_path: Path, monkeypatch):
    handler = Report6Handler()
    page = AsyncMock()
    page.url = "https://example/rmmis/admin/home.jsp?page=/mis_reports/report6"
    session = AsyncMock()
    report_root = MagicMock()
    csv_path = tmp_path / "scr-station_complaints_raw.csv"

    monkeypatch.setattr(
        "app.automation.handlers.report5_handler.config.extracted_data_dir",
        str(tmp_path / "extracted"),
    )

    finalize = AsyncMock(
        return_value=MagicMock(
            slug="scr-station",
            status="success",
            row_count=0,
            source_row_count=0,
            excel_path=str(tmp_path / "out.xlsx"),
            pdf_path=str(tmp_path / "out.pdf"),
        )
    )

    with (
        patch.object(handler, "ensure_mis_page", AsyncMock(return_value=page)),
        patch.object(handler, "_apply_station_filters", AsyncMock(return_value=report_root)),
        patch.object(handler, "click_received_twice", AsyncMock()),
        patch.object(
            handler,
            "_extract_scr_complaints",
            AsyncMock(return_value=(0, [], None)),
        ),
        patch.object(handler, "archive_pdf", AsyncMock()),
        patch.object(handler, "finalize_after_extract", finalize),
    ):
        result = await handler.execute(page, session, REPORT_6_SCR_STATION)

    assert result.status == "success"
    finalize.assert_awaited()
    call_kwargs = finalize.await_args.kwargs
    assert call_kwargs["source_row_count"] == 0
    assert Path(call_kwargs["csv_path"]).exists()
    assert Path(call_kwargs["csv_path"]).read_text(encoding="utf-8").startswith("complaintRefNo,")


class _FakeText:
    def __init__(self, text: str) -> None:
        self._text = text

    async def inner_text(self) -> str:
        return self._text


class _FakeCells:
    def __init__(self, texts: list[str]) -> None:
        self._texts = texts

    def nth(self, idx: int) -> _FakeText:
        return _FakeText(self._texts[idx])

    async def count(self) -> int:
        return len(self._texts)


class _FakeRow:
    def __init__(self, texts: list[str]) -> None:
        self._texts = texts

    def locator(self, sel: str) -> _FakeCells:
        return _FakeCells(self._texts)


class _FakeRows:
    def __init__(self, rows: list[list[str]]) -> None:
        self._rows = rows

    def nth(self, idx: int) -> _FakeRow:
        return _FakeRow(self._rows[idx])

    async def count(self) -> int:
        return len(self._rows)


class _FakeTable:
    def __init__(self, headers: list[str], body_rows: list[list[str]]) -> None:
        self._headers = headers
        self._body_rows = body_rows

    def locator(self, sel: str):
        if sel == "tbody tr, tfoot tr":
            return _FakeRows(self._body_rows)
        if sel == "tr":
            return _FakeRows([self._headers] + self._body_rows)
        if sel.startswith("thead"):
            return _FakeEmpty()
        return _FakeEmpty()


class _FakeEmpty:
    def first(self):
        return self

    def locator(self, *_a, **_k):
        return self

    def nth(self, *_a, **_k):
        return self

    async def count(self) -> int:
        return 0

    async def inner_text(self) -> str:
        return ""


@pytest.mark.asyncio
async def test_get_target_blank_unsatisfactory_is_zero():
    handler = Report6Handler()
    # columns match ZONE_HEADERS indices 1=Org, 6=Unsatisfactory
    body = [
        ["1", "Secunderabad", "10", "50", "5", "5", "", "0"],
        ["", "Total", "10", "50", "5", "5", "", "0"],  # blank Unsatisfactory
    ]
    table = _FakeTable(ZONE_HEADERS, body)

    async def fake_headers(_table):
        return ZONE_HEADERS

    with patch.object(handler, "_extract_table_headers", side_effect=fake_headers):
        status, count, row_idx = await handler._get_station_unsatisfactory_target(table)

    assert status == _TargetStatus.FOUND
    assert count == 0
    assert row_idx == 1


class _FakeRowWithCellTags:
    """Simulates tbody (td) vs tfoot Total (th) row layouts."""

    def __init__(
        self,
        *,
        td_texts: list[str] | None = None,
        th_texts: list[str] | None = None,
    ) -> None:
        self._td = td_texts or []
        self._th = th_texts if th_texts is not None else list(self._td)

    def locator(self, sel: str) -> _FakeCells:
        if sel == "td":
            return _FakeCells(self._td)
        if "th" in sel:
            return _FakeCells(self._th)
        return _FakeCells([])


class _FakeRowsWithCellTags:
    def __init__(self, rows: list[_FakeRowWithCellTags]) -> None:
        self._rows = rows

    def nth(self, idx: int) -> _FakeRowWithCellTags:
        return self._rows[idx]

    async def count(self) -> int:
        return len(self._rows)


class _FakeTableTfootTh:
    def __init__(self, headers: list[str], body_rows: list[_FakeRowWithCellTags]) -> None:
        self._headers = headers
        self._body_rows = body_rows

    def locator(self, sel: str):
        if sel == "tbody tr, tfoot tr":
            return _FakeRowsWithCellTags(self._body_rows)
        if sel == "tr":
            return _FakeRows([r._td or r._th for r in self._body_rows])
        if sel.startswith("thead"):
            return _FakeEmpty()
        return _FakeEmpty()


@pytest.mark.asyncio
async def test_get_target_prefers_scr_over_total_when_both_present():
    handler = Report6Handler()
    body = [
        ["1", "South Central Railway", "10", "50", "5", "5", "6", "30"],
        ["", "Total", "179", "100%", "66", "42", "113", "39.66"],
    ]
    table = _FakeTable(ZONE_HEADERS, body)

    async def fake_headers(_table):
        return ZONE_HEADERS

    with patch.object(handler, "_extract_table_headers", side_effect=fake_headers):
        status, count, row_idx = await handler._get_station_unsatisfactory_target(table)

    assert status == _TargetStatus.FOUND
    assert count == 6
    assert row_idx == 0


@pytest.mark.asyncio
async def test_extract_portal_total_mismatch_fails():
    handler = Report6Handler()
    modal_rows = [{"Ref. No.": "R1", "Mode": "Station"}]
    with (
        patch.object(handler, "_find_zone_wise_table", AsyncMock(return_value=MagicMock())),
        patch.object(
            handler,
            "_get_station_unsatisfactory_target",
            AsyncMock(return_value=(_TargetStatus.FOUND, 6, 1)),
        ),
        patch.object(handler, "_click_unsatisfactory_row_exact", AsyncMock(return_value=True)),
        patch.object(handler, "_read_modal_portal_total", AsyncMock(return_value=6)),
        patch.object(handler, "_extract_modal_pages", AsyncMock(return_value=modal_rows)),
        patch.object(handler, "_close_modal", AsyncMock()),
    ):
        count, complaints, error = await handler._extract_scr_complaints(
            AsyncMock(), MagicMock(), "scr-station"
        )
    assert len(complaints) == 1
    assert error is not None
    assert "REPORT6_PORTAL_EXTRACTION_COUNT_MISMATCH" in error
    assert count == 6


def test_report6_uses_run_scoped_extract_when_context_present():
    handler = Report6Handler()
    from app.automation.run_context import RunContext, set_run_context, reset_run_context
    from app.automation.timing import RunTiming

    ctx = RunContext(run_id="run-r6", timing=RunTiming(run_id="run-r6"))
    token = set_run_context(ctx)
    try:
        assert handler._uses_run_scoped_extract() is True
    finally:
        reset_run_context(token)


@pytest.mark.asyncio
async def test_get_target_tfoot_total_row_uses_th_cells():
    """Live portal puts Zone=ALL station Total in tfoot with th-only cells."""
    handler = Report6Handler()
    # NR zone row in tbody (td); aggregate Total in tfoot (th) — no SCR row.
    body = [
        _FakeRowWithCellTags(
            td_texts=["1", "Northern Railway", "27", "15.08", "4", "7", "16", "59.26"]
        ),
        _FakeRowWithCellTags(
            td_texts=[],
            th_texts=["", "Total", "179", "100%", "66", "42", "71", "39.66"],
        ),
    ]
    table = _FakeTableTfootTh(ZONE_HEADERS, body)

    async def fake_headers(_table):
        return ZONE_HEADERS

    with patch.object(handler, "_extract_table_headers", side_effect=fake_headers):
        status, count, row_idx = await handler._get_station_unsatisfactory_target(table)

    assert status == _TargetStatus.FOUND
    assert count == 71
    assert row_idx == 1


@pytest.mark.asyncio
async def test_get_target_missing_total_is_not_found():
    handler = Report6Handler()
    body = [
        ["1", "Secunderabad", "10", "50", "5", "5", "3", "30"],
    ]
    table = _FakeTable(ZONE_HEADERS, body)

    async def fake_headers(_table):
        return ZONE_HEADERS

    with patch.object(handler, "_extract_table_headers", side_effect=fake_headers):
        status, count, row_idx = await handler._get_station_unsatisfactory_target(table)

    assert status == _TargetStatus.NOT_FOUND
    assert count == 0
    assert row_idx is None


def test_processor_empty_csv_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    processor = Report6Processor()
    empty_csv = tmp_path / "empty.csv"
    empty_csv.write_text("Ref. No.,Mode\n", encoding="utf-8")

    monkeypatch.setattr(
        "app.automation.processing.report6_processor.config.extracted_data_dir",
        str(tmp_path / "extracted"),
    )
    monkeypatch.setattr(
        "app.automation.processing.report6_processor.config.output_excel_dir",
        str(tmp_path / "output" / "excel"),
    )
    monkeypatch.setattr(
        "app.automation.processing.report6_processor.config.output_pdf_dir",
        str(tmp_path / "output" / "pdf"),
    )
    monkeypatch.setattr(processor, "_find_template", lambda: None)

    result = processor.process(source_a_path=empty_csv, report_slug="scr-station")

    assert result.success is True
    assert result.processed_row_count == 0
    assert result.excel_path is not None
    assert result.pdf_path is not None
    assert Path(result.excel_path).exists()
    assert Path(result.pdf_path).exists()
