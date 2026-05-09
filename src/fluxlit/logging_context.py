"""Request correlation ID storage for the gateway and optional FastAPI logging middleware.

The gateway sets a context variable from the ``X-Request-ID`` header (or generates a UUID)
for each HTTP/WebSocket request. Optional FastAPI middleware can use the same header so
access logs share the same identifier.

Constants:

- :data:`REQUEST_ID_HEADER` — lowercase header name clients may send.
- :data:`request_id_ctx` — :class:`contextvars.ContextVar` holding the current ID.
- :data:`log` — ``logging.getLogger("fluxlit")`` for package diagnostics.
"""

from __future__ import annotations

import contextvars
import logging
import uuid
from typing import Final

REQUEST_ID_HEADER: Final = "x-request-id"

request_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "fluxlit_request_id", default=None
)

log = logging.getLogger("fluxlit")


def get_request_id() -> str | None:
    """Return the active request ID from :data:`request_id_ctx`, if any."""
    return request_id_ctx.get()


def new_request_id() -> str:
    """Generate a new opaque request ID (UUID4 string)."""
    return str(uuid.uuid4())


def set_request_id(value: str | None) -> contextvars.Token[str | None]:
    """Bind ``value`` into :data:`request_id_ctx`; returns a token for :func:`reset_request_id`."""
    return request_id_ctx.set(value)


def reset_request_id(token: contextvars.Token[str | None]) -> None:
    """Restore the previous context after :func:`set_request_id` (typically in ``finally``)."""
    request_id_ctx.reset(token)
