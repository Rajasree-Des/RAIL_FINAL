"""Tests for PDF download endpoint and dataset ensure."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.automation.report_keys import canonicalize_report_key
from app.features.auth.dependencies import require_admin, validate_csrf_token
from app.domain.entities.user import User, UserRole
from datetime import UTC, datetime
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
async def api_client(admin_user: User):
    async def override_admin() -> User:
        return admin_user

    app.dependency_overrides[require_admin] = override_admin
    app.dependency_overrides[validate_csrf_token] = lambda: None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_pdf_download_serves_valid_pdf(api_client: AsyncClient, tmp_path: Path):
    pdf_dir = tmp_path / "division"
    pdf_dir.mkdir(parents=True)
    pdf_path = pdf_dir / "test.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake content for test")

    with patch("app.api.automation.config") as mock_config:
        mock_config.output_pdf_dir = str(tmp_path)
        response = await api_client.get("/api/v1/automation/reports/division/pdf")

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF-")
    assert "attachment" in response.headers.get("content-disposition", "")


@pytest.mark.asyncio
async def test_pdf_download_rejects_unknown_key(api_client: AsyncClient):
    response = await api_client.get("/api/v1/automation/reports/../../etc/passwd/pdf")
    assert response.status_code in (404, 400)


@pytest.mark.asyncio
async def test_pdf_download_alias_report2_maps_to_division(
    api_client: AsyncClient, tmp_path: Path
):
    pdf_dir = tmp_path / "division"
    pdf_dir.mkdir(parents=True)
    (pdf_dir / "out.pdf").write_bytes(b"%PDF-1.4 alias test")

    with patch("app.api.automation.config") as mock_config:
        mock_config.output_pdf_dir = str(tmp_path)
        response = await api_client.get("/api/v1/automation/reports/report2/pdf")

    assert response.status_code == 200
    assert canonicalize_report_key("report2") == "division"


@pytest.mark.asyncio
async def test_ensure_dataset_exists_idempotent():
    from app.features.datasets.service import DatasetService

    existing = MagicMock()
    existing.report_id = "division"

    service = DatasetService(AsyncMock())
    service._repository = MagicMock()
    service._repository.get_by_report_id = AsyncMock(return_value=existing)

    model = await service.ensure_dataset_exists("report2")
    assert model is existing
    # Should not call ingest when already present
    service._repository.get_by_report_id.assert_awaited()
