"""Integration tests for summary generation with mocked LLM."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.password import password_hasher
from app.features.summary.llm.base import LLMClient, LLMResponse
from app.features.summary.seeds.default_prompts import DEFAULT_PROMPT_TEMPLATES
from app.infrastructure.database.models import AiPromptTemplateModel, UserModel
from app.main import app


class FakeLLMClient(LLMClient):
    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> LLMResponse:
        return LLMResponse(
            content="Test summary content from mock LLM.",
            model="test-model",
            prompt_tokens=50,
            completion_tokens=20,
            total_tokens=70,
        )


SAMPLE_DATASET = [
    {
        "division": "SCR",
        "train_number": "12724",
        "complaint_type": "Electrical Equipment",
        "complaint_count": 45,
        "status": "Resolved",
        "unsatisfactory_count": 3,
    },
]


@pytest.fixture
def mock_llm(monkeypatch):
    from app.features.summary import service as summary_service_module

    monkeypatch.setattr(
        summary_service_module.SummaryService,
        "_create_llm_client",
        staticmethod(lambda: FakeLLMClient()),
    )


@pytest.fixture
async def officer_user(test_session: AsyncSession) -> UserModel:
    user = UserModel(
        id="officer-user-id",
        username="officeruser",
        email="officer@example.com",
        password_hash=password_hasher.hash("TestPass123"),
        role="officer",
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    return user


@pytest.fixture
async def officer_client(
    client: AsyncClient, officer_user: UserModel
) -> tuple[AsyncClient, dict[str, str]]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "officeruser", "password": "TestPass123"},
    )
    assert response.status_code == 200
    headers = auth_headers(response)
    return client, headers


@pytest.fixture
async def seeded_templates(test_session: AsyncSession) -> None:
    for template_data in DEFAULT_PROMPT_TEMPLATES:
        test_session.add(AiPromptTemplateModel(**template_data))
    await test_session.commit()


def auth_headers(login_response) -> dict[str, str]:
    csrf_token = login_response.json().get("csrf_token")
    headers = {}
    if csrf_token:
        headers["X-CSRF-Token"] = csrf_token
    return headers


@pytest.mark.asyncio
async def test_generate_summary_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/summary/generate",
            json={
                "summary_type": "executive",
                "dataset": SAMPLE_DATASET,
                "metadata": {"report_name": "Test"},
            },
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_templates_requires_officer_or_admin(authenticated_client):
    response = await authenticated_client.get("/api/v1/summary/templates")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_templates_as_officer(officer_client, seeded_templates):
    client, _headers = officer_client
    response = await client.get("/api/v1/summary/templates")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == len(DEFAULT_PROMPT_TEMPLATES)


@pytest.mark.asyncio
async def test_generate_summary_with_mock_llm(
    officer_client, seeded_templates, mock_llm
):
    client, headers = officer_client

    response = await client.post(
        "/api/v1/summary/generate",
        json={
            "summary_type": "executive",
            "dataset": SAMPLE_DATASET,
            "metadata": {"report_name": "Test Report"},
        },
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["content"] == "Test summary content from mock LLM."
    assert data["summary_type"] == "executive"
    assert data["statistics"]["total_complaints"] >= 0
    assert data["id"]
