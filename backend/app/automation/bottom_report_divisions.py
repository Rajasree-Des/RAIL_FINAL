"""Division name → code mapping for Bottom Performed Trains Report."""

from __future__ import annotations

import re

_DIVISION_ABBREVS: dict[str, str] = {
    "secunderabad": "SC",
    "hyderabad": "HYB",
    "nanded": "NED",
    "vijayawada": "BZA",
    "guntur": "GNT",
    "guntakal": "GTL",
}


def _normalize_division_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).lower()


def is_total_division_row(division_name: str) -> bool:
    """Return True when the row is a portal Total/grand-total division label."""
    text = _normalize_division_text(division_name)
    if not text:
        return True
    if text in {"total", "total:", "grand total"}:
        return True
    if text.startswith("total "):
        return True
    if " grand total" in text:
        return True
    return False


def division_code_from_name(division_name: str) -> str:
    """Map portal division label to short code (SC, HYB, NED, …)."""
    text = _normalize_division_text(division_name)
    if not text:
        return ""
    for pattern, code in _DIVISION_ABBREVS.items():
        if pattern in text:
            return code
    # Fallback: first token before DIVISION / parentheses
    cleaned = re.sub(r"\(.*?\)", "", division_name or "").strip()
    token = cleaned.split()[0] if cleaned.split() else cleaned
    token = re.sub(r"[^A-Za-z]", "", token).upper()
    if len(token) >= 2:
        return token[:3]
    return token or "UNK"


def parse_received_count(value: str) -> int:
    """Parse Received cell text to integer."""
    text = str(value or "").strip()
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        return 0
    try:
        return int(digits)
    except ValueError:
        return 0
