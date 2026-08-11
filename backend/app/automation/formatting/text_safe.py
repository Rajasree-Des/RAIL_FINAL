"""Shared safe text normalization for report Excel/PDF rendering."""

from __future__ import annotations

import html
import logging
import re
import unicodedata
from typing import Literal

logger = logging.getLogger(__name__)

FieldKind = Literal["text", "id", "numeric", "header"]

_INVALID_XML_RE = re.compile(
    r"[\x00-\x08\x0B\x0C\x0E-\x1F"
    r"\uFFFE\uFFFF"
    r"]"
)
_ZERO_WIDTH_RE = re.compile(r"[\u200B-\u200D\uFEFF\u2060]")
_BAD_GLYPH_RE = re.compile(r"[\uFFFD\u25A0\u25AA]")
_BR_TAG_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_BLOCK_BREAK_RE = re.compile(r"</(?:p|div|li|tr|h\d)\s*>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_MULTISPACE_RE = re.compile(r"[^\S\n]+")
_EXCESS_NEWLINES_RE = re.compile(r"\n{3,}")

NUMERIC_HEADERS = frozenset(
    {
        "S.No.",
        "Received",
        "Closed",
        "Opening Balance",
        "Closing Balance",
        "% Share",
        "% Disposal",
        "% Feedback",
        "% Unsatisfactory",
        "Feedback Received",
        "Excellent",
        "Satisfactory",
        "Unsatisfactory",
        "Forwarded",
        "Avg. FRT",
        "Avg. Disposal Time",
        "Avg. Rating",
        "Avg. Pendency Time",
    }
)

ID_HEADERS = frozenset(
    {
        "Complaint Ref Number",
        "Ref. No.",
        "User ID",
        "Train No.",
        "Train/Station",
        "PNR/UTS No.",
    }
)


class UnsupportedTextRenderingError(ValueError):
    """Raised when final output still contains unrenderable text markers."""


def field_kind_for_header(header: str) -> FieldKind:
    if header in NUMERIC_HEADERS:
        return "numeric"
    if header in ID_HEADERS:
        return "id"
    return "text"


def _decode_html_content(text: str) -> str:
    decoded = _BR_TAG_RE.sub("\n", text)
    decoded = _BLOCK_BREAK_RE.sub("\n", decoded)
    decoded = _TAG_RE.sub("", decoded)
    return html.unescape(decoded)


def _strip_control_chars(text: str) -> str:
    cleaned = _INVALID_XML_RE.sub("", text)
    return _ZERO_WIDTH_RE.sub("", cleaned)


def _log_text_diagnostic(
    *,
    report_slug: str,
    column_name: str,
    row_identifier: str,
    before: str,
    after: str,
) -> None:
    suspicious = sorted({f"U+{ord(ch):04X}" for ch in before if ord(ch) < 32 or ord(ch) in (0xFFFD, 0x200B, 0xFEFF)})
    logger.info(
        "report_text_normalized report_slug=%s row=%s column=%s repr_before=%r repr_after=%r codepoints=%s",
        report_slug,
        row_identifier,
        column_name,
        before,
        after,
        suspicious,
    )


def normalize_report_text(
    value: object,
    *,
    field_kind: FieldKind = "text",
    report_slug: str = "",
    column_name: str = "",
    row_identifier: str = "",
) -> str:
    """Normalize one cell for rendering; never blank the whole cell for one bad char."""
    if value is None:
        return ""
    text = str(value)
    original = text

    if field_kind == "numeric":
        cleaned = _strip_control_chars(text)
        return cleaned.strip()

    if field_kind == "id":
        cleaned = _decode_html_content(text)
        cleaned = _strip_control_chars(cleaned)
        cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
        if cleaned != original and (_INVALID_XML_RE.search(original) or "<" in original):
            _log_text_diagnostic(
                report_slug=report_slug,
                column_name=column_name,
                row_identifier=row_identifier,
                before=original,
                after=cleaned,
            )
        return cleaned.strip()

    cleaned = _decode_html_content(text)
    cleaned = unicodedata.normalize("NFKC", cleaned)
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = _strip_control_chars(cleaned)
    cleaned = _BAD_GLYPH_RE.sub("", cleaned)
    cleaned = _MULTISPACE_RE.sub(" ", cleaned)
    cleaned = _EXCESS_NEWLINES_RE.sub("\n\n", cleaned)
    cleaned = cleaned.strip()

    if cleaned != original.strip() and (
        _INVALID_XML_RE.search(original)
        or _ZERO_WIDTH_RE.search(original)
        or _BAD_GLYPH_RE.search(original)
        or "<" in original
    ):
        _log_text_diagnostic(
            report_slug=report_slug,
            column_name=column_name,
            row_identifier=row_identifier,
            before=original,
            after=cleaned,
        )
    return cleaned


def contains_non_latin1(text: str) -> bool:
    return any(ord(ch) > 255 for ch in text)


def contains_rendering_risk_markers(text: str) -> bool:
    return bool(_BAD_GLYPH_RE.search(text) or "\ufffd" in text)


def row_identifier_from_values(values: list[str]) -> str:
    if not values:
        return ""
    return str(values[0] or "")
