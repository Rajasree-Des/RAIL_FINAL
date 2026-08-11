"""Live acceptance for dashboard summary + SSE activity stream."""

from __future__ import annotations

import asyncio
import json
import sys
import uuid

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
ADMIN_USER = "admin"
ADMIN_PASS = "Admin@123456"


async def login(client: httpx.AsyncClient, username: str, password: str) -> str:
    resp = await client.post(
        f"{BASE}/auth/login", json={"username": username, "password": password}
    )
    resp.raise_for_status()
    return resp.json()["csrf_token"]


async def listen_sse(client: httpx.AsyncClient, events: list[dict], stop: asyncio.Event) -> None:
    try:
        async with client.stream(
            "GET", f"{BASE}/activity/stream", timeout=httpx.Timeout(5, read=40)
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    events.append(json.loads(line[len("data: "):]))
                if stop.is_set():
                    break
    except (httpx.ReadTimeout, httpx.ReadError):
        pass


async def main() -> int:
    ok = True
    async with httpx.AsyncClient() as admin:
        csrf = await login(admin, ADMIN_USER, ADMIN_PASS)
        print("[1] admin login ok")

        summary = (await admin.get(f"{BASE}/dashboard/summary")).json()
        print(
            "[2] summary:",
            json.dumps(
                {
                    k: summary[k]
                    for k in (
                        "current_status",
                        "last_run_status",
                        "last_generated_at",
                        "successful_report_count",
                        "generated_report_count",
                        "total_enabled_reports",
                        "estimated_duration_seconds",
                    )
                },
                indent=2,
            ),
        )
        print("    reports:", [(r["slug"], r["status"]) for r in summary["reports"]])
        assert summary["total_enabled_reports"] > 0
        assert isinstance(summary["recent_activity"], list)

        # SSE: subscribe, then trigger CONFIG_UPDATED via template create
        events: list[dict] = []
        stop = asyncio.Event()
        listener = asyncio.create_task(listen_sse(admin, events, stop))
        await asyncio.sleep(1.0)

        marker = uuid.uuid4().hex[:8]
        resp = await admin.post(
            f"{BASE}/admin/templates",
            json={"name": f"Live Verify {marker}", "slug": f"live-verify-{marker}"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 201, resp.text
        template_id = resp.json()["id"]
        print("[3] template created (CONFIG_UPDATED should stream)")

        for _ in range(20):
            if any(e.get("action") == "CONFIG_UPDATED" for e in events):
                break
            await asyncio.sleep(0.5)
        got_sse = any(e.get("action") == "CONFIG_UPDATED" for e in events)
        print(f"[4] SSE delivered CONFIG_UPDATED without refresh: {got_sse}")
        ok &= got_sse

        # cleanup the throwaway template
        del_resp = await admin.delete(
            f"{BASE}/admin/templates/{template_id}",
            headers={"X-CSRF-Token": csrf},
        )
        assert del_resp.status_code == 200, del_resp.text

        stop.set()
        listener.cancel()

        # persistence: fresh request still returns the events from DB
        recent = (await admin.get(f"{BASE}/activity/recent?limit=10")).json()
        persisted = any(i["action"] == "CONFIG_UPDATED" for i in recent["items"])
        print(f"[5] events persisted across 'refresh' (fresh GET): {persisted}")
        ok &= persisted

    # cross-user isolation
    async with httpx.AsyncClient() as other:
        uname = f"verify_{uuid.uuid4().hex[:8]}"
        reg = await other.post(
            f"{BASE}/auth/register",
            json={
                "username": uname,
                "email": f"{uname}@example.com",
                "password": "VerifyPass123!",
            },
        )
        assert reg.status_code == 201, reg.text
        await login(other, uname, "VerifyPass123!")
        their = (await other.get(f"{BASE}/activity?limit=100")).json()
        foreign = [
            i for i in their["items"] if i["action"] in {"CONFIG_UPDATED", "PDF_GENERATED"}
        ]
        isolated = len(foreign) == 0
        print(
            f"[6] second user sees {their['total']} own events, "
            f"0 admin events: {isolated}"
        )
        ok &= isolated

    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
