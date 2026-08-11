"""Table data validation for Phase 9 reliability hardening."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.automation.utils import log_automation_event

logger = logging.getLogger(__name__)

NO_DATA_MESSAGES = frozenset(
    {
        "no data available in table",
        "no records found",
        "no data",
        "no matching records found",
        "no results found",
    }
)

COMPREHENSIVE_REQUIRED_HEADERS = frozenset({"Organisation", "Received"})

FEEDBACK_REQUIRED_HEADERS = frozenset(
    {
        "Organisation",
        "Feedback Received",
    }
)

# Division Wise Feedback requires only feedback columns - Division/Organisation is checked separately
FEEDBACK_DIVISION_REQUIRED_HEADERS = frozenset(
    {
        "Feedback Received",
    }
)


@dataclass
class TableValidationResult:
    """Outcome of table data validation."""

    valid: bool
    error: str | None = None
    detected_issues: list[str] = field(default_factory=list)
    row_count: int = 0
    header_count: int = 0


def _normalize_for_comparison(text: str) -> str:
    """Normalize text for case-insensitive comparison."""
    return text.strip().lower()


def _contains_no_data_message(cell: str) -> bool:
    """Check if a cell contains a known empty-table message."""
    normalized = _normalize_for_comparison(cell)
    return normalized in NO_DATA_MESSAGES


def _headers_present(
    headers: list[str],
    required: frozenset[str],
) -> tuple[bool, set[str]]:
    """Check if required headers are present; return (ok, missing)."""
    normalized_headers = {_normalize_for_comparison(h) for h in headers}
    normalized_required = {_normalize_for_comparison(r) for r in required}
    missing = normalized_required - normalized_headers
    return len(missing) == 0, {r for r in required if _normalize_for_comparison(r) in missing}


def validate_extracted_data(
    data: list[list[str]],
    required_headers: frozenset[str] | None = None,
    min_data_rows: int = 1,
) -> TableValidationResult:
    """Validate extracted table data for completeness and validity.

    Checks:
    1. Data is not empty
    2. Headers exist (first row)
    3. Required headers are present (if specified)
    4. At least min_data_rows data rows exist (excluding header)
    5. No cell contains a known "no data" message

    Returns TableValidationResult with valid=True or error details.
    """
    issues: list[str] = []

    log_automation_event(logger, "table_validation_started")

    if not data:
        log_automation_event(logger, "table_validation_failed", reason="empty_data")
        return TableValidationResult(
            valid=False,
            error="Table data is empty",
            detected_issues=["empty_data"],
        )

    headers = data[0] if data else []
    data_rows = data[1:] if len(data) > 1 else []

    if not headers or all(not h.strip() for h in headers):
        issues.append("no_headers")
        log_automation_event(logger, "table_validation_failed", reason="no_headers")
        return TableValidationResult(
            valid=False,
            error="No headers found in table",
            detected_issues=issues,
            row_count=len(data_rows),
            header_count=0,
        )

    if required_headers:
        headers_ok, missing = _headers_present(headers, required_headers)
        if not headers_ok:
            issues.append("missing_headers")
            missing_str = ", ".join(sorted(missing))
            log_automation_event(
                logger,
                "table_validation_failed",
                reason="missing_headers",
                missing=missing_str,
            )
            return TableValidationResult(
                valid=False,
                error=f"Missing required headers: {missing_str}",
                detected_issues=issues,
                row_count=len(data_rows),
                header_count=len(headers),
            )

    if len(data_rows) < min_data_rows:
        issues.append("insufficient_rows")
        log_automation_event(
            logger,
            "table_validation_failed",
            reason="insufficient_rows",
            found=len(data_rows),
            required=min_data_rows,
        )
        return TableValidationResult(
            valid=False,
            error=f"Insufficient data rows: found {len(data_rows)}, need {min_data_rows}",
            detected_issues=issues,
            row_count=len(data_rows),
            header_count=len(headers),
        )

    for row_idx, row in enumerate(data_rows):
        for cell_idx, cell in enumerate(row):
            if _contains_no_data_message(cell):
                issues.append("no_data_message")
                log_automation_event(
                    logger,
                    "no_data_table_detected",
                    row=row_idx + 1,
                    cell=cell_idx,
                    content=cell[:100],
                )
                return TableValidationResult(
                    valid=False,
                    error=f"Table contains empty-state message: '{cell}'",
                    detected_issues=issues,
                    row_count=len(data_rows),
                    header_count=len(headers),
                )

    log_automation_event(
        logger,
        "table_validation_passed",
        row_count=len(data_rows),
        header_count=len(headers),
    )

    return TableValidationResult(
        valid=True,
        row_count=len(data_rows),
        header_count=len(headers),
    )


def get_required_headers_for_report(report_slug: str) -> frozenset[str] | None:
    """Return required headers for a report slug, or None for no check."""
    if report_slug == "report1":
        return COMPREHENSIVE_REQUIRED_HEADERS
    if report_slug == "report6":
        return FEEDBACK_REQUIRED_HEADERS
    return None
