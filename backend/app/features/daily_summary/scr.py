"""SCR detection helpers for daily summary builders."""

from __future__ import annotations

import re

from app.automation.formatting.scr import SCR_PATTERN, row_contains_scr

_SCR_ABBREV = re.compile(r"(?:^|[^a-z])scr(?:[^a-z]|$)", re.IGNORECASE)
_SOUTH_CENTRAL = re.compile(r"south\s*central", re.IGNORECASE)


def text_is_scr(value: object) -> bool:
    """True if a zone/division/org string identifies South Central Railway."""
    if value is None:
        return False
    text = re.sub(r"\s+", " ", str(value).strip())
    if not text:
        return False
    if SCR_PATTERN.search(text):
        return True
    if _SOUTH_CENTRAL.search(text):
        return True
    if text.strip().upper() == "SCR":
        return True
    if _SCR_ABBREV.search(text):
        return True
    return False


def row_dict_is_scr(row: dict[str, str], *preferred_keys: str) -> bool:
    """Detect SCR from preferred keys first, then any cell values."""
    for key in preferred_keys:
        if key in row and text_is_scr(row.get(key, "")):
            return True
    # Common aliases
    for key in (
        "Owning Zone",
        "Owning Division",
        "Zone",
        "Div",
        "Owning Div",
        "Organisation",
        "Division",
    ):
        if key in row and text_is_scr(row.get(key, "")):
            return True
    return row_contains_scr(list(row.values()))
