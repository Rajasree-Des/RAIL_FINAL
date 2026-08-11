"""Unit tests for table data validation (Phase 9)."""

import pytest

from app.automation.table_validator import (
    COMPREHENSIVE_REQUIRED_HEADERS,
    FEEDBACK_REQUIRED_HEADERS,
    TableValidationResult,
    get_required_headers_for_report,
    validate_extracted_data,
)


def test_empty_data_rejected():
    result = validate_extracted_data([])
    assert result.valid is False
    assert "empty" in result.error.lower()
    assert "empty_data" in result.detected_issues


def test_no_headers_rejected():
    result = validate_extracted_data([["", "", ""]])
    assert result.valid is False
    assert "header" in result.error.lower()
    assert "no_headers" in result.detected_issues


def test_header_only_rejected():
    data = [["Organisation", "Received", "Closed"]]
    result = validate_extracted_data(data, min_data_rows=1)
    assert result.valid is False
    assert "insufficient" in result.error.lower()
    assert "insufficient_rows" in result.detected_issues


def test_no_data_available_message_rejected():
    data = [
        ["S.No.", "Organisation", "Received"],
        ["No data available in table"],
    ]
    result = validate_extracted_data(data)
    assert result.valid is False
    assert "empty-state" in result.error.lower() or "no data" in result.error.lower()
    assert "no_data_message" in result.detected_issues


def test_no_records_found_message_rejected():
    data = [
        ["Organisation", "Received", "Closed"],
        ["No records found"],
    ]
    result = validate_extracted_data(data)
    assert result.valid is False
    assert "no_data_message" in result.detected_issues


def test_valid_data_accepted():
    data = [
        ["Organisation", "Received", "Closed"],
        ["Northern Railway", "100", "95"],
        ["Central Railway", "80", "75"],
    ]
    result = validate_extracted_data(data)
    assert result.valid is True
    assert result.error is None
    assert result.row_count == 2
    assert result.header_count == 3


def test_missing_required_headers_rejected():
    data = [
        ["Organisation", "Closed"],
        ["Northern Railway", "95"],
    ]
    result = validate_extracted_data(data, required_headers=COMPREHENSIVE_REQUIRED_HEADERS)
    assert result.valid is False
    assert "missing" in result.error.lower()
    assert "missing_headers" in result.detected_issues
    assert "Received" in result.error


def test_required_headers_present_accepted():
    data = [
        ["Organisation", "Received", "Extra Column"],
        ["Northern Railway", "100", "extra"],
    ]
    result = validate_extracted_data(data, required_headers=COMPREHENSIVE_REQUIRED_HEADERS)
    assert result.valid is True


def test_feedback_required_headers():
    data = [
        ["Organisation", "Feedback Received", "% Feedback"],
        ["Northern Railway", "50", "10.5"],
    ]
    result = validate_extracted_data(data, required_headers=FEEDBACK_REQUIRED_HEADERS)
    assert result.valid is True


def test_feedback_missing_headers_rejected():
    data = [
        ["Organisation", "Something Else"],
        ["Northern Railway", "100"],
    ]
    result = validate_extracted_data(data, required_headers=FEEDBACK_REQUIRED_HEADERS)
    assert result.valid is False
    assert "Feedback Received" in result.error


def test_case_insensitive_header_match():
    data = [
        ["ORGANISATION", "RECEIVED"],
        ["Northern Railway", "100"],
    ]
    result = validate_extracted_data(data, required_headers=COMPREHENSIVE_REQUIRED_HEADERS)
    assert result.valid is True


def test_get_required_headers_for_report():
    assert get_required_headers_for_report("report1") == COMPREHENSIVE_REQUIRED_HEADERS
    assert get_required_headers_for_report("report6") == FEEDBACK_REQUIRED_HEADERS
    assert get_required_headers_for_report("unknown") is None


def test_min_data_rows_custom():
    data = [
        ["Organisation", "Received"],
        ["Northern Railway", "100"],
    ]
    result = validate_extracted_data(data, min_data_rows=2)
    assert result.valid is False
    assert "insufficient" in result.error.lower()

    result = validate_extracted_data(data, min_data_rows=1)
    assert result.valid is True


def test_validation_result_dataclass():
    result = TableValidationResult(
        valid=True,
        row_count=5,
        header_count=3,
    )
    assert result.valid is True
    assert result.row_count == 5
    assert result.header_count == 3
    assert result.error is None
    assert result.detected_issues == []
