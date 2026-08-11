"""API tests for CDP run stop endpoint."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.automation.dependencies import get_automation_service
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

    app.dependency_overrides[require_admin] = override_admin
    app.dependency_overrides[validate_csrf_token] = override_csrf

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_stop_run_calls_service_with_run_id(api_client: AsyncClient, admin_user: User):
    mock_service = AsyncMock()
    mock_service.stop.return_value = {
        "success": True,
        "status": "stopped",
        "message": "Automation stopped",
        "run_id": "run-123",
    }
    app.dependency_overrides[get_automation_service] = lambda: mock_service

    response = await api_client.post("/api/v1/automation/runs/run-123/stop")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["status"] == "stopped"
    assert payload["run_id"] == "run-123"
    mock_service.stop.assert_awaited_once_with("run-123", user_id=admin_user.id)


@pytest.mark.asyncio
async def test_stop_run_not_found(api_client: AsyncClient):
    mock_service = AsyncMock()
    mock_service.stop.return_value = {
        "success": False,
        "status": "not_found",
        "message": "Run not found",
        "run_id": "missing",
    }
    app.dependency_overrides[get_automation_service] = lambda: mock_service

    response = await api_client.post("/api/v1/automation/runs/missing/stop")

    assert response.status_code == 404
