"""Report 1 handler: source validation and fail-closed terminal status."""

from __future__ import annotations

from pathlib import Path

from app.automation.handlers.report1_handler import (
    REPORT1_COMPREHENSIVE_MISSING,
    Report1Handler,
    validate_report1_source_csv,
)
from app.automation.table_validator import COMPREHENSIVE_REQUIRED_HEADERS, FEEDBACK_REQUIRED_HEADERS


def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [",".join(headers)] + [",".join(r) for r in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    return path


def test_validate_comprehensive_ok(tmp_path: Path):
    csv_path = _write_csv(
        tmp_path / "comp.csv",
        ["Organisation", "Received", "Pending"],
        [["SCR", "10", "1"], ["NR", "5", "0"]],
    )
    ok, err, rows = validate_report1_source_csv(
        csv_path,
        required_headers=COMPREHENSIVE_REQUIRED_HEADERS,
        label="Comprehensive",
    )
    assert ok is True
    assert err is None
    assert rows == 2


def test_validate_missing_comprehensive_fails():
    ok, err, rows = validate_report1_source_csv(
        None,
        required_headers=COMPREHENSIVE_REQUIRED_HEADERS,
        label="Comprehensive",
    )
    assert ok is False
    assert "missing" in (err or "").lower()
    assert rows == 0


def test_validate_empty_file_fails(tmp_path: Path):
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    ok, err, _ = validate_report1_source_csv(
        empty,
        required_headers=COMPREHENSIVE_REQUIRED_HEADERS,
        label="Comprehensive",
    )
    assert ok is False
    assert "empty" in (err or "").lower()


def test_validate_feedback_headers(tmp_path: Path):
    csv_path = _write_csv(
        tmp_path / "fb.csv",
        ["Organisation", "Feedback Received", "% Feedback"],
        [["SCR", "3", "10"]],
    )
    ok, err, rows = validate_report1_source_csv(
        csv_path,
        required_headers=FEEDBACK_REQUIRED_HEADERS,
        label="Feedback",
    )
    assert ok is True
    assert rows == 1


def test_failed_result_is_failed_not_partial():
    from app.automation.handlers.report1_handler import Report1Handler

    handler = Report1Handler()
    result = handler._failed(
        "report1",
        f"{REPORT1_COMPREHENSIVE_MISSING}: path is missing",
        source_paths=["only_feedback.csv"],
        row_counts={"feedback": 20},
    )
    assert result.status == "failed"
    assert result.processing_success is False
    assert result.excel_path is None
    assert result.pdf_path is None
    assert REPORT1_COMPREHENSIVE_MISSING in (result.error or "")
