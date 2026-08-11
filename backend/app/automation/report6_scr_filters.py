"""Filter definitions for MIS Report 6 SCR (Station Mode Unsatisfactory Feedback)."""

from __future__ import annotations

from app.automation.report5_filters import REPORT_5_FILTERS
from app.automation.report1_filters import FilterFieldDefinition


def _with_mode(mode: str) -> list[FilterFieldDefinition]:
    filters: list[FilterFieldDefinition] = []
    for field in REPORT_5_FILTERS:
        if field.name == "mode":
            filters.append(
                FilterFieldDefinition(
                    name=field.name,
                    selector=field.selector,
                    field_type=field.field_type,
                    value=mode,
                    required=field.required,
                    label=field.label,
                )
            )
        else:
            filters.append(field)
    return filters


def _station_filters() -> list[FilterFieldDefinition]:
    """Station mode with Zone=SC (Report 6 spec: South Central Railway)."""
    filters: list[FilterFieldDefinition] = []
    for field in _with_mode("Station"):
        if field.name == "zone":
            filters.append(
                FilterFieldDefinition(
                    name=field.name,
                    selector=field.selector,
                    field_type=field.field_type,
                    value="SC",
                    required=field.required,
                    label=field.label,
                )
            )
        else:
            filters.append(field)
    return filters


REPORT_6_SCR_FILTERS: list[FilterFieldDefinition] = _station_filters()


def filters_for_report6_station() -> list[FilterFieldDefinition]:
    """Return the curated filter list for Report 6 SCR Station Mode."""
    return list(REPORT_6_SCR_FILTERS)
