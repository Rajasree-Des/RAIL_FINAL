"""Ingest existing division CSV and generate outputs."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.automation.processing.report2_processor import Report2Processor
from app.features.datasets.service import DatasetService
from app.infrastructure.database.session import SessionLocal


async def main() -> None:
    csv = ROOT / "storage/extracted/division/division_2026-07-11_17-50-40.csv"
    print("csv exists", csv.exists())
    if not csv.exists():
        return
    rows = sum(1 for _ in csv.open(encoding="utf-8-sig")) - 1
    print("rows", rows)
    async with SessionLocal() as session:
        svc = DatasetService(session)
        await svc.ensure_dataset_exists("division")
        await svc.ingest_file("division", file_path=csv, source_filename=csv.name)
        meta = await svc.get_metadata("division")
        print("ingested division row_count", meta.row_count)
    proc = Report2Processor()
    result = proc.process(source_a_path=csv, report_slug="division")
    print("processing", result.success, result.excel_path, result.pdf_path, result.error)


if __name__ == "__main__":
    asyncio.run(main())
