"""HTTP request utilities."""

from fastapi import Request


def get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def get_client_identifier(request: Request, default: str = "unknown") -> str:
    return get_client_ip(request) or default
