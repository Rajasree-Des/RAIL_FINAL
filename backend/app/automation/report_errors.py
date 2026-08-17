"""Shared report automation error types."""

from __future__ import annotations

from app.core.exceptions import AppException


class ReportGenerationError(AppException):
    """Raised when report generation or results verification fails."""

    def __init__(self, message: str, *, code: str = "REPORT_GENERATION_ERROR") -> None:
        super().__init__(message=message, code=code)


class ReportStageError(ReportGenerationError):
    """Stage-scoped automation failure with a machine-readable code."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        stage: str,
        report_slug: str,
    ) -> None:
        super().__init__(message, code=code)
        self.stage = stage
        self.report_slug = report_slug
