"""Report processor registry."""

from __future__ import annotations

from typing import Any

from app.automation.processing.report1_processor import (
    PROCESSOR_NAME as REPORT1_PROCESSOR_NAME,
    Report1Processor,
)
from app.automation.processing.report2_processor import Report2Processor
from app.automation.processing.report3_processor import Report3Processor
from app.automation.processing.report4_processor import Report4Processor
from app.automation.processing.report5_processor import Report5Processor
from app.automation.processing.report6_processor import Report6Processor
from app.automation.processing.comprehensive1013_processor import Comprehensive1013Processor
from app.automation.processing.report9_processor import Report9Processor
from app.automation.processing.report14_processor import Report14Processor
from app.automation.processing.report18_processor import Report18Processor
from app.automation.processing.bottom_report_processor import BottomReportProcessor
from app.automation.report_keys import canonicalize_report_key

_PROCESSORS: dict[str, Any] = {
    "report1": Report1Processor(),
    "division": Report2Processor(),
    "train-no": Report3Processor(),
    "types": Report4Processor(),
    "scr-train": Report5Processor(),
    "scr-station": Report6Processor(),
    "report9": Report9Processor(),
    "comprehensive-10-13": Comprehensive1013Processor(),
    "report14": Report14Processor(),
    "report18": Report18Processor(),
    "bottom-report": BottomReportProcessor(),
}


class _ProcessorLookup(dict):
    """Dict that resolves aliases to canonical processor keys."""

    def get(self, key, default=None):  # type: ignore[override]
        try:
            canonical = canonicalize_report_key(str(key))
        except ValueError:
            return default
        return super().get(canonical, default)

    def __contains__(self, key: object) -> bool:
        try:
            canonical = canonicalize_report_key(str(key))
        except ValueError:
            return False
        return super().__contains__(canonical)

    def __getitem__(self, key):  # type: ignore[override]
        canonical = canonicalize_report_key(str(key))
        return super().__getitem__(canonical)


PROCESSORS: dict[str, Any] = _ProcessorLookup(_PROCESSORS)

PROCESSOR_NAME = REPORT1_PROCESSOR_NAME
