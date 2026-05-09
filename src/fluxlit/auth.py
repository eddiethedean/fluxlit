"""Lightweight authentication helpers (forward-auth style; expand in future releases)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Request

AuthDependency = Callable[[Request], Any]
"""FastAPI dependency callable taking the incoming :class:`~fastapi.Request`."""


def proxy_user_header(header_name: str = "X-Remote-User") -> AuthDependency:
    """Build a dependency that reads a trusted user id from an HTTP header.

    Intended for deployments where an upstream proxy (SSO, API gateway) authenticates
    the user and forwards identity via a header. This does **not** validate signatures
    or sessions; it only exposes the header value to route handlers.

    Args:
        header_name: Header to read (default ``X-Remote-User``).

    Returns:
        Async dependency returning ``str | None`` (the raw header value).
    """

    async def load_user(request: Request) -> str | None:
        return request.headers.get(header_name)

    return load_user
