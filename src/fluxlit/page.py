"""Streamlit page registration types."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from fluxlit.client import ApiClient


class PageFn(Protocol):
    def __call__(self, st: Any, client: ApiClient, /) -> None: ...
