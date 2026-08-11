"""Unit tests for report downloader."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.automation.downloader import ReportDownloader, VALID_EXTENSIONS


def test_generate_filename_includes_timestamp():
    downloader = ReportDownloader(downloads_dir="/tmp/test-downloads")
    filename = downloader._generate_filename("report1", ".xlsx")
    assert filename.startswith("report1_")
    assert filename.endswith(".xlsx")
    assert len(filename.split("_")) >= 3


def test_unique_target_path_appends_suffix_when_exists(tmp_path: Path):
    downloader = ReportDownloader(downloads_dir=tmp_path)
    existing = tmp_path / "report1_2026-07-10_12-00-00.xlsx"
    existing.write_bytes(b"x")

    unique = downloader._unique_target_path(existing)
    assert unique.name == "report1_2026-07-10_12-00-00_1.xlsx"


@pytest.mark.asyncio
async def test_validate_download_accepts_pdf(tmp_path: Path):
    downloader = ReportDownloader(downloads_dir=tmp_path)
    pdf_path = tmp_path / "report1.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 content")

    assert await downloader.validate_download(pdf_path) is True


@pytest.mark.asyncio
async def test_validate_download_accepts_nonempty_xlsx(tmp_path: Path):
    downloader = ReportDownloader(downloads_dir=tmp_path)
    xlsx_path = tmp_path / "report1.xlsx"
    xlsx_path.write_bytes(b"PK\x03\x04")

    assert await downloader.validate_download(xlsx_path) is True


def test_is_pdf_only_button():
    assert ReportDownloader._is_pdf_only_button("PDF") is True
    assert ReportDownloader._is_pdf_only_button("Export to Excel") is False


def test_valid_extensions_include_pdf():
    assert ".pdf" in VALID_EXTENSIONS


@pytest.mark.asyncio
async def test_wait_for_download_ready_prefers_spreadsheet(tmp_path: Path):
    downloader = ReportDownloader(downloads_dir=tmp_path)
    page = MagicMock()
    page.wait_for_load_state = AsyncMock()

    spreadsheet_button = MagicMock()
    pdf_called = False

    async def fake_find_spreadsheet(*_args, **_kwargs):
        return spreadsheet_button

    async def fake_find_pdf(*_args, **_kwargs):
        nonlocal pdf_called
        pdf_called = True
        return MagicMock()

    downloader._find_spreadsheet_export_button = fake_find_spreadsheet
    downloader._find_pdf_export_button = fake_find_pdf

    button, export_format = await downloader.wait_for_download_ready(page, page)

    assert button is spreadsheet_button
    assert export_format == "spreadsheet"
    assert pdf_called is False


@pytest.mark.asyncio
async def test_wait_for_download_ready_falls_back_to_pdf(tmp_path: Path):
    downloader = ReportDownloader(downloads_dir=tmp_path)
    page = MagicMock()
    page.wait_for_load_state = AsyncMock()

    pdf_button = MagicMock()

    async def fake_find_spreadsheet(*_args, **_kwargs):
        return None

    async def fake_find_pdf(*_args, **_kwargs):
        return pdf_button

    downloader._find_spreadsheet_export_button = fake_find_spreadsheet
    downloader._find_pdf_export_button = fake_find_pdf

    button, export_format = await downloader.wait_for_download_ready(page, page)

    assert button is pdf_button
    assert export_format == "pdf"
