"""Tests for CDP pause/resume and hardened PDF download."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.automation import cancellation as control
from app.automation.config import config
from app.automation.dependencies import get_automation_service
from app.automation.run_registry import (
    ArtifactPathError,
    create_cdp_run,
    ensure_cdp_profile,
    register_artifact,
    validate_artifact_file,
)
from app.domain.entities.user import User, UserRole
from app.features.auth.dependencies import require_admin, validate_csrf_token
from app.infrastructure.database.session import get_db_session
from app.main import app


@pytest.fixture
def admin_user() -> User:
    now = datetime.now(UTC)
    return User(
        id="test-admin",
        username="admin",
        email="admin@test.local",
        password_hash="hash",
        role=UserRole.ADMIN,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
async def api_client(admin_user: User, test_session: AsyncSession):
    async def override_admin() -> User:
        return admin_user

    def override_csrf() -> None:
        return None

    async def override_db():
        yield test_session

    app.dependency_overrides[get_automation_service] = lambda: AsyncMock()
    app.dependency_overrides[require_admin] = override_admin
    app.dependency_overrides[validate_csrf_token] = override_csrf
    app.dependency_overrides[get_db_session] = override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


def test_pdf_validate_rejects_archive(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "output_pdf_dir", str(tmp_path / "pdf"))
    monkeypatch.setattr(config, "output_excel_dir", str(tmp_path / "excel"))
    monkeypatch.setattr(config, "extracted_data_dir", str(tmp_path / "extracted"))
    monkeypatch.setattr(config, "pdf_archive_dir", str(tmp_path / "archive"))
    for name in ("pdf", "excel", "extracted", "archive"):
        (tmp_path / name).mkdir()

    archive_pdf = tmp_path / "archive" / "portal.pdf"
    archive_pdf.write_bytes(b"%PDF-1.4x")
    with pytest.raises(ArtifactPathError):
        validate_artifact_file(archive_pdf, file_type="pdf")


def test_pdf_validate_accepts_output_pdf(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "output_pdf_dir", str(tmp_path / "pdf"))
    monkeypatch.setattr(config, "output_excel_dir", str(tmp_path / "excel"))
    monkeypatch.setattr(config, "extracted_data_dir", str(tmp_path / "extracted"))
    monkeypatch.setattr(config, "pdf_archive_dir", str(tmp_path / "archive"))
    for name in ("pdf", "excel", "extracted", "archive"):
        (tmp_path / name).mkdir()

    good = tmp_path / "pdf" / "division" / "Rail_Madad.pdf"
    good.parent.mkdir(parents=True)
    good.write_bytes(b"%PDF-1.4 final")
    resolved = validate_artifact_file(good, file_type="pdf")
    assert resolved.suffix == ".pdf"
    assert resolved.read_bytes().startswith(b"%PDF-")


@pytest.mark.asyncio
async def test_artifact_pdf_download_rejects_non_output(
    tmp_path, monkeypatch, api_client, test_session: AsyncSession
):
    monkeypatch.setattr(config, "output_pdf_dir", str(tmp_path / "pdf"))
    monkeypatch.setattr(config, "output_excel_dir", str(tmp_path / "excel"))
    monkeypatch.setattr(config, "extracted_data_dir", str(tmp_path / "extracted"))
    monkeypatch.setattr(config, "pdf_archive_dir", str(tmp_path / "archive"))
    for name in ("pdf", "excel", "extracted", "archive"):
        (tmp_path / name).mkdir()

    await ensure_cdp_profile(test_session)
    run = await create_cdp_run(test_session)
    # Register a PDF under archive (would have been allowed before harden)
    bad = tmp_path / "archive" / "raw.pdf"
    bad.write_bytes(b"%PDF-1.4 raw")
    art = await register_artifact(
        test_session,
        run_id=run.id,
        report_slug="division",
        report_name="division",
        file_type="pdf",
        file_path=bad,
    )
    # register_artifact marks missing when validation fails
    assert art is not None
    assert art.status == "missing"

    resp = await api_client.get(f"/api/v1/automation/artifacts/{art.id}/download")
    assert resp.status_code in {400, 404}


@pytest.mark.asyncio
async def test_pause_resume_api(api_client, admin_user: User):
    mock_service = AsyncMock()
    mock_service.pause.return_value = {
        "success": True,
        "status": "pause_requested",
        "message": "Pause requested",
        "run_id": "run-p1",
    }
    mock_service.resume.return_value = {
        "success": True,
        "status": "running",
        "message": "Automation resumed",
        "run_id": "run-p1",
    }
    app.dependency_overrides[get_automation_service] = lambda: mock_service

    pause = await api_client.post("/api/v1/automation/runs/run-p1/pause")
    assert pause.status_code == 200
    assert pause.json()["status"] == "pause_requested"
    mock_service.pause.assert_awaited_once_with("run-p1", user_id=admin_user.id)

    resume = await api_client.post("/api/v1/automation/runs/run-p1/resume")
    assert resume.status_code == 200
    assert resume.json()["status"] == "running"
    mock_service.resume.assert_awaited_once_with("run-p1", user_id=admin_user.id)


@pytest.mark.asyncio
async def test_pause_blocks_until_resume():
    run_id = f"pause-{uuid4()}"
    control.clear_cancel(run_id)
    control.clear_pause(run_id)
    control.request_pause(run_id)
    assert control.is_pause_requested(run_id)

    async def _resume_later() -> None:
        await asyncio.sleep(0.1)
        control.clear_pause(run_id)

    task = asyncio.create_task(_resume_later())
    await asyncio.wait_for(control.wait_if_paused_async(run_id), timeout=2.0)
    await task
    assert not control.is_pause_requested(run_id)
    control.clear_cancel(run_id)
