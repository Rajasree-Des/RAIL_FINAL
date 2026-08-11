"""Dual Excel/PDF artifact exposure for manual Report 1 and Report 2 runs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.automation.config import config
from app.automation.dependencies import get_automation_service
from app.automation.run_registry import register_artifact
from app.domain.entities.user import User, UserRole
from app.features.auth.dependencies import (
    get_current_active_user,
    require_admin,
    require_officer_or_admin,
    validate_csrf_token,
)
from app.features.reports.service import (
    ManualReportService,
    _artifact_is_ready,
    _artifacts_for_slug,
)
from app.infrastructure.database.models import AutomationArtifactModel, AutomationRunModel
from app.infrastructure.database.session import get_db_session
from app.main import app
from unittest.mock import AsyncMock


def _make_manual_run(
    *,
    slug: str,
    run_id: str,
    processing_success: bool = True,
    excel_path: str | None = "/tmp/out.xlsx",
    pdf_path: str | None = "/tmp/out.pdf",
    export_format: str = "xlsx",
) -> AutomationRunModel:
    manual_config = {
        "report_slug": slug,
        "export_format": export_format,
        "selected_column_ids": [f"{slug}.source_a.received"],
        "column_order": [f"{slug}.source_a.received"],
        "report_date": "16-07-2026",
        "configuration_source": "manual_snapshot",
    }
    report = {
        "slug": slug,
        "status": "success" if processing_success else "failed",
        "processing_success": processing_success,
        "ingestion_success": True,
        "source_row_count": 10,
        "processed_row_count": 10,
        "row_counts": {"comprehensive": 10},
        "source_csv_path": "/tmp/source.csv",
        "excel_path": excel_path,
        "pdf_path": pdf_path,
        "visible_columns": ["Received"],
    }
    payload = {
        "manual_config": manual_config,
        "result": {
            "success": processing_success,
            "connected": True,
            "tab_found": True,
            "reports": [report],
        },
    }
    return AutomationRunModel(
        id=run_id,
        profile_id="test-profile",
        status="completed",
        trigger_type="manual_report",
        success_count=1 if processing_success else 0,
        failure_count=0 if processing_success else 1,
        result_json=json.dumps(payload),
        completed_at=datetime.now(UTC),
    )


def _matching_column_metadata(slug: str) -> str:
    payload = {
        "selected_column_ids": [f"{slug}.source_a.received"],
        "column_order": [f"{slug}.source_a.received"],
    }
    return json.dumps(payload)


@pytest.mark.asyncio
async def test_get_run_status_report1_returns_dual_artifacts(
    test_session: AsyncSession,
    tmp_path: Path,
):
    run_id = str(uuid4())
    slug = "report1"
    excel_path = tmp_path / "report1.xlsx"
    pdf_path = tmp_path / "report1.pdf"
    excel_path.write_bytes(b"PK\x03\x04excel")
    pdf_path.write_bytes(b"%PDF-1.4 processed")

    test_session.add(_make_manual_run(slug=slug, run_id=run_id))
    excel_id = str(uuid4())
    pdf_id = str(uuid4())
    test_session.add_all(
        [
            AutomationArtifactModel(
                id=excel_id,
                run_id=run_id,
                artifact_type="excel",
                file_path=str(excel_path),
                file_size_bytes=excel_path.stat().st_size,
                report_slug=slug,
                report_name=slug,
                status="ready",
                metadata_json=_matching_column_metadata(slug),
            ),
            AutomationArtifactModel(
                id=pdf_id,
                run_id=run_id,
                artifact_type="pdf",
                file_path=str(pdf_path),
                file_size_bytes=pdf_path.stat().st_size,
                report_slug=slug,
                report_name=slug,
                status="ready",
                metadata_json=_matching_column_metadata(slug),
            ),
        ]
    )
    await test_session.commit()

    status = await ManualReportService().get_run_status(test_session, run_id)

    assert status.status == "Completed"
    assert status.excel_artifact_id == excel_id
    assert status.pdf_artifact_id == pdf_id
    assert status.excel_download_url == f"/api/v1/automation/artifacts/{excel_id}/download"
    assert status.pdf_download_url == f"/api/v1/automation/artifacts/{pdf_id}/download"
    assert status.pdf_preview_url == f"/api/v1/automation/artifacts/{pdf_id}/preview"
    assert status.artifact_id == excel_id
    assert status.download_url == status.excel_download_url


@pytest.mark.asyncio
async def test_get_run_status_division_returns_dual_artifacts(
    test_session: AsyncSession,
    tmp_path: Path,
):
    run_id = str(uuid4())
    slug = "division"
    excel_path = tmp_path / "division.xlsx"
    pdf_path = tmp_path / "division.pdf"
    excel_path.write_bytes(b"PK\x03\x04excel")
    pdf_path.write_bytes(b"%PDF-1.4 processed")

    test_session.add(_make_manual_run(slug=slug, run_id=run_id))
    excel_id = str(uuid4())
    pdf_id = str(uuid4())
    test_session.add_all(
        [
            AutomationArtifactModel(
                id=excel_id,
                run_id=run_id,
                artifact_type="excel",
                file_path=str(excel_path),
                file_size_bytes=excel_path.stat().st_size,
                report_slug=slug,
                report_name=slug,
                status="ready",
                metadata_json=_matching_column_metadata(slug),
            ),
            AutomationArtifactModel(
                id=pdf_id,
                run_id=run_id,
                artifact_type="pdf",
                file_path=str(pdf_path),
                file_size_bytes=pdf_path.stat().st_size,
                report_slug=slug,
                report_name=slug,
                status="ready",
                metadata_json=_matching_column_metadata(slug),
            ),
        ]
    )
    await test_session.commit()

    status = await ManualReportService().get_run_status(test_session, run_id, expected_slug=slug)

    assert status.status == "Completed"
    assert status.excel_artifact_id == excel_id
    assert status.pdf_artifact_id == pdf_id


@pytest.mark.asyncio
async def test_get_run_status_not_completed_when_artifact_metadata_mismatch(
    test_session: AsyncSession,
    tmp_path: Path,
):
    run_id = str(uuid4())
    slug = "report1"
    excel_path = tmp_path / "report1.xlsx"
    pdf_path = tmp_path / "report1.pdf"
    excel_path.write_bytes(b"PK\x03\x04excel")
    pdf_path.write_bytes(b"%PDF-1.4 processed")

    test_session.add(_make_manual_run(slug=slug, run_id=run_id))
    excel_id = str(uuid4())
    pdf_id = str(uuid4())
    test_session.add_all(
        [
            AutomationArtifactModel(
                id=excel_id,
                run_id=run_id,
                artifact_type="excel",
                file_path=str(excel_path),
                file_size_bytes=excel_path.stat().st_size,
                report_slug=slug,
                report_name=slug,
                status="ready",
                metadata_json=_matching_column_metadata(slug),
            ),
            AutomationArtifactModel(
                id=pdf_id,
                run_id=run_id,
                artifact_type="pdf",
                file_path=str(pdf_path),
                file_size_bytes=pdf_path.stat().st_size,
                report_slug=slug,
                report_name=slug,
                status="ready",
                metadata_json=json.dumps(
                    {
                        "selected_column_ids": ["report1.source_a.closed"],
                        "column_order": ["report1.source_a.closed"],
                    }
                ),
            ),
        ]
    )
    await test_session.commit()

    status = await ManualReportService().get_run_status(test_session, run_id)

    assert status.status != "Completed"
    assert "mismatch" in (status.error or "").lower()


@pytest.mark.asyncio
async def test_get_run_status_not_completed_when_pdf_missing_for_report1(
    test_session: AsyncSession,
    tmp_path: Path,
):
    run_id = str(uuid4())
    slug = "report1"
    excel_path = tmp_path / "report1.xlsx"
    excel_path.write_bytes(b"PK\x03\x04excel")

    test_session.add(_make_manual_run(slug=slug, run_id=run_id))
    excel_id = str(uuid4())
    test_session.add(
        AutomationArtifactModel(
            id=excel_id,
            run_id=run_id,
            artifact_type="excel",
            file_path=str(excel_path),
            file_size_bytes=excel_path.stat().st_size,
            report_slug=slug,
            report_name=slug,
            status="ready",
        )
    )
    await test_session.commit()

    status = await ManualReportService().get_run_status(test_session, run_id)

    assert status.status != "Completed"
    assert status.excel_artifact_id == excel_id
    assert status.pdf_artifact_id is None


@pytest.mark.asyncio
async def test_get_run_status_train_no_single_artifact_unchanged(
    test_session: AsyncSession,
    tmp_path: Path,
):
    run_id = str(uuid4())
    slug = "train-no"
    pdf_path = tmp_path / "train.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    test_session.add(_make_manual_run(slug=slug, run_id=run_id, export_format="pdf"))
    pdf_id = str(uuid4())
    test_session.add(
        AutomationArtifactModel(
            id=pdf_id,
            run_id=run_id,
            artifact_type="pdf",
            file_path=str(pdf_path),
            file_size_bytes=pdf_path.stat().st_size,
            report_slug=slug,
            report_name=slug,
            status="ready",
        )
    )
    await test_session.commit()

    status = await ManualReportService().get_run_status(test_session, run_id)

    assert status.artifact_id == pdf_id
    assert status.excel_artifact_id is None
    assert status.pdf_artifact_id is None


def test_artifacts_for_slug_returns_ready_types():
    class _Art:
        def __init__(self, artifact_type: str, slug: str, size: int):
            self.artifact_type = artifact_type
            self.report_slug = slug
            self.status = "ready"
            self.file_size_bytes = size

    found = _artifacts_for_slug(
        [
            _Art("excel", "report1", 100),
            _Art("pdf", "report1", 200),
            _Art("pdf", "division", 50),
        ],
        slug="report1",
    )
    assert "excel" in found
    assert "pdf" in found


def test_artifact_is_ready_requires_size():
    class _Art:
        status = "ready"
        file_size_bytes = 0

    assert _artifact_is_ready(_Art()) is False


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
    async def override_user() -> User:
        return admin_user

    def override_csrf() -> None:
        return None

    async def override_db():
        yield test_session

    app.dependency_overrides[get_automation_service] = lambda: AsyncMock()
    app.dependency_overrides[get_current_active_user] = override_user
    app.dependency_overrides[require_admin] = override_user
    app.dependency_overrides[require_officer_or_admin] = override_user
    app.dependency_overrides[validate_csrf_token] = override_csrf
    app.dependency_overrides[get_db_session] = override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_dual_artifact_download_content_types(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    api_client: AsyncClient,
    test_session: AsyncSession,
):
    pdf_dir = tmp_path / "pdf" / "report1"
    excel_dir = tmp_path / "excel" / "report1"
    pdf_dir.mkdir(parents=True)
    excel_dir.mkdir(parents=True)
    pdf_path = pdf_dir / "report1.pdf"
    excel_path = excel_dir / "report1.xlsx"
    pdf_path.write_bytes(b"%PDF-1.4 processed")
    excel_path.write_bytes(b"PK\x03\x04excel")

    monkeypatch.setattr(config, "output_pdf_dir", str(tmp_path / "pdf"))
    monkeypatch.setattr(config, "output_excel_dir", str(tmp_path / "excel"))
    monkeypatch.setattr(config, "extracted_data_dir", str(tmp_path / "extracted"))
    monkeypatch.setattr(config, "pdf_archive_dir", str(tmp_path / "archive"))
    (tmp_path / "extracted").mkdir(exist_ok=True)
    (tmp_path / "archive").mkdir(exist_ok=True)

    run_id = str(uuid4())
    test_session.add(_make_manual_run(slug="report1", run_id=run_id))
    await test_session.commit()

    pdf_art = await register_artifact(
        test_session,
        run_id=run_id,
        report_slug="report1",
        report_name="report1",
        file_type="pdf",
        file_path=pdf_path,
    )
    excel_art = await register_artifact(
        test_session,
        run_id=run_id,
        report_slug="report1",
        report_name="report1",
        file_type="excel",
        file_path=excel_path,
    )

    pdf_dl = await api_client.get(f"/api/v1/automation/artifacts/{pdf_art.id}/download")
    assert pdf_dl.status_code == 200
    assert pdf_dl.content.startswith(b"%PDF")
    assert "pdf" in pdf_dl.headers.get("content-type", "").lower()

    excel_dl = await api_client.get(
        f"/api/v1/automation/artifacts/{excel_art.id}/download"
    )
    assert excel_dl.status_code == 200
    ct = excel_dl.headers.get("content-type", "").lower()
    assert "spreadsheet" in ct or "excel" in ct or "octet-stream" in ct
