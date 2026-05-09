"""Small utilities for declaring :class:`fastapi.APIRouter` instances."""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum
from typing import cast

from fastapi import APIRouter


def router(*, prefix: str = "", tags: Sequence[str] | None = None) -> APIRouter:
    """Create an :class:`~fastapi.APIRouter` with optional prefix and OpenAPI tags.

    Exists to normalize ``tags`` typing (``list[str]`` vs enum tags) for strict callers.

    Args:
        prefix: Path prefix for all routes on this router.
        tags: Tag names attached to operations in OpenAPI.

    Returns:
        A new :class:`~fastapi.APIRouter`.
    """
    t = cast(
        list[str | Enum] | None,
        list(tags) if tags is not None else None,
    )
    return APIRouter(prefix=prefix, tags=t)
