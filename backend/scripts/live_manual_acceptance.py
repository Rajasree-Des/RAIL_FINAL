"""Live acceptance: generate each manual report with a unique 2-column selection."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.domain.entities.user import User, UserRole
from app.features.auth.dependencies import require_officer_or_admin, validate_csrf_token
from app.main import app

SLUGS = ["report1", "division", "train-no", "types", "scr-train", "scr-station"]
POLL_S = 5
TIMEOUT_S = 900


async def wait_terminal(client: AsyncClient, slug: str, run_id: str) -> dict:
    deadline = time.monotonic() + TIMEOUT_S
    last: dict = {}
    while time.monotonic() < deadline:
        resp = await client.get(
            f"/api/v1/reports/runs/{run_id}",
            params={"report_slug": slug},
        )
        last = resp.json()
        status = last.get("status")
        print(f"  poll {slug} {run_id[:8]} status={status}", flush=True)
        if status in {"Completed", "Failed"}:
            return last
        await asyncio.sleep(POLL_S)
    last["status"] = "Failed"
    last["error"] = last.get("error") or f"Timed out after {TIMEOUT_S}s"
    return last


async def main() -> int:
    officer = User(
        id="live-accept",
        username="live",
        email="live@test.local",
        password_hash="h",
        role=UserRole.OFFICER,
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    app.dependency_overrides[require_officer_or_admin] = lambda: officer
    app.dependency_overrides[validate_csrf_token] = lambda: None

    results: list[dict] = []
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=60.0) as client:
        for slug in SLUGS:
            print(f"\n=== {slug} ===", flush=True)
            cfg = await client.get(f"/api/v1/reports/{slug}/config")
            assert cfg.status_code == 200, cfg.text
            cols = cfg.json()["selected_column_ids"][:2]
            assert cols, f"no columns for {slug}"

            preview = await client.post(
                f"/api/v1/reports/{slug}/preview",
                json={"selected_column_ids": cols, "column_order": cols},
            )
            print(f"  config=200 preview={preview.status_code} cols={cols}", flush=True)

            gen = await client.post(
                f"/api/v1/reports/{slug}/generate",
                json={
                    "report_slug": slug,
                    "selected_column_ids": cols,
                    "column_order": cols,
                    "export_format": "xlsx",
                    "requested_formats": ["xlsx", "pdf"],
                    "configuration_source": "manual_snapshot",
                    "force_fresh_extraction": True,
                },
            )
            print(f"  generate={gen.status_code} body={gen.text[:300]}", flush=True)
            if gen.status_code != 200:
                results.append(
                    {
                        "slug": slug,
                        "status": "Failed",
                        "error": gen.text,
                        "http_status": gen.status_code,
                    }
                )
                continue

            run_id = gen.json()["run_id"]
            final = await wait_terminal(client, slug, run_id)
            entry = {
                "slug": slug,
                "run_id": run_id,
                "status": final.get("status"),
                "error": final.get("error"),
                "excel_download_url": final.get("excel_download_url") or final.get("download_url"),
                "pdf_download_url": final.get("pdf_download_url"),
                "pdf_preview_url": final.get("pdf_preview_url"),
                "selected_column_ids": cols,
            }
            results.append(entry)
            print(f"  FINAL {json.dumps(entry, indent=2)}", flush=True)

    out = ROOT / "storage" / "live_manual_acceptance.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWrote {out}", flush=True)

    failed = [r for r in results if r.get("status") != "Completed"]
    app.dependency_overrides.clear()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
