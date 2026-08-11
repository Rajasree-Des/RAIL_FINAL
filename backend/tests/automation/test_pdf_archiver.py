"""Unit tests for PDF archiver."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.automation.pdf_archiver import PdfArchiver, PdfArchiveResult


def test_generate_filename_includes_timestamp():
    archiver = PdfArchiver(archive_dir="/tmp/test-archive")
    filename = archiver._generate_filename("report1")
    assert filename.startswith("report1_")
    assert filename.endswith(".pdf")
    parts = filename.split("_")
    assert len(parts) >= 3


def test_unique_path_appends_suffix_when_exists(tmp_path: Path):
    archiver = PdfArchiver(archive_dir=tmp_path)
    existing = tmp_path / "report1_2026-07-10_12-00-00.pdf"
    existing.write_bytes(b"pdf content")

    unique = archiver._unique_path(existing)
    assert unique.name == "report1_2026-07-10_12-00-00_1.pdf"


def test_is_valid_pdf_returns_true_for_valid_file(tmp_path: Path):
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 " + b"x" * 200)

    assert PdfArchiver.is_valid_pdf(pdf_path) is True


def test_is_valid_pdf_returns_false_for_missing_file():
    assert PdfArchiver.is_valid_pdf(Path("/nonexistent/file.pdf")) is False


def test_is_valid_pdf_returns_false_for_non_pdf(tmp_path: Path):
    xlsx_path = tmp_path / "test.xlsx"
    xlsx_path.write_bytes(b"PK\x03\x04" + b"x" * 200)

    assert PdfArchiver.is_valid_pdf(xlsx_path) is False


def test_is_valid_pdf_returns_false_for_empty_file(tmp_path: Path):
    pdf_path = tmp_path / "empty.pdf"
    pdf_path.write_bytes(b"")

    assert PdfArchiver.is_valid_pdf(pdf_path) is False


def test_reuse_existing_pdf_copies_file(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()

    source_pdf = source_dir / "phase6.pdf"
    source_pdf.write_bytes(b"%PDF-1.4 " + b"x" * 200)

    archiver = PdfArchiver(archive_dir=archive_dir)
    result = archiver.reuse_existing_pdf(source_pdf, "report1")

    assert result.success is True
    assert result.source == "phase6_reuse"
    assert result.file_path is not None
    assert result.file_path.exists()
    assert result.file_path.parent == archive_dir


def test_reuse_existing_pdf_same_dir_no_copy(tmp_path: Path):
    source_pdf = tmp_path / "phase6.pdf"
    source_pdf.write_bytes(b"%PDF-1.4 " + b"x" * 200)

    archiver = PdfArchiver(archive_dir=tmp_path)
    result = archiver.reuse_existing_pdf(source_pdf, "report1")

    assert result.success is True
    assert result.source == "phase6_reuse"
    assert result.file_path == source_pdf


def test_reuse_existing_pdf_invalid_file_returns_failure(tmp_path: Path):
    archiver = PdfArchiver(archive_dir=tmp_path)
    result = archiver.reuse_existing_pdf(Path("/nonexistent.pdf"), "report1")

    assert result.success is False
    assert "invalid" in result.error.lower() or "missing" in result.error.lower()


@pytest.mark.asyncio
async def test_archive_pdf_reuses_phase6_pdf(tmp_path: Path):
    source_pdf = tmp_path / "source" / "phase6.pdf"
    source_pdf.parent.mkdir()
    source_pdf.write_bytes(b"%PDF-1.4 " + b"x" * 200)

    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()

    archiver = PdfArchiver(archive_dir=archive_dir)

    mock_page = MagicMock()
    mock_root = MagicMock()

    result = await archiver.archive_pdf(
        mock_page,
        mock_root,
        "report1",
        existing_pdf_path=source_pdf,
    )

    assert result.success is True
    assert result.source == "phase6_reuse"


@pytest.mark.asyncio
async def test_archive_pdf_fallback_when_no_phase6_pdf(tmp_path: Path):
    archiver = PdfArchiver(archive_dir=tmp_path)

    fallback_called = False

    async def mock_export(*args, **kwargs):
        nonlocal fallback_called
        fallback_called = True
        return PdfArchiveResult(success=True, source="download")

    archiver.archive_from_export = mock_export

    mock_page = MagicMock()
    mock_root = MagicMock()

    result = await archiver.archive_pdf(
        mock_page,
        mock_root,
        "report1",
        existing_pdf_path=None,
    )

    assert fallback_called is True


@pytest.mark.asyncio
async def test_find_pdf_button_returns_visible_button():
    archiver = PdfArchiver(archive_dir="/tmp/test")

    mock_button = MagicMock()
    mock_button.count = AsyncMock(return_value=1)
    mock_button.nth = MagicMock(return_value=mock_button)
    mock_button.is_visible = AsyncMock(return_value=True)

    mock_root = MagicMock()
    mock_root.locator = MagicMock(return_value=mock_button)

    mock_page = MagicMock()
    mock_page.locator = MagicMock(return_value=mock_button)

    button = await archiver.find_pdf_button(mock_root, mock_page, timeout_ms=100)
    assert button is not None


@pytest.mark.asyncio
async def test_find_print_button_returns_visible_button():
    archiver = PdfArchiver(archive_dir="/tmp/test")

    mock_button = MagicMock()
    mock_button.count = AsyncMock(return_value=1)
    mock_button.nth = MagicMock(return_value=mock_button)
    mock_button.is_visible = AsyncMock(return_value=True)

    mock_root = MagicMock()
    mock_root.locator = MagicMock(return_value=mock_button)

    mock_page = MagicMock()
    mock_page.locator = MagicMock(return_value=mock_button)

    button = await archiver.find_print_button(mock_root, mock_page, timeout_ms=100)
    assert button is not None


@pytest.mark.asyncio
async def test_archive_from_export_returns_failure_when_no_button():
    archiver = PdfArchiver(archive_dir="/tmp/test")

    async def no_button(*args, **kwargs):
        return None

    archiver.find_pdf_button = no_button

    mock_page = MagicMock()
    mock_page.url = "https://example.com"
    mock_root = MagicMock()

    result = await archiver.archive_from_export(mock_page, mock_root, "report1")

    assert isinstance(result, PdfArchiveResult)
    assert result.success is False
    assert "not found" in result.error.lower()


@pytest.mark.asyncio
async def test_archive_from_print_returns_failure_when_no_button():
    archiver = PdfArchiver(archive_dir="/tmp/test")

    async def no_button(*args, **kwargs):
        return None

    archiver.find_print_button = no_button

    mock_page = MagicMock()
    mock_page.url = "https://example.com"
    mock_root = MagicMock()

    result = await archiver.archive_from_print(mock_page, mock_root, "report1")

    assert isinstance(result, PdfArchiveResult)
    assert result.success is False
    assert "not found" in result.error.lower()


@pytest.mark.asyncio
async def test_restore_original_tab_calls_bring_to_front():
    archiver = PdfArchiver(archive_dir="/tmp/test")

    mock_page = MagicMock()
    mock_page.bring_to_front = AsyncMock()
    mock_page.url = "https://example.com"

    result = await archiver._restore_original_tab(mock_page)

    assert result is True
    mock_page.bring_to_front.assert_called_once()


@pytest.mark.asyncio
async def test_close_popup_safely_handles_closed_page():
    archiver = PdfArchiver(archive_dir="/tmp/test")

    mock_popup = MagicMock()
    mock_popup.is_closed = MagicMock(return_value=True)

    await archiver._close_popup_safely(mock_popup)


@pytest.mark.asyncio
async def test_render_page_as_pdf_creates_file(tmp_path: Path):
    archiver = PdfArchiver(archive_dir=tmp_path)

    mock_popup = MagicMock()
    pdf_content = b"%PDF-1.4 " + b"x" * 200
    mock_popup.pdf = AsyncMock(return_value=pdf_content)

    target_path = tmp_path / "test.pdf"
    result = await archiver._render_page_as_pdf(mock_popup, target_path)

    assert result is not None
    assert result.exists()
    assert result.stat().st_size >= 100


@pytest.mark.asyncio
async def test_fetch_pdf_from_url_saves_content(tmp_path: Path):
    archiver = PdfArchiver(archive_dir=tmp_path)

    pdf_content = b"%PDF-1.4 " + b"x" * 200
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.body = AsyncMock(return_value=pdf_content)

    mock_request = MagicMock()
    mock_request.get = AsyncMock(return_value=mock_response)

    mock_context = MagicMock()
    mock_context.request = mock_request

    mock_popup = MagicMock()
    mock_popup.context = mock_context

    target_path = tmp_path / "fetched.pdf"
    result = await archiver._fetch_pdf_from_url(mock_popup, "https://example.com/report.pdf", target_path)

    assert result is not None
    assert result.exists()
    assert result.stat().st_size >= 100


@pytest.mark.asyncio
async def test_archive_pdf_uses_print_when_specified(tmp_path: Path):
    archiver = PdfArchiver(archive_dir=tmp_path)

    print_called = False
    export_called = False

    async def mock_print(*args, **kwargs):
        nonlocal print_called
        print_called = True
        return PdfArchiveResult(success=True, source="print")

    async def mock_export(*args, **kwargs):
        nonlocal export_called
        export_called = True
        return PdfArchiveResult(success=True, source="export")

    archiver.archive_from_print = mock_print
    archiver.archive_from_export = mock_export

    mock_page = MagicMock()
    mock_root = MagicMock()

    result = await archiver.archive_pdf(mock_page, mock_root, "report6", use_print=True)

    assert print_called is True
    assert export_called is False
    assert result.source == "print"


@pytest.mark.asyncio
async def test_archive_pdf_uses_export_by_default(tmp_path: Path):
    archiver = PdfArchiver(archive_dir=tmp_path)

    print_called = False
    export_called = False

    async def mock_print(*args, **kwargs):
        nonlocal print_called
        print_called = True
        return PdfArchiveResult(success=True, source="print")

    async def mock_export(*args, **kwargs):
        nonlocal export_called
        export_called = True
        return PdfArchiveResult(success=True, source="export")

    archiver.archive_from_print = mock_print
    archiver.archive_from_export = mock_export

    mock_page = MagicMock()
    mock_root = MagicMock()

    result = await archiver.archive_pdf(mock_page, mock_root, "report1", use_print=False)

    assert export_called is True
    assert print_called is False
    assert result.source == "export"


def test_pdf_archive_result_dataclass():
    result = PdfArchiveResult(
        success=True,
        file_path=Path("/tmp/test.pdf"),
        file_size=1024,
        source="phase6_reuse",
    )
    assert result.success is True
    assert result.file_path == Path("/tmp/test.pdf")
    assert result.file_size == 1024
    assert result.source == "phase6_reuse"
    assert result.error is None


def test_no_double_report_slug_in_path(tmp_path: Path):
    archive_dir = tmp_path / "downloads" / "report1"
    archive_dir.mkdir(parents=True)

    archiver = PdfArchiver(archive_dir=archive_dir)
    filename = archiver._generate_filename("report1")
    target_path = archiver._unique_path(archiver.archive_dir / filename)

    assert "report1/report1" not in str(target_path)
    assert target_path.parent == archive_dir


def test_resolve_report_dir_avoids_double_slug(tmp_path: Path):
    from app.automation.utils import resolve_report_dir

    base = tmp_path / "downloads" / "report1"
    base.mkdir(parents=True)
    resolved = resolve_report_dir(base, "report1")
    assert resolved == base
    assert resolved.name == "report1"


def test_is_valid_pdf_rejects_wrong_magic_bytes(tmp_path: Path):
    pdf_path = tmp_path / "fake.pdf"
    pdf_path.write_bytes(b"NOTPDF" + b"x" * 200)
    assert PdfArchiver.is_valid_pdf(pdf_path) is False


@pytest.mark.asyncio
async def test_archive_pdf_reuse_does_not_call_find_pdf_button(tmp_path: Path):
    source_pdf = tmp_path / "phase6.pdf"
    source_pdf.write_bytes(b"%PDF-1.4 " + b"x" * 200)

    archiver = PdfArchiver(archive_dir=tmp_path)
    archiver.find_pdf_button = AsyncMock(return_value=MagicMock())

    mock_page = MagicMock()
    mock_root = MagicMock()

    result = await archiver.archive_pdf(
        mock_page,
        mock_root,
        "report1",
        existing_pdf_path=source_pdf,
    )

    assert result.success is True
    assert result.source == "phase6_reuse"
    archiver.find_pdf_button.assert_not_called()


@pytest.mark.asyncio
async def test_click_and_capture_tries_popup_after_invalid_download(tmp_path: Path):
    archiver = PdfArchiver(archive_dir=tmp_path)
    target_path = tmp_path / "report1_test.pdf"

    mock_download = MagicMock()
    mock_download.suggested_filename = "bad.bin"

    async def save_as(path: str) -> None:
        Path(path).write_bytes(b"not a pdf")

    mock_download.save_as = save_as

    mock_popup = MagicMock()
    mock_popup.url = "about:blank"
    mock_popup.is_closed = MagicMock(return_value=False)
    mock_popup.close = AsyncMock()
    pdf_content = b"%PDF-1.4 " + b"x" * 200
    mock_popup.pdf = AsyncMock(return_value=pdf_content)
    mock_popup.wait_for_load_state = AsyncMock()

    mock_page = MagicMock()
    mock_page.bring_to_front = AsyncMock()
    mock_page.wait_for_event = AsyncMock(return_value=mock_download)
    mock_page.context.wait_for_event = AsyncMock(return_value=mock_popup)

    mock_button = MagicMock()
    mock_button.click = AsyncMock()

    result = await archiver._click_and_capture(mock_page, mock_button, "report1")

    assert result.success is True
    assert result.source == "popup"
