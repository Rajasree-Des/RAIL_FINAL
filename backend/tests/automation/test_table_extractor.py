"""Unit tests for HTML table extractor."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.automation.table_extractor import TableExtractor, ExtractionResult


def test_generate_filename_includes_timestamp():
    extractor = TableExtractor(output_dir="/tmp/test-extracted")
    filename = extractor._generate_filename("report1", ".csv")
    assert filename.startswith("report1_")
    assert filename.endswith(".csv")
    parts = filename.split("_")
    assert len(parts) >= 3


def test_unique_path_appends_suffix_when_exists(tmp_path: Path):
    extractor = TableExtractor(output_dir=tmp_path)
    existing = tmp_path / "report1_2026-07-10_12-00-00.csv"
    existing.write_text("x")

    unique = extractor._unique_path(existing)
    assert unique.name == "report1_2026-07-10_12-00-00_1.csv"


def test_clean_cell_text_normalizes_whitespace():
    result = TableExtractor._clean_cell_text("  hello   world\n\t ")
    assert result == "hello world"


@pytest.mark.asyncio
async def test_save_as_csv_creates_file(tmp_path: Path):
    extractor = TableExtractor(output_dir=tmp_path)
    data = [
        ["Header1", "Header2", "Header3"],
        ["Row1Col1", "Row1Col2", "Row1Col3"],
        ["Row2Col1", "Row2Col2", "Row2Col3"],
    ]

    csv_path = await extractor.save_as_csv(data, "report1")

    assert csv_path is not None
    assert csv_path.exists()
    assert csv_path.suffix == ".csv"
    content = csv_path.read_text(encoding="utf-8-sig")
    assert "Header1" in content
    assert "Row1Col1" in content


@pytest.mark.asyncio
async def test_save_as_csv_returns_none_for_empty_data(tmp_path: Path):
    extractor = TableExtractor(output_dir=tmp_path)
    csv_path = await extractor.save_as_csv([], "report1")
    assert csv_path is None


@pytest.mark.asyncio
async def test_extract_table_html_returns_content():
    extractor = TableExtractor(output_dir="/tmp/test")

    mock_table = MagicMock()
    mock_table.count = AsyncMock(return_value=1)
    mock_table.is_visible = AsyncMock(return_value=True)
    mock_table.inner_html = AsyncMock(return_value="<tr><td>Test</td></tr>")

    mock_root = MagicMock()
    mock_root.locator.return_value.first = mock_table

    html = await extractor.extract_table_html(mock_root)

    assert html is not None
    assert "<tr>" in html
    assert "Test" in html


@pytest.mark.asyncio
async def test_extract_table_data_parses_rows():
    extractor = TableExtractor(output_dir="/tmp/test")

    mock_cell1 = MagicMock()
    mock_cell1.inner_text = AsyncMock(return_value="Cell1")
    mock_cell2 = MagicMock()
    mock_cell2.inner_text = AsyncMock(return_value="Cell2")

    mock_cells = MagicMock()
    mock_cells.count = AsyncMock(return_value=2)
    mock_cells.nth = MagicMock(side_effect=[mock_cell1, mock_cell2])

    mock_row = MagicMock()
    mock_row.locator.return_value = mock_cells

    cells = await extractor._extract_row_cells(mock_row, "td")

    assert cells == ["Cell1", "Cell2"]


@pytest.mark.asyncio
async def test_extract_and_save_returns_result(tmp_path: Path):
    extractor = TableExtractor(output_dir=tmp_path)

    async def mock_extract_html(root):
        return "<table><tr><td>Test</td></tr></table>"

    async def mock_extract_data(root):
        return [["Organisation", "Received"], ["Northern Railway", "100"]]

    extractor.extract_table_html = mock_extract_html
    extractor.extract_table_data = mock_extract_data

    mock_root = MagicMock()
    result = await extractor.extract_and_save(mock_root, "report1")

    assert isinstance(result, ExtractionResult)
    assert result.success is True
    assert result.html is not None
    assert result.data is not None
    assert result.csv_path is not None
    assert result.row_count == 2
    assert result.validation_result is not None
    assert result.validation_result.valid is True


@pytest.mark.asyncio
async def test_extract_and_save_handles_no_table(tmp_path: Path):
    extractor = TableExtractor(output_dir=tmp_path)

    async def mock_extract_html(root):
        return None

    extractor.extract_table_html = mock_extract_html

    mock_root = MagicMock()
    result = await extractor.extract_and_save(mock_root, "report1")

    assert result.success is False
    assert result.error is not None


@pytest.mark.asyncio
async def test_save_as_csv_fixed_creates_file(tmp_path: Path):
    extractor = TableExtractor(output_dir=tmp_path)
    data = [
        ["Organisation", "Feedback Received", "% Feedback"],
        ["Northern Railway", "980", "12.5"],
        ["Central Railway", "550", "7.0"],
    ]

    csv_path = await extractor.save_as_csv_fixed(
        data,
        report_slug="report1",
        filename="report1_feedback_zone_raw.csv",
    )

    assert csv_path is not None
    assert csv_path.exists()
    assert csv_path.name == "report1_feedback_zone_raw.csv"
    content = csv_path.read_text(encoding="utf-8-sig")
    assert "Organisation" in content
    assert "Northern Railway" in content


@pytest.mark.asyncio
async def test_save_as_csv_fixed_overwrites_existing(tmp_path: Path):
    extractor = TableExtractor(output_dir=tmp_path)

    report_dir = tmp_path / "report1"
    report_dir.mkdir(parents=True, exist_ok=True)
    existing = report_dir / "report1_feedback_zone_raw.csv"
    existing.write_text("old content", encoding="utf-8")

    data = [["Header"], ["NewData"]]
    csv_path = await extractor.save_as_csv_fixed(
        data,
        report_slug="report1",
        filename="report1_feedback_zone_raw.csv",
    )

    assert csv_path is not None
    content = csv_path.read_text(encoding="utf-8-sig")
    assert "NewData" in content
    assert "old content" not in content


@pytest.mark.asyncio
async def test_save_as_csv_fixed_returns_none_for_empty_data(tmp_path: Path):
    extractor = TableExtractor(output_dir=tmp_path)
    csv_path = await extractor.save_as_csv_fixed(
        [],
        report_slug="report1",
        filename="report1_feedback_zone_raw.csv",
    )
    assert csv_path is None


def test_headers_match_required_feedback_zone():
    from app.automation.table_extractor import FEEDBACK_ZONE_REQUIRED_HEADERS, TableExtractor

    headers = [
        "S.No.",
        "Organisation",
        "Feedback Received",
        "% Feedback",
        "Excellent",
        "Satisfactory",
        "Unsatisfactory",
        "% Unsatisfactory",
    ]
    assert TableExtractor()._headers_match_required(headers, FEEDBACK_ZONE_REQUIRED_HEADERS)


def test_skips_department_wise_headers():
    from app.automation.table_extractor import TableExtractor

    dept_headers = ["S.No.", "Department", "Received", "% Share"]
    assert TableExtractor._looks_like_department_wise(dept_headers) is True

    feedback_headers = [
        "Organisation",
        "Feedback Received",
        "% Feedback",
        "Excellent",
        "Satisfactory",
        "Unsatisfactory",
        "% Unsatisfactory",
    ]
    assert TableExtractor._looks_like_department_wise(feedback_headers) is False


@pytest.mark.asyncio
async def test_extract_table_data_by_headers_selects_feedback_zone():
    from app.automation.table_extractor import FEEDBACK_ZONE_REQUIRED_HEADERS, TableExtractor

    extractor = TableExtractor(output_dir="/tmp/test")

    dept_rows = [["S.No.", "Department", "Received"], ["1", "Commercial", "10"]]
    feedback_rows = [
        [
            "Organisation",
            "Feedback Received",
            "% Feedback",
            "Excellent",
            "Satisfactory",
            "Unsatisfactory",
            "% Unsatisfactory",
        ],
        ["Northern Railway", "980", "12.5", "100", "800", "80", "8.2"],
    ]

    async def fake_extract(table):
        # First table department, second feedback — keyed by call order
        if not hasattr(fake_extract, "n"):
            fake_extract.n = 0
        fake_extract.n += 1
        return dept_rows if fake_extract.n == 1 else feedback_rows

    extractor._extract_rows_from_table = fake_extract  # type: ignore[method-assign]

    mock_table0 = MagicMock()
    mock_table0.is_visible = AsyncMock(return_value=True)
    mock_table1 = MagicMock()
    mock_table1.is_visible = AsyncMock(return_value=True)

    mock_tables = MagicMock()
    mock_tables.count = AsyncMock(return_value=2)
    mock_tables.nth = MagicMock(side_effect=[mock_table0, mock_table1])

    mock_root = MagicMock()
    mock_root.locator.return_value = mock_tables

    rows = await extractor.extract_table_data_by_headers(
        mock_root, FEEDBACK_ZONE_REQUIRED_HEADERS
    )
    assert rows[0][0] == "Organisation"
    assert "Feedback Received" in rows[0]


@pytest.mark.asyncio
async def test_missing_feedback_table_returns_empty():
    from app.automation.table_extractor import FEEDBACK_ZONE_REQUIRED_HEADERS, TableExtractor

    extractor = TableExtractor(output_dir="/tmp/test")

    async def fake_extract(table):
        return [["S.No.", "Department", "Received"], ["1", "Commercial", "10"]]

    extractor._extract_rows_from_table = fake_extract  # type: ignore[method-assign]

    mock_table = MagicMock()
    mock_table.is_visible = AsyncMock(return_value=True)
    mock_tables = MagicMock()
    mock_tables.count = AsyncMock(return_value=1)
    mock_tables.nth = MagicMock(return_value=mock_table)
    mock_root = MagicMock()
    mock_root.locator.return_value = mock_tables

    rows = await extractor.extract_table_data_by_headers(
        mock_root, FEEDBACK_ZONE_REQUIRED_HEADERS
    )
    assert rows == []
