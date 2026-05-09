"""Authentication hooks (placeholders for future JWT, sessions, proxy headers)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Request

AuthDependency = Callable[[Request], Any]


def proxy_user_header(header_name: str = "X-Remote-User") -> AuthDependency:
    """Trust an upstream proxy to identify the user via a header."""

    async def load_user(request: Request) -> str | None:
        return request.headers.get(header_name)

    return load_user
