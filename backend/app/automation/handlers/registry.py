"""Handler registry for dispatching reports to the correct handler."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.automation.report_keys import canonicalize_report_key

if TYPE_CHECKING:
    from .base import BaseReportHandler

HANDLER_REGISTRY: dict[str, type["BaseReportHandler"]] = {}


def register_handler(slug: str, handler_cls: type["BaseReportHandler"]) -> None:
    """Register a handler class for a report slug."""
    HANDLER_REGISTRY[canonicalize_report_key(slug)] = handler_cls


def get_handler(slug: str) -> "BaseReportHandler":
    """Return a fresh handler instance for a report slug (aliases resolve to canonical keys)."""
    key = canonicalize_report_key(slug)
    if key not in HANDLER_REGISTRY:
        raise ValueError(f"No handler registered for report slug: {slug}")
    return HANDLER_REGISTRY[key]()


def _register_all_handlers() -> None:
    """Register all report handlers. Called once at import time."""
    from .report1_handler import Report1Handler
    from .report2_handler import Report2Handler
    from .report3_handler import Report3Handler
    from .report4_handler import Report4Handler
    from .report5_handler import Report5Handler
    from .report6_handler import Report6Handler
    from .report9_handler import Report9Handler
    from .comprehensive1013_handler import Comprehensive1013Handler
    from .report14_handler import Report14Handler
    from .report18_handler import Report18Handler
    from .bottom_report_handler import BottomReportHandler

    register_handler("report1", Report1Handler)
    register_handler("division", Report2Handler)
    register_handler("train-no", Report3Handler)
    register_handler("types", Report4Handler)
    register_handler("scr-train", Report5Handler)
    register_handler("scr-station", Report6Handler)
    register_handler("report9", Report9Handler)
    register_handler("comprehensive-10-13", Comprehensive1013Handler)
    register_handler("report14", Report14Handler)
    register_handler("report18", Report18Handler)
    register_handler("bottom-report", BottomReportHandler)


_register_all_handlers()
