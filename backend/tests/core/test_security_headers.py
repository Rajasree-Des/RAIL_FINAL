"""Unit tests for security headers middleware."""

from unittest.mock import MagicMock

import pytest
from starlette.requests import Request
from starlette.responses import Response

from app.core.security.headers import (
    DEVELOPMENT_CSP,
    PRODUCTION_CSP,
    SecurityHeadersMiddleware,
)


async def _dispatch_with_debug(*, debug: bool, monkeypatch: pytest.MonkeyPatch) -> Response:
    middleware = SecurityHeadersMiddleware(app=MagicMock())
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})

    async def call_next(_request: Request) -> Response:
        return Response()

    monkeypatch.setattr("app.core.security.headers.settings.debug", debug)
    return await middleware.dispatch(request, call_next)


@pytest.mark.asyncio
async def test_csp_development_when_debug_true(monkeypatch: pytest.MonkeyPatch):
    response = await _dispatch_with_debug(debug=True, monkeypatch=monkeypatch)

    assert response.headers["Content-Security-Policy"] == DEVELOPMENT_CSP
    assert "cdn.jsdelivr.net" in response.headers["Content-Security-Policy"]
    assert "fastapi.tiangolo.com" in response.headers["Content-Security-Policy"]


@pytest.mark.asyncio
async def test_csp_production_when_debug_false(monkeypatch: pytest.MonkeyPatch):
    response = await _dispatch_with_debug(debug=False, monkeypatch=monkeypatch)

    csp = response.headers["Content-Security-Policy"]
    assert csp == PRODUCTION_CSP
    assert "cdn.jsdelivr.net" not in csp
    assert "object-src 'none'" in csp


@pytest.mark.asyncio
async def test_other_security_headers_always_present(monkeypatch: pytest.MonkeyPatch):
    response = await _dispatch_with_debug(debug=False, monkeypatch=monkeypatch)

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-XSS-Protection"] == "1; mode=block"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Permissions-Policy"] == "geolocation=(), microphone=(), camera=()"
