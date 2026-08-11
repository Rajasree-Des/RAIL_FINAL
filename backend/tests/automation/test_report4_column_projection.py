"""Report 4 shared column projection across sections."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from app.automation.processing.report4_processor import Report4Processor
from app.automation.report4_filters import COMPLAINT_TYPES_ORDERED, get_type_configs

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "report4"

SELECTED_FOUR = [
    "types.train_name",
    "types.train_no",
    "types.received",
    "types.pending",
]


def _write_index_and_type_csvs(base: Path) -> Path:
    index_path = base / "types_combined_index.csv"
    rows = []
    for type_config in get_type_configs():
        slug = type_config.name.lower().replace(" ", "_").replace("&", "and")
        csv_path = base / f"report4_{slug}_raw.csv"
        if type_config.name == "Security":
            csv_path.write_text(
                (FIXTURES_DIR / "security_raw.csv").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        else:
            csv_path.write_text(
                (FIXTURES_DIR / "security_raw.csv").read_text(encoding="utf-8").replace(
                    "Express Train A", f"{type_config.name} Train"
                ),
                encoding="utf-8",
            )
        rows.append(
            {
                "type_name": type_config.name,
                "csv_path": str(csv_path),
                "row_count": "10",
                "status": "success",
                "error": "",
            }
        )
    with index_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["type_name", "csv_path", "row_count", "status", "error"],
        )
        writer.writeheader()
        writer.writerows(rows)
    return index_path


def test_all_sections_share_selected_headers(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "app.automation.processing.report4_processor.config.output_excel_dir",
        str(tmp_path / "excel"),
    )
    monkeypatch.setattr(
        "app.automation.processing.report4_processor.config.output_pdf_dir",
        str(tmp_path / "pdf"),
    )
    index_path = _write_index_and_type_csvs(tmp_path)
    selection = {
        "selected_column_ids": SELECTED_FOUR,
        "column_order": SELECTED_FOUR,
        "configuration_source": "manual_snapshot",
    }
    result = Report4Processor().process(
        source_a_path=index_path,
        report_slug="types",
        column_selection=selection,
    )
    assert result.success is True, result.error
    assert result.output_columns == ["Train Name", "Train No.", "Received", "Pending"]
    sections, headers, keys, _ = Report4Processor.build_projected_sections(
        index_path,
        column_selection=selection,
    )
    assert len(sections) == len(COMPLAINT_TYPES_ORDERED)
    for section in sections:
        assert section.headers == headers


def test_sno_restarts_per_section(tmp_path: Path):
    index_path = _write_index_and_type_csvs(tmp_path)
    sections, _, _, _ = Report4Processor.build_projected_sections(
        index_path,
        column_selection={
            "selected_column_ids": ["types.sno", "types.train_name"],
            "column_order": ["types.sno", "types.train_name"],
        },
    )
    assert len(sections) == len(COMPLAINT_TYPES_ORDERED)
    for section in sections:
        if not section.rows:
            continue
        assert section.rows[0][0] == "1"
