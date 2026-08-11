"""HTTP client for the standalone automation-engine service."""

import logging
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)


class AutomationEngineClient:
    def __init__(self, base_url: str | None = None, token: str | None = None):
        self.base_url = (base_url or settings.automation_engine_url).rstrip("/")
        self.token = token or settings.automation_service_token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    async def start_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/internal/run",
                    json=payload,
                    headers=self._headers(),
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error("Automation engine start failed: %s", type(e).__name__)
            raise ExternalServiceError("automation-engine", str(e)) from e

    async def stop_run(self, run_id: str) -> dict[str, Any]:
        return await self._post(f"/internal/stop/{run_id}")

    async def pause_run(self, run_id: str) -> dict[str, Any]:
        return await self._post(f"/internal/pause/{run_id}")

    async def resume_run(self, run_id: str) -> dict[str, Any]:
        return await self._post(f"/internal/resume/{run_id}")

    async def get_engine_status(self, run_id: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/internal/status/{run_id}",
                    headers=self._headers(),
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            raise ExternalServiceError("automation-engine", str(e)) from e

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def _post(self, path: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.base_url}{path}",
                    headers=self._headers(),
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            raise ExternalServiceError("automation-engine", str(e)) from e
