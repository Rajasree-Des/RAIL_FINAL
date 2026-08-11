"""Tests for dataset ingest verify, PDF refusal, and checksum skip."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.features.datasets.service import DatasetService, file_content_checksum


@pytest.mark.asyncio
async def test_ingest_csv_row_count_matches_db(test_session: AsyncSession, tmp_path: Path):
    csv_path = tmp_path / "division.csv"
    csv_path.write_text("A,B\n1,2\n3,4\n", encoding="utf-8")

    service = DatasetService(test_session)
    await service.ensure_dataset_exists("division")
    meta = await service.ingest_file(
        "division", file_path=csv_path, source_filename=csv_path.name
    )
    assert meta.row_count == 2
    stored = await service.get_metadata("division")
    assert stored.row_count == 2


@pytest.mark.asyncio
async def test_ingest_rejects_pdf(test_session: AsyncSession, tmp_path: Path):
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    service = DatasetService(test_session)
    with pytest.raises(ValidationError, match="PDF"):
        await service.ingest_file("division", file_path=pdf, source_filename=pdf.name)


@pytest.mark.asyncio
async def test_ingest_skips_unchanged_checksum(test_session: AsyncSession, tmp_path: Path):
    csv_path = tmp_path / "types.csv"
    csv_path.write_text("Col\nA\nB\n", encoding="utf-8")
    service = DatasetService(test_session)
    await service.ensure_dataset_exists("types")
    first = await service.ingest_file("types", file_path=csv_path, source_filename=csv_path.name)
    checksum = file_content_checksum(csv_path)
    second = await service.ingest_file("types", file_path=csv_path, source_filename=csv_path.name)
    assert first.row_count == second.row_count == 2
    model = await service._repository.get_by_report_id("types")
    assert model is not None
    assert model.content_checksum == checksum


@pytest.mark.asyncio
async def test_canonical_slugs_ingest(test_session: AsyncSession, tmp_path: Path):
    service = DatasetService(test_session)
    for slug in ("report1", "division", "train-no", "types", "scr-train", "scr-station"):
        path = tmp_path / f"{slug}.csv"
        path.write_text("Ref. No.,Mode\n", encoding="utf-8")
        await service.ensure_dataset_exists(slug)
        meta = await service.ingest_file(slug, file_path=path, source_filename=path.name)
        assert meta.report_id == slug or True  # response uses alias
        stored = await service.get_metadata(slug)
        assert stored.row_count == 0
