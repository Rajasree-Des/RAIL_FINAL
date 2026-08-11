"""Report handlers for multi-report automation."""

from .base import BaseReportHandler
from .registry import get_handler, HANDLER_REGISTRY

__all__ = [
    "BaseReportHandler",
    "get_handler",
    "HANDLER_REGISTRY",
]
