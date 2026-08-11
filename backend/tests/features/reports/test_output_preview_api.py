"""Tests for reactive output preview API."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app.domain.entities.user import User, UserRole
from app.features.auth.dependencies import require_officer_or_admin, validate_csrf_token
from app.main import app


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
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_output_preview_rejects_empty_selection(api_client):
    response = await api_client.post(
        "/reports/report1/output-preview",
        json={"selected_column_ids": [], "column_order": []},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_output_preview_rejects_invalid_column_id(api_client):
    response = await api_client.post(
        "/reports/report1/output-preview",
        json={
            "selected_column_ids": ["serialNo"],
            "column_order": ["serialNo"],
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_output_preview_no_data_message(api_client, monkeypatch):
    async def _no_paths(_slug: str):
        return None

    monkeypatch.setattr(
        "app.features.reports.preview_projection.resolve_source_paths",
        _no_paths,
    )
    response = await api_client.post(
        "/reports/report1/output-preview",
        json={
            "selected_column_ids": ["report1.source_a.received"],
            "column_order": ["report1.source_a.received"],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is False
    assert "No generated report data is available for preview." in payload["message"]


@pytest.mark.asyncio
async def test_scr_train_output_preview_rejects_empty_selection(api_client):
    response = await api_client.post(
        "/reports/scr-train/output-preview",
        json={"selected_column_ids": [], "column_order": []},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_scr_station_output_preview_no_data_message(api_client, monkeypatch):
    async def _no_scr_path(_slug: str):
        return None

    monkeypatch.setattr(
        "app.features.reports.preview_projection.resolve_scr_source_path",
        _no_scr_path,
    )
    response = await api_client.post(
        "/reports/scr-station/output-preview",
        json={
            "selected_column_ids": ["scr-station.complaint_ref_no"],
            "column_order": ["scr-station.complaint_ref_no"],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is False
    assert "No generated report data is available for preview." in payload["message"]


@pytest.mark.asyncio
async def test_train_no_output_preview_no_data_message(api_client, monkeypatch):
    async def _no_topn_path(_slug: str):
        return None

    monkeypatch.setattr(
        "app.features.reports.preview_projection.resolve_topn_dataset",
        _no_topn_path,
    )
    response = await api_client.post(
        "/reports/train-no/output-preview",
        json={
            "selected_column_ids": ["train-no.train_name", "train-no.received"],
            "column_order": ["train-no.train_name", "train-no.received"],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is False


@pytest.mark.asyncio
async def test_types_output_preview_no_data_message(api_client, monkeypatch):
    async def _no_topn_path(_slug: str):
        return None

    monkeypatch.setattr(
        "app.features.reports.preview_projection.resolve_topn_dataset",
        _no_topn_path,
    )
    response = await api_client.post(
        "/reports/types/output-preview",
        json={
            "selected_column_ids": ["types.train_name", "types.received"],
            "column_order": ["types.train_name", "types.received"],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is False


@pytest.mark.asyncio
async def test_train_no_output_preview_rejects_cross_slug_ids(api_client):
    response = await api_client.post(
        "/reports/train-no/output-preview",
        json={
            "selected_column_ids": ["types.train_name"],
            "column_order": ["types.train_name"],
        },
    )
    assert response.status_code == 422
