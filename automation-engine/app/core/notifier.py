"""Notify backend after download events."""

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class BackendNotifier:
    def __init__(self, service_token: str | None = None, base_url: str | None = None):
        self.token = service_token or settings.service_token
        self.base_url = (base_url or settings.backend_url).rstrip("/")
        self.api_prefix = settings.backend_api_prefix

    async def callback(self, payload: dict[str, Any]) -> None:
        url = f"{self.base_url}{self.api_prefix}/automation/callback"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.token}",
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("Backend callback failed: %s", type(e).__name__)

    async def log(self, run_id: str, message: str, level: str = "info") -> None:
        await self.callback(
            {
                "run_id": run_id,
                "status": "running",
                "log_message": message,
                "log_level": level,
            }
        )

    async def report_download(
        self,
        run_id: str,
        file_path: str,
        report_name: str,
        file_size: int,
    ) -> None:
        await self.callback(
            {
                "run_id": run_id,
                "status": "running",
                "log_message": f"Downloaded: {report_name}",
                "log_level": "info",
                "artifact": {
                    "type": "download",
                    "file_path": file_path,
                    "file_size_bytes": file_size,
                    "report_name": report_name,
                },
            }
        )

    async def report_failure(
        self,
        run_id: str,
        error: str,
        screenshot_path: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "run_id": run_id,
            "status": "failed",
            "log_message": error,
            "log_level": "error",
            "error_message": error,
        }
        if screenshot_path:
            payload["artifact"] = {
                "type": "screenshot",
                "file_path": screenshot_path,
            }
        await self.callback(payload)

    async def report_complete(
        self,
        run_id: str,
        success_count: int,
        failure_count: int,
        session_state: str | None = None,
    ) -> None:
        status = "completed" if failure_count == 0 else "failed"
        payload: dict[str, Any] = {
            "run_id": run_id,
            "status": status,
            "success_count": success_count,
            "failure_count": failure_count,
            "log_message": f"Run finished: {success_count} success, {failure_count} failed",
            "log_level": "info" if failure_count == 0 else "warning",
        }
        if session_state:
            payload["session_state"] = session_state
        await self.callback(payload)
