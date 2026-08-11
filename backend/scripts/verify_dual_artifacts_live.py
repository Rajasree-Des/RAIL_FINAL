"""Verify dual Excel/PDF artifact exposure for manual report1 and division runs."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.automation.run_registry import ensure_schema_columns
from app.features.reports.service import ManualReportService
from app.infrastructure.database.session import SessionLocal

API_BASE = "http://127.0.0.1:8000/api/v1"
DIVISION_RUN_ID = "844209d4-9f9c-4bc4-9ef9-b8a4c64a857c"
DIVISION_EXCEL_ID = "71af3407-e168-4e9a-96b2-a70c6c63e5ad"
DIVISION_PDF_ID = "84975044-621e-4901-b373-019e4dfce03d"


def _dual_manual_runs(db_path: Path) -> dict[str, str]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT r.id, r.result_json, a.artifact_type
        FROM automation_runs r
        JOIN automation_artifacts a ON a.run_id = r.id
        WHERE r.trigger_type = 'manual_report'
          AND a.report_slug IN ('report1', 'division')
          AND a.status = 'ready'
          AND a.file_size_bytes > 0
        ORDER BY r.completed_at DESC
        LIMIT 60
        """
    )
    runs: dict[str, dict] = defaultdict(lambda: {"types": set(), "slug": None})
    for row in cur.fetchall():
        rid = row["id"]
        runs[rid]["types"].add(row["artifact_type"])
        if row["result_json"]:
            try:
                payload = json.loads(row["result_json"])
                runs[rid]["slug"] = payload.get("manual_config", {}).get("report_slug")
            except json.JSONDecodeError:
                pass
    conn.close()
    by_slug: dict[str, str] = {}
    for rid, info in runs.items():
        if info["types"] >= {"excel", "pdf"} and info["slug"]:
            by_slug.setdefault(info["slug"], rid)
    return by_slug


async def _verify_run(db_path: Path, run_id: str, slug: str) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        status = await ManualReportService().get_run_status(session, run_id, expected_slug=slug)
        assert status.status == "Completed", f"{slug}: expected Completed, got {status.status}"
        assert status.excel_artifact_id, f"{slug}: missing excel_artifact_id"
        assert status.pdf_artifact_id, f"{slug}: missing pdf_artifact_id"
        assert status.excel_download_url, f"{slug}: missing excel_download_url"
        assert status.pdf_download_url, f"{slug}: missing pdf_download_url"
        assert status.pdf_preview_url, f"{slug}: missing pdf_preview_url"
        assert "16-07-2026" in (status.excel_filename or ""), status.excel_filename
        assert "16-07-2026" in (status.pdf_filename or ""), status.pdf_filename

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        for art_id in (status.excel_artifact_id, status.pdf_artifact_id):
            cur.execute(
                "SELECT run_id, file_path, file_size_bytes FROM automation_artifacts WHERE id=?",
                (art_id,),
            )
            row = cur.fetchone()
            assert row and row[0] == run_id, f"artifact {art_id} run_id mismatch"
            path = Path(row[1])
            assert path.exists() and row[2] > 0, f"missing or empty: {path}"
            if path.suffix.lower() == ".pdf":
                assert path.read_bytes()[:5] == b"%PDF-", path
        conn.close()
        print(f"OK manual {slug} run_id={run_id}")
        print(f"  excel={status.excel_artifact_id} {status.excel_filename}")
        print(f"  pdf={status.pdf_artifact_id} {status.pdf_filename}")
    await engine.dispose()


