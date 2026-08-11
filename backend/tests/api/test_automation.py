"""Unit tests for in-process automation API."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.automation.dependencies import get_automation_service
from app.automation.schemas import MultiReportResult, ReportResult
from app.domain.entities.user import User, UserRole
from app.features.auth.dependencies import require_admin, validate_csrf_token
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

    def override_csrf() -> None:
        return None

    app.dependency_overrides[get_automation_service] = lambda: AsyncMock()
    app.dependency_overrides[require_admin] = override_admin
    app.dependency_overrides[validate_csrf_token] = override_csrf

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_start_automation_success(api_client: AsyncClient):
    mock_service = AsyncMock()
    mock_service.start.return_value = MultiReportResult(
        success=True,
        connected=True,
        tab_found=True,
        reports=[
            ReportResult(
                slug="report1",
                status="success",
                excel_path="storage/output/excel/report1/test.xlsx",
                pdf_path="storage/output/pdf/report1/test.pdf",
            )
        ],
    )
    app.dependency_overrides[get_automation_service] = lambda: mock_service

    response = await api_client.post("/api/v1/automation/start")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["connected"] is True
    assert payload["tab_found"] is True
    assert payload["reports"][0]["slug"] == "report1"
    assert payload["reports"][0]["status"] == "success"
    assert payload["error"] is None
    mock_service.start.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_automation_returns_connect_failure_in_body(api_client: AsyncClient):
    mock_service = AsyncMock()
    mock_service.start.return_value = MultiReportResult(
        success=False,
        connected=False,
        tab_found=False,
        error="Cannot connect to Chromium",
    )
    app.dependency_overrides[get_automation_service] = lambda: mock_service

    response = await api_client.post("/api/v1/automation/start")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["connected"] is False
    assert data["error"] == "Cannot connect to Chromium"


@pytest.mark.asyncio
async def test_start_automation_returns_500_on_unexpected_failure(api_client: AsyncClient):
    mock_service = AsyncMock()
    mock_service.start.side_effect = RuntimeError("boom")
    app.dependency_overrides[get_automation_service] = lambda: mock_service

    response = await api_client.post("/api/v1/automation/start")

    assert response.status_code == 500
