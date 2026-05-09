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
    return request_id_ctx.get()


def new_request_id() -> str:
    return str(uuid.uuid4())


def set_request_id(value: str | None) -> contextvars.Token[str | None]:
    return request_id_ctx.set(value)


def reset_request_id(token: contextvars.Token[str | None]) -> None:
    request_id_ctx.reset(token)