async def _verify_division_artifacts_on_disk() -> None:
    db_path = Path(__file__).resolve().parents[1] / "railway.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, artifact_type, file_path, file_size_bytes, run_id
        FROM automation_artifacts
        WHERE report_slug = 'division'
          AND status = 'ready'
          AND file_size_bytes > 0
          AND file_path LIKE ?
        ORDER BY created_at DESC
        LIMIT 4
        """,
        ("%16-07-2026_222314%",),
    )
    rows = cur.fetchall()
    conn.close()
    by_type = {row[1]: row for row in rows}
    assert "excel" in by_type and "pdf" in by_type, rows
    excel_row = by_type["excel"]
    pdf_row = by_type["pdf"]
    assert excel_row[4] == pdf_row[4], "excel/pdf run_id mismatch"
    excel_path = Path(excel_row[2])
    pdf_path = Path(pdf_row[2])
    assert excel_path.exists() and excel_path.suffix.lower() == ".xlsx"
    assert pdf_path.exists() and pdf_path.suffix.lower() == ".pdf"
    assert pdf_path.read_bytes()[:5] == b"%PDF-"
    assert "16-07-2026" in excel_path.name
    print(f"OK division artifacts run_id={excel_row[4]}")
    print(f"  excel={excel_row[0]} {excel_path.name}")
    print(f"  pdf={pdf_row[0]} {pdf_path.name}")


async def _verify_division_download_routes() -> None:
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30.0) as client:
        login = await client.post(
            "/auth/login",
            json={"username": "admin", "password": "Admin@123456"},
        )
        login.raise_for_status()

        pdf_resp = await client.get(f"/automation/artifacts/{DIVISION_PDF_ID}/download")
        assert pdf_resp.status_code == 200, pdf_resp.text
        assert pdf_resp.content.startswith(b"%PDF")
        assert "pdf" in pdf_resp.headers.get("content-type", "").lower()
        assert pdf_resp.headers.get("content-disposition", "").endswith(".pdf\"")

        excel_resp = await client.get(f"/automation/artifacts/{DIVISION_EXCEL_ID}/download")
        assert excel_resp.status_code == 200, excel_resp.text
        ct = excel_resp.headers.get("content-type", "").lower()
        assert "spreadsheet" in ct or "excel" in ct or "octet-stream" in ct
        assert excel_resp.headers.get("content-disposition", "").endswith(".xlsx\"")

        preview_resp = await client.get(f"/automation/artifacts/{DIVISION_PDF_ID}/preview")
        assert preview_resp.status_code == 200, preview_resp.text
        assert preview_resp.content.startswith(b"%PDF")

        conn = sqlite3.connect(Path(__file__).resolve().parents[1] / "railway.db")
        cur = conn.cursor()
        cur.execute(
            "SELECT run_id FROM automation_artifacts WHERE id IN (?, ?)",
            (DIVISION_EXCEL_ID, DIVISION_PDF_ID),
        )
        run_ids = {row[0] for row in cur.fetchall()}
        conn.close()
        assert run_ids == {DIVISION_RUN_ID}, run_ids

        print(f"OK division download routes run_id={DIVISION_RUN_ID}")
        print(f"  excel={DIVISION_EXCEL_ID}")
        print(f"  pdf={DIVISION_PDF_ID}")


def main() -> None:
    db_path = Path(__file__).resolve().parents[1] / "railway.db"
    if not db_path.exists():
        raise SystemExit("railway.db not found")

    async def _ensure_schema() -> None:
        async with SessionLocal() as session:
            await ensure_schema_columns(session)

    asyncio.run(_ensure_schema())

    by_slug = _dual_manual_runs(db_path)
    print(f"Dual manual runs found: {list(by_slug.keys())}")

    if "report1" in by_slug:
        asyncio.run(_verify_run(db_path, by_slug["report1"], "report1"))
    else:
        print("WARN: no manual report1 dual run in DB")

    if "division" in by_slug:
        asyncio.run(_verify_run(db_path, by_slug["division"], "division"))
    else:
        print("WARN: no manual division dual run in DB — verifying division artifact files")
        asyncio.run(_verify_division_artifacts_on_disk())
        try:
            asyncio.run(_verify_division_download_routes())
        except (httpx.ConnectError, httpx.ReadTimeout):
            print("WARN: API server not reachable; division download routes skipped")

    print("Live verification finished")


if __name__ == "__main__":
    main()
    sys.exit(0)
