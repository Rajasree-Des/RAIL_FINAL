"""Integration tests for the system info/maintenance API."""

import pytest
from httpx import AsyncClient
from pathlib import Path
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.features.system.service as system_service
from app.core.security.password import password_hasher
from app.features.system.cache_cleaner import clear_whitelisted_cache, validate_cache_path
from app.infrastructure.database.models import UserActivityModel, UserModel


@pytest.fixture(autouse=True)
def cdp_down(monkeypatch):
    """Make the CDP probe fail fast and deterministically."""

    class _FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            raise ConnectionError("CDP not running")

    monkeypatch.setattr(system_service.httpx, "AsyncClient", _FailingClient)


@pytest.fixture
async def admin_user(test_session: AsyncSession) -> UserModel:
    user = UserModel(
        id="admin-system-id",
        username="systemadmin",
        email="systemadmin@example.com",
        password_hash=password_hasher.hash("TestPass123"),
        role="admin",
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    return user


@pytest.fixture
async def admin_client(client: AsyncClient, admin_user: UserModel) -> tuple[AsyncClient, dict]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "systemadmin", "password": "TestPass123"},
    )
    assert response.status_code == 200
    csrf = response.json().get("csrf_token")
    headers = {"X-CSRF-Token": csrf} if csrf else {}
    return client, headers


@pytest.mark.asyncio
async def test_system_info_requires_auth(client):
    response = await client.get("/api/v1/system/info")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_system_info_forbidden_for_viewer(authenticated_client):
    response = await authenticated_client.get("/api/v1/system/info")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_system_info_shape(admin_client):
    client, _ = admin_client
    response = await client.get("/api/v1/system/info")
    assert response.status_code == 200
    data = response.json()

    assert data["backend"]["ok"] is True
    assert data["database"]["ok"] is True
    assert data["cdp"]["ok"] is False
    assert data["automation_status"] == "idle"
    assert data["app_version"]
    assert data["environment"]
    assert isinstance(data["storage_usage_bytes"], int)
    assert data["last_successful_run_at"] is None
    assert data["last_failed_run_at"] is None


@pytest.mark.asyncio
async def test_clear_cache(admin_client, tmp_path, monkeypatch):
    client, headers = admin_client
    backend_root = tmp_path / "backend"
    backend_root.mkdir()
    (backend_root / "app").mkdir()
    (backend_root / "app" / "main.py").write_text("# test\n", encoding="utf-8")
    (backend_root / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")

    pytest_cache = backend_root / ".pytest_cache"
    pytest_cache.mkdir()
    cache_file = pytest_cache / "dummy.txt"
    cache_file.write_text("cache me", encoding="utf-8")

    debug_dir = backend_root / "storage" / "debug"
    debug_dir.mkdir(parents=True)
    debug_file = debug_dir / "probe.json"
    debug_file.write_text("{}", encoding="utf-8")

    preserved_db = backend_root / "railway.db"
    preserved_db.write_bytes(b"sqlite-data")
    output_dir = backend_root / "storage" / "output"
    output_dir.mkdir(parents=True)
    report_file = output_dir / "report.pdf"
    report_file.write_bytes(b"%PDF preserved")

    monkeypatch.chdir(backend_root)

    response = await client.post("/api/v1/system/clear-cache", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "settings" in data["cleared"]
    assert "dashboard_analytics" in data["cleared"]
    assert data["files_removed"] >= 2
    assert data["bytes_freed"] > 0
    assert not cache_file.exists()
    assert not debug_file.exists()
    assert preserved_db.exists()
    assert report_file.exists()


@pytest.mark.asyncio
async def test_clear_cache_preserves_activity_rows(admin_client, test_session, admin_user):
    client, headers = admin_client
    test_session.add(
        UserActivityModel(
            id="preserve-activity-1",
            user_id=admin_user.id,
            action="LOGIN",
            message="Should remain after cache clear",
            status="info",
        )
    )
    await test_session.commit()
    count_before = (
        await test_session.execute(select(func.count()).select_from(UserActivityModel))
    ).scalar_one()

    response = await client.post("/api/v1/system/clear-cache", headers=headers)
    assert response.status_code == 200

    count_after = (
        await test_session.execute(select(func.count()).select_from(UserActivityModel))
    ).scalar_one()
    assert count_after == count_before


def test_cache_cleaner_rejects_path_traversal(tmp_path):
    root = tmp_path / "backend"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    assert validate_cache_path(outside, root) is False


def test_cache_cleaner_handles_locked_files(tmp_path, monkeypatch):
    backend_root = tmp_path / "backend"
    backend_root.mkdir()
    cache_dir = backend_root / ".pytest_cache"
    cache_dir.mkdir()
    locked = cache_dir / "locked.txt"
    locked.write_text("x", encoding="utf-8")

    original_unlink = Path.unlink

    def _unlink(self, missing_ok=False):
        if self.name == "locked.txt":
            raise PermissionError("locked")
        return original_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", _unlink)
    result = clear_whitelisted_cache(backend_root=backend_root, repo_root=tmp_path)
    assert result.skipped_locked >= 1
    assert result.partial is True


@pytest.mark.asyncio
async def test_clear_cache_forbidden_for_viewer(authenticated_client):
    response = await authenticated_client.post("/api/v1/system/clear-cache")
    assert response.status_code in (400, 403, 422)
