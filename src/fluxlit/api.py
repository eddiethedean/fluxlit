"""Helpers for organizing FastAPI routers (optional)."""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum
from typing import cast

from fastapi import APIRouter


def router(*, prefix: str = "", tags: Sequence[str] | None = None) -> APIRouter:
    t = cast(
        list[str | Enum] | None,
        list(tags) if tags is not None else None,
    )
    return APIRouter(prefix=prefix, tags=t)
