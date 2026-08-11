"""Tests for manual report configuration GET/PUT and shared dispatch."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.automation.handlers.registry import get_handler
from app.domain.entities.user import User, UserRole
from app.features.auth.dependencies import require_officer_or_admin, validate_csrf_token
from app.features.reports.slug_map import MANUAL_REPORT_SLUGS, resolve_manual_slug
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


@pytest.mark.parametrize("slug", sorted(MANUAL_REPORT_SLUGS))
@pytest.mark.asyncio
async def test_get_config_returns_defaults_not_404(api_client: AsyncClient, slug: str):
    response = await api_client.get(f"/api/v1/reports/{slug}/config")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["report_slug"] == slug
    assert payload["has_saved_configuration"] is False
    assert len(payload["available_columns"]) > 0
    assert len(payload["default_column_ids"]) > 0
    assert len(payload["selected_column_ids"]) > 0
    assert payload["column_order"] == payload["selected_column_ids"]


@pytest.mark.asyncio
async def test_get_config_hyphenated_train_no(api_client: AsyncClient):
    response = await api_client.get("/api/v1/reports/train-no/config")
    assert response.status_code == 200
    assert response.json()["report_slug"] == "train-no"


@pytest.mark.asyncio
async def test_get_config_unknown_slug_404(api_client: AsyncClient):
    response = await api_client.get("/api/v1/reports/not-a-report/config")
    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["code"] == "INVALID_REPORT_SLUG"


@pytest.mark.parametrize(
    ("page_id", "expected"),
    [
        ("merging", "report1"),
        ("train-no", "train-no"),
        ("scr-train", "scr-train"),
    ],
)
def test_resolve_manual_slug_aliases(page_id: str, expected: str):
    assert resolve_manual_slug(page_id) == expected


@pytest.mark.parametrize("slug", sorted(MANUAL_REPORT_SLUGS))
def test_manual_report_handlers_registered(slug: str):
    assert get_handler(slug) is not None


@pytest.mark.asyncio
async def test_generate_lock_race_returns_409_not_500(api_client: AsyncClient):
    from app.automation.automation_lock import release_automation_lock, try_acquire_automation_lock

    try_acquire_automation_lock("other-run", "report1")
    try:
        with patch("app.features.reports.service.AutomationService") as mock_cls:
            mock_service = AsyncMock()

            async def _start(*args, **kwargs):
                from app.automation.service import AutomationLockBusyError

                raise AutomationLockBusyError(
                    active_run_id="other-run",
                    active_report_slug="report1",
                )

            mock_service.start_manual_async.side_effect = _start
            mock_cls.return_value = mock_service

            response = await api_client.post(
                "/api/v1/reports/scr-train/generate",
                json={
                    "date_from": "2026-07-25",
                    "date_to": "2026-07-26",
                    "selected_column_ids": [
                        "scr-train.complaint_ref_no",
                        "scr-train.created_on",
                    ],
                    "column_order": [
                        "scr-train.complaint_ref_no",
                        "scr-train.created_on",
                    ],
                    "export_format": "xlsx",
                    "requested_formats": ["xlsx", "pdf"],
                    "configuration_source": "manual_snapshot",
                },
            )
        assert response.status_code == 409, response.text
        assert response.json()["detail"]["code"] == "AUTOMATION_ALREADY_RUNNING"
    finally:
        release_automation_lock("other-run")


@pytest.mark.asyncio
async def test_get_run_status_handles_naive_started_at(api_client: AsyncClient):
    """SQLite may return naive datetimes; stale watchdog must not 500."""
    naive_started = datetime(2026, 7, 20, 6, 0, 0)  # no tzinfo
    run = MagicMock()
    run.id = "run-naive"
    run.status = "running"
    run.started_at = naive_started
    run.trigger_type = "manual"
    run.result_json = json.dumps(
        {
            "manual_config": {
                "report_slug": "report1",
                "report_date": "19-07-2026",
                "column_order": ["report1.source_a.organisation"],
            }
        }
    )
    run.error_message = None
    run.created_by = "test-officer"
    run.completed_at = None

    with (
        patch("app.features.reports.service.list_run_artifacts", new_callable=AsyncMock, return_value=[]),
        patch("app.features.reports.service.read_preview_rows", return_value=[]),
    ):
        from app.features.reports.service import ManualReportService

        db = MagicMock()

        async def _get(_model, _id):
            return run

        db.get = _get
        status = await ManualReportService().get_run_status(db, "run-naive", expected_slug="report1")

    assert status.status in {"Extracting", "Failed", "Ingesting", "Processing", "Generating Excel/PDF"}


@pytest.mark.asyncio
async def test_generate_dispatches_single_report_only(api_client: AsyncClient):
    with patch("app.features.reports.service.AutomationService") as mock_cls:
        mock_service = AsyncMock()
        mock_service.start_manual_async.return_value = ("run-abc", "running")
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
                "requested_formats": ["xlsx", "pdf"],
                "configuration_source": "manual_snapshot",
            },
        )

    assert response.status_code == 200
    mock_service.start_manual_async.assert_awaited_once()
    assert mock_service.start_manual_async.await_args.kwargs["report_slugs"] == ["report1"]

@pytest.mark.asyncio
async def test_preview_alias_route_matches_output_preview(api_client: AsyncClient):
    with patch(
        "app.features.reports.service.build_output_preview",
        new_callable=AsyncMock,
    ) as mock_preview:
        mock_preview.return_value = {
            "available": True,
            "report_slug": "report1",
            "visible_columns": ["Organisation"],
            "preview_rows": [{"Organisation": "SCR"}],
            "selected_count": 1,
            "selected_column_ids": ["report1.source_a.organisation"],
            "column_order": ["report1.source_a.organisation"],
        }
        body = {
            "selected_column_ids": ["report1.source_a.organisation"],
            "column_order": ["report1.source_a.organisation"],
        }
        alias = await api_client.post("/api/v1/reports/report1/preview", json=body)
        legacy = await api_client.post("/api/v1/reports/report1/output-preview", json=body)

    assert alias.status_code == 200, alias.text
    assert legacy.status_code == 200, legacy.text
    assert alias.json()["visible_columns"] == legacy.json()["visible_columns"]


@pytest.mark.parametrize(
    ("alias", "expected"),
    [
        ("report2", "division"),
        ("report3", "train-no"),
        ("report4", "types"),
        ("report5", "scr-train"),
        ("report6_station", "scr-station"),
    ],
)
def test_legacy_report_aliases_resolve(alias: str, expected: str):
    assert resolve_manual_slug(alias) == expected


@pytest.mark.asyncio
async def test_save_and_load_default_selected_column_ids(
    api_client: AsyncClient, tmp_path, monkeypatch
):
    config_dir = tmp_path / "report-configs"
    monkeypatch.setattr("app.features.reports.config_store.CONFIG_DIR", config_dir)

    columns_resp = await api_client.get("/api/v1/reports/report1/output-columns")
    assert columns_resp.status_code == 200
    defaults = columns_resp.json()["default_column_ids"]
    assert len(defaults) >= 2
    custom_defaults = defaults[:2]

    save_resp = await api_client.put(
        "/api/v1/reports/report1/config",
        json={
            "selected_column_ids": defaults,
            "column_order": defaults,
            "default_selected_column_ids": custom_defaults,
            "export_format": "xlsx",
        },
    )
    assert save_resp.status_code == 200, save_resp.text

    get_resp = await api_client.get("/api/v1/reports/report1/config")
    assert get_resp.status_code == 200, get_resp.text
    payload = get_resp.json()
    assert payload["default_selected_column_ids"] == custom_defaults
    assert payload["selected_column_ids"] == custom_defaults
    assert payload["has_saved_configuration"] is True

    # Without an explicit default_selected_column_ids save, field stays empty.
    monkeypatch.setattr(
        "app.features.reports.config_store.CONFIG_DIR",
        tmp_path / "report-configs-empty",
    )
    empty_resp = await api_client.get("/api/v1/reports/division/config")
    assert empty_resp.status_code == 200
    assert empty_resp.json()["default_selected_column_ids"] == []
    assert len(empty_resp.json()["default_column_ids"]) > 0


@pytest.mark.asyncio
@pytest.mark.parametrize("slug", sorted(MANUAL_REPORT_SLUGS))
async def test_generate_payload_preserves_selected_columns(
    api_client: AsyncClient, slug: str
):
    columns_resp = await api_client.get(f"/api/v1/reports/{slug}/output-columns")
    assert columns_resp.status_code == 200
    defaults = columns_resp.json()["default_column_ids"][:2]
    assert defaults

    with patch("app.features.reports.service.AutomationService") as mock_cls, patch(
        "app.features.reports.service.has_valid_topn_dataset",
        new_callable=AsyncMock,
        return_value=False,
    ):
        mock_service = AsyncMock()
        mock_service.start_manual_async.return_value = (f"run-{slug}", "running")
        mock_cls.return_value = mock_service

        response = await api_client.post(
            f"/api/v1/reports/{slug}/generate",
            json={
                "date_from": "2026-07-25",
                "date_to": "2026-07-26",
                "report_slug": slug,
                "selected_column_ids": defaults,
                "column_order": defaults,
                "export_format": "xlsx",
                "requested_formats": ["xlsx", "pdf"],
                "configuration_source": "manual_snapshot",
            },
        )

    assert response.status_code == 200, response.text
    assert response.json()["report_slug"] == slug
    kwargs = mock_service.start_manual_async.await_args.kwargs
    assert kwargs["report_slugs"] == [slug]
    assert kwargs["manual_config"]["selected_column_ids"] == defaults
    assert kwargs["manual_config"]["configuration_source"] == "manual_snapshot"
