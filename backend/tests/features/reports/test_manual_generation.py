"""Tests for manual report generation API."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.entities.user import User, UserRole
from app.features.auth.dependencies import require_officer_or_admin, validate_csrf_token
from app.features.reports.slug_map import PAGE_ID_TO_SLUG, resolve_manual_slug
from app.features.reports.status import extraction_success, map_manual_status
from app.automation.schemas import ReportResult
from app.main import app


@pytest.fixture(autouse=True)
def _clear_automation_lock_after_test():
    from app.automation.automation_lock import reset_automation_lock_for_tests

    yield
    reset_automation_lock_for_tests()


@pytest.fixture
def officer_user() -> User:
    now = datetime.now(UTC)
    return User(
        id="test-officer",
        username="officer",
        email="officer@test.local",
        password_hash="hash",
        role=UserRole.OFFICER,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
async def api_client(officer_user: User):
    async def override_user() -> User:
        return officer_user

    def override_csrf() -> None:
        return None

    app.dependency_overrides[require_officer_or_admin] = override_user
    app.dependency_overrides[validate_csrf_token] = override_csrf

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("page_id", "expected"),
    [
        ("merging", "report1"),
        ("zone", "report1"),
        ("division", "division"),
        ("train-no", "train-no"),
        ("types", "types"),
        ("scr-train", "scr-train"),
        ("scr-station", "scr-station"),
    ],
)
def test_page_id_maps_to_canonical_slug(page_id: str, expected: str):
    assert resolve_manual_slug(page_id) == expected
    assert PAGE_ID_TO_SLUG[page_id] == expected


def test_extraction_success_from_source_rows():
    report = ReportResult(slug="report1", status="partial_success", source_row_count=12)
    assert extraction_success(report) is True


def test_map_manual_status_completed_requires_artifact():
    report = ReportResult(
        slug="report1",
        status="success",
        source_row_count=10,
        ingestion_success=True,
        processing_success=True,
    )
    assert map_manual_status(run_status="completed", report=report, artifact_ready=True) == "Completed"
    assert map_manual_status(run_status="completed", report=report, artifact_ready=False) == (
        "Generating Excel/PDF"
    )


@pytest.mark.asyncio
async def test_generate_invokes_manual_automation(api_client: AsyncClient):
    with patch("app.features.reports.service.AutomationService") as mock_cls:
        mock_service = AsyncMock()
        mock_service.start_manual_async.return_value = ("run-123", "running")
        mock_cls.return_value = mock_service

        response = await api_client.post(
            "/api/v1/reports/report1/generate",
            json={
                "date_from": "2026-07-25",
                "date_to": "2026-07-26",
                "selected_column_ids": [
                    "report1.source_a.organisation",
                    "report1.source_a.received",
                ],
                "column_order": [
                    "report1.source_a.organisation",
                    "report1.source_a.received",
                ],
                "export_format": "xlsx",
                "configuration_source": "manual_snapshot",
                "config_overrides": {"division": "all"},
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "run-123"
    assert payload["report_slug"] == "report1"
    assert payload["status"] == "Extracting"
    mock_service.start_manual_async.assert_awaited_once()
    call_kwargs = mock_service.start_manual_async.await_args.kwargs
    assert call_kwargs["report_slugs"] == ["report1"]
    assert call_kwargs["manual_config"]["export_format"] == "xlsx"
    assert call_kwargs["manual_config"]["configuration_source"] == "manual_snapshot"
    assert call_kwargs["manual_config"]["selected_column_ids"] == [
        "report1.source_a.organisation",
        "report1.source_a.received",
    ]
    assert "report_date" in call_kwargs["manual_config"]
    assert call_kwargs["manual_config"]["date_from"] == "2026-07-25"
    assert call_kwargs["manual_config"]["date_to"] == "2026-07-26"


@pytest.mark.asyncio
async def test_generate_rejects_unknown_slug(api_client: AsyncClient):
    response = await api_client.post(
        "/api/v1/reports/unknown-report/generate",
        json={
            "date_from": "2026-07-25",
            "date_to": "2026-07-26",
            "selected_column_ids": [],
            "column_order": [],
            "export_format": "pdf",
        },
    )
    assert response.status_code == 404
