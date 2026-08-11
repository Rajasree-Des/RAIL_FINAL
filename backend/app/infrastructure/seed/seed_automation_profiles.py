"""Seed default RailMadad automation profile."""

import json
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.encryption import encrypt_secret
from app.infrastructure.database.models import AutomationProfileModel

DEFAULT_REPORT_SEQUENCE = [
    {
        "name": "Daily Complaints",
        "report_path": "/reports/complaints",
        "filters": {},
    },
    {
        "name": "Division Summary",
        "report_path": "/reports/division",
        "filters": {"division": "SCR"},
    },
]


async def seed_automation_profiles(session: AsyncSession) -> None:
    result = await session.execute(select(AutomationProfileModel.id).limit(1))
    if result.scalar_one_or_none():
        return

    username = os.environ.get("RAILMADAD_USERNAME", "portal_user")
    password = os.environ.get("RAILMADAD_PASSWORD", "portal_password")
    portal_url = os.environ.get(
        "RAILMADAD_PORTAL_URL", "https://railmadad.indianrail.gov.in"
    )

    profile = AutomationProfileModel(
        name="RailMadad Daily Download",
        slug="railmadad-daily",
        portal_url=portal_url,
        username_encrypted=encrypt_secret(username),
        password_encrypted=encrypt_secret(password),
        download_folder="downloads/railmadad",
        browser="chromium",
        headless=True,
        timeout_ms=60000,
        retry_count=3,
        delay_seconds=5,
        report_sequence_json=json.dumps(DEFAULT_REPORT_SEQUENCE),
        is_enabled=True,
    )
    session.add(profile)
    await session.commit()
