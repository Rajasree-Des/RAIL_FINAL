"""Live acceptance for the simplified Settings feature.

Checks: seed sync (4->3 setting categories), /settings/display, settings
update propagation, /system/info, /system/clear-cache, session timeout
in token expiry, and /auth/logout-all.
"""

from __future__ import annotations

import asyncio
import json
import sys

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
ADMIN_USER = "admin"
ADMIN_PASS = "Admin@123456"


async def main() -> int:
    ok = True
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{BASE}/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS}
        )
        resp.raise_for_status()
        login_data = resp.json()
        csrf = login_data["csrf_token"]
        headers = {"X-CSRF-Token": csrf}
        print(f"[1] admin login ok (expires_in={login_data['expires_in']}s)")

        # Seed sync: exactly 3 categories
        settings_resp = (await client.get(f"{BASE}/settings")).json()
        slugs = sorted(c["slug"] for c in settings_resp["categories"])
        print(f"[2] settings categories: {slugs} total={settings_resp['total']}")
        if slugs != ["account", "general", "notifications"]:
            print("    FAIL: unexpected categories")
            ok = False

        # Display endpoint
        display = (await client.get(f"{BASE}/settings/display")).json()
        print(f"[3] display: {json.dumps(display)}")

        # Update a setting and confirm display reflects it
        upd = await client.put(
            f"{BASE}/settings",
            json={"settings": [{"category": "general", "key": "time_format", "value": "24h"}]},
            headers=headers,
        )
        upd.raise_for_status()
        display2 = (await client.get(f"{BASE}/settings/display")).json()
        print(f"[4] after update time_format={display2['time_format']}")
        if display2["time_format"] != "24h":
            print("    FAIL: display did not reflect update")
            ok = False

        # Revert
        await client.put(
            f"{BASE}/settings",
            json={"settings": [{"category": "general", "key": "time_format", "value": "12h"}]},
            headers=headers,
        )

        # Session timeout: set 1h, then login again and check expires_in
        await client.put(
            f"{BASE}/settings",
            json={"settings": [{"category": "account", "key": "session_timeout", "value": "1h"}]},
            headers=headers,
        )
        async with httpx.AsyncClient(timeout=60) as second:
            second_login = await second.post(
                f"{BASE}/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS}
            )
            expires = second_login.json()["expires_in"]
            print(f"[5] login with session_timeout=1h -> expires_in={expires}s")
            if expires != 3600:
                print("    FAIL: expected 3600")
                ok = False
        await client.put(
            f"{BASE}/settings",
            json={"settings": [{"category": "account", "key": "session_timeout", "value": "30m"}]},
            headers=headers,
        )

        # System info
        info = (await client.get(f"{BASE}/system/info")).json()
        print(
            "[6] system info:",
            json.dumps(
                {
                    "backend": info["backend"]["ok"],
                    "database": info["database"]["ok"],
                    "db_type": info["database_type"],
                    "cdp": info["cdp"]["ok"],
                    "automation": info["automation_status"],
                    "version": info["app_version"],
                    "storage_bytes": info["storage_usage_bytes"],
                    "last_success": info["last_successful_run_at"],
                }
            ),
        )
        if not (info["backend"]["ok"] and info["database"]["ok"]):
            print("    FAIL: backend/database should be ok")
            ok = False

        # Clear cache
        cleared = await client.post(f"{BASE}/system/clear-cache", headers=headers)
        cleared.raise_for_status()
        print(f"[7] clear-cache: {cleared.json()}")

        # Logout-all revokes refresh: refresh should fail afterwards
        out = await client.post(f"{BASE}/auth/logout-all", headers=headers)
        print(f"[8] logout-all status={out.status_code}")
        if out.status_code != 204:
            ok = False
        refresh = await client.post(f"{BASE}/auth/refresh")
        print(f"[9] refresh after logout-all -> {refresh.status_code} (expect 401)")
        if refresh.status_code != 401:
            ok = False

    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

