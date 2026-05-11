"""Request ID extraction from ASGI scope."""

from __future__ import annotations

from starlette.types import Scope

from fluxlit.logging import REQUEST_ID_HEADER, new_request_id


def request_id_from_scope(scope: Scope) -> str:
    """Return the client ``X-Request-ID`` header value or a new UUID string."""
    raw = scope.get("headers") or []
    want = REQUEST_ID_HEADER.lower().encode("latin-1")
    for k, v in raw:
        if k.lower() == want:
            return v.decode("latin-1").strip() or new_request_id()
    return new_request_id()
