"""Phase 8 post-ingestion report processing."""

from app.automation.processing.base import ProcessingResult
from app.automation.processing.service import process_report

__all__ = ["ProcessingResult", "process_report"]
