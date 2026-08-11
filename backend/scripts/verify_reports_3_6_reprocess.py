"""Live reprocess verification for Reports 3–6 using latest extracted CSVs."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.automation.processing.service import process_report
from app.features.datasets.service import DatasetService

SLUGS = ("train-no", "types", "scr-train", "scr-station")
RUN_ID = "844209d4-9f9c-4bc4-9ef9-b8a4c64a857c"


def _report_paths(db_path: Path) -> dict[str, dict]:
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT result_json FROM automation_runs WHERE id=?",
        (RUN_ID,),
    ).fetchone()
    conn.close()
    if not row or not row[0]:
        return {}
    data = json.loads(row[0])
    reports = data.get("reports") or []
    return {str(r["slug"]): r for r in reports if isinstance(r, dict) and r.get("slug")}


async def _reprocess_slug(session: AsyncSession, slug: str, csv_path: Path) -> None:
    service = DatasetService(session)
    await service.ensure_dataset_exists(slug)
    meta = await service.ingest_file(slug, file_path=csv_path, source_filename=csv_path.name)
    result = await process_report(slug, True)
    print(f"--- {slug} ---")
    print(f"  ingested_rows={meta.row_count}")
    print(f"  processing_success={result.success}")
    print(f"  excel_path={result.excel_path}")
    print(f"  pdf_path={result.pdf_path}")
    if result.error:
        print(f"  error={result.error}")
    if result.success:
        assert result.excel_path and Path(result.excel_path).is_file()
        assert result.pdf_path and Path(result.pdf_path).read_bytes()[:5] == b"%PDF-"


async def main() -> None:
    db_path = Path(__file__).resolve().parents[1] / "railway.db"
    reports = _report_paths(db_path)
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    paths = {
        "train-no": Path(
            reports.get("train-no", {}).get("source_csv_path")
            or "storage/extracted/train-no/train-no_2026-07-16_22-23-35_1.csv"
        ),
        "types": Path(
            f"storage/extracted/types/{RUN_ID}/types_combined_index.csv"
        ),
        "scr-train": Path("storage/extracted/scr-train/scr-train_complaints_raw.csv"),
        "scr-station": Path("storage/extracted/scr-station/scr-station_complaints_raw.csv"),
    }

    async with sf() as session:
        for slug in SLUGS:
            csv_path = paths[slug]
            if not csv_path.is_file():
                print(f"SKIP {slug}: missing {csv_path}")
                continue
            await _reprocess_slug(session, slug, csv_path)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
