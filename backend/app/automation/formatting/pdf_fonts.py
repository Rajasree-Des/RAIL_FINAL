"""Unicode-capable font registration for ReportLab PDF output."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)

PDF_FONT_REGULAR = "Helvetica"
PDF_FONT_BOLD = "Helvetica-Bold"
_UNICODE_EMBEDDED = False
_initialized = False


def _bundled_font_dir() -> Path:
    return Path(__file__).resolve().parent / "fonts"


def _font_candidates() -> list[tuple[str, Path, Path | None]]:
    candidates: list[tuple[str, Path, Path | None]] = []
    bundled = _bundled_font_dir()
    candidates.extend(
        [
            (
                "NotoSansBundled",
                bundled / "NotoSans-Regular.ttf",
                bundled / "NotoSans-Bold.ttf",
            ),
        ]
    )
    if sys.platform == "win32":
        fonts_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        candidates.extend(
            [
                # Prefer Indic-capable system fonts before Latin-only DejaVu.
                ("NirmalaUI", fonts_dir / "Nirmala.ttf", fonts_dir / "NirmalaB.ttf"),
                ("NirmalaUIAlt", fonts_dir / "NirmalaUI.ttf", fonts_dir / "NirmalaUIB.ttf"),
                ("NotoSans", fonts_dir / "NotoSans-Regular.ttf", fonts_dir / "NotoSans-Bold.ttf"),
                ("NotoSansTelugu", fonts_dir / "NotoSansTelugu-Regular.ttf", fonts_dir / "NotoSansTelugu-Bold.ttf"),
                ("SegoeUI", fonts_dir / "segoeui.ttf", fonts_dir / "segoeuib.ttf"),
                ("DejaVuSans", fonts_dir / "DejaVuSans.ttf", fonts_dir / "DejaVuSans-Bold.ttf"),
                ("Arial", fonts_dir / "arial.ttf", fonts_dir / "arialbd.ttf"),
            ]
        )
    linux_dirs = [
        Path("/usr/share/fonts/truetype/dejavu"),
        Path("/usr/share/fonts/truetype/noto"),
        Path("/usr/share/fonts/opentype/noto"),
        Path("/usr/local/share/fonts"),
    ]
    for directory in linux_dirs:
        candidates.append(
            ("DejaVuSans", directory / "DejaVuSans.ttf", directory / "DejaVuSans-Bold.ttf")
        )
        candidates.append(
            ("NotoSans", directory / "NotoSans-Regular.ttf", directory / "NotoSans-Bold.ttf")
        )
    return candidates


def ensure_pdf_unicode_fonts() -> bool:
    """Register the first available Unicode TTF; fall back to Helvetica."""
    global _initialized, PDF_FONT_REGULAR, PDF_FONT_BOLD, _UNICODE_EMBEDDED
    if _initialized:
        return _UNICODE_EMBEDDED
    _initialized = True

    for family, regular_path, bold_path in _font_candidates():
        if not regular_path.is_file():
            continue
        try:
            regular_name = f"RailReport-{family}"
            pdfmetrics.registerFont(TTFont(regular_name, str(regular_path)))
            PDF_FONT_REGULAR = regular_name
            if bold_path and bold_path.is_file():
                bold_name = f"RailReport-{family}-Bold"
                pdfmetrics.registerFont(TTFont(bold_name, str(bold_path)))
                PDF_FONT_BOLD = bold_name
            else:
                PDF_FONT_BOLD = regular_name
            _UNICODE_EMBEDDED = True
            logger.info(
                "pdf_unicode_font_registered family=%s regular=%s bold=%s",
                family,
                regular_path,
                bold_path,
            )
            break
        except Exception as exc:
            logger.warning("pdf_font_register_failed path=%s error=%s", regular_path, exc)

    if not _UNICODE_EMBEDDED:
        logger.warning("pdf_unicode_font_unavailable renderer=Helvetica")
    return _UNICODE_EMBEDDED


def pdf_font_regular() -> str:
    ensure_pdf_unicode_fonts()
    return PDF_FONT_REGULAR


def pdf_font_bold() -> str:
    ensure_pdf_unicode_fonts()
    return PDF_FONT_BOLD


def unicode_font_embedded() -> bool:
    ensure_pdf_unicode_fonts()
    return _UNICODE_EMBEDDED


def pdf_title_style(name: str = "ReportTitle"):
    ensure_pdf_unicode_fonts()
    styles = getSampleStyleSheet()
    return ParagraphStyle(
        name,
        parent=styles["Title"],
        fontName=pdf_font_bold(),
    )
