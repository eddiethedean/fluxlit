"""Authentication helpers: forward-auth (trusted headers) and related utilities."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status
from starlette.requests import Request

AuthDependency = Callable[[Request], Any]
"""FastAPI dependency callable taking the incoming :class:`~fastapi.Request`."""


def proxy_user_header(header_name: str = "X-Remote-User") -> AuthDependency:
    """Build a dependency that reads a trusted user id from an HTTP header.

    Intended for deployments where an upstream proxy (SSO, API gateway) authenticates
    the user and forwards identity via a header. This does **not** validate signatures
    or sessions; it only exposes the header value to route handlers.

    For stricter control (HTTPS, client IP allowlists), use :class:`TrustedProxyUser`.

    Args:
        header_name: Header to read (default ``X-Remote-User``).

    Returns:
        Async dependency returning ``str | None`` (the raw header value).
    """

    async def load_user(request: Request) -> str | None:
        return request.headers.get(header_name)

    return load_user


@dataclass(frozen=True, slots=True)
class TrustedProxyUserConfig:
    """Policy for :class:`TrustedProxyUser`."""

    header_name: str = "X-Remote-User"
    require_https: bool = False
    """If True, require ``X-Forwarded-Proto: https`` or direct ``https`` URL scheme."""

    trusted_client_hosts: frozenset[str] | None = None
    """If set, ``request.client.host`` must be in this set (use with reverse proxies)."""

    require_non_empty_user: bool = True
    """If True, missing header yields 401 instead of allowing empty identity."""


class TrustedProxyUser:
    """FastAPI dependency: trusted gateway user header with optional safety checks.

    Use only when a **network path** guarantees that clients cannot spoof the header
    (for example, the app listens only on loopback and nginx strips inbound identity
    headers from untrusted clients).
    """

    def __init__(self, config: TrustedProxyUserConfig | None = None) -> None:
        self._config = config or TrustedProxyUserConfig()

    def _effective_scheme(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-proto")
        if forwarded:
            return forwarded.split(",")[0].strip().lower()
        return request.url.scheme.lower()

    def __call__(self, request: Request) -> str:
        if self._config.trusted_client_hosts is not None:
            client = request.client
            host = client.host if client else None
            if host not in self._config.trusted_client_hosts:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Untrusted client for forward-auth",
                )

        if self._config.require_https and self._effective_scheme(request) != "https":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="HTTPS required for forward-auth",
            )

        raw = request.headers.get(self._config.header_name)
        if self._config.require_non_empty_user and not (raw and raw.strip()):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing trusted user header",
            )
        return (raw or "").strip()


__all__ = [
    "AuthDependency",
    "TrustedProxyUser",
    "TrustedProxyUserConfig",
    "proxy_user_header",
]
