from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI

from fluxlit.client import ApiClient
from fluxlit.config import FluxlitSettings


class FluxLit:
    """Single app object combining FastAPI routes and Streamlit pages."""

    def __init__(
        self,
        *,
        title: str | None = None,
        settings: FluxlitSettings | None = None,
        fastapi_kwargs: dict[str, Any] | None = None,
    ) -> None:
        self.settings = settings or FluxlitSettings()
        if title is not None:
            self.settings.title = title

        fa_kwargs: dict[str, Any] = {
            "title": self.settings.title,
            "root_path": self.settings.root_path,
        }
        if fastapi_kwargs:
            fa_kwargs.update(fastapi_kwargs)

        self.api = FastAPI(**fa_kwargs)
        self._pages: list[tuple[str, str, Callable[..., None]]] = []

    def page(
        self, path: str, *, title: str | None = None
    ) -> Callable[[Callable[..., None]], Callable[..., None]]:
        """Register a Streamlit page reachable at `path` (Streamlit `url_path`)."""

        def decorator(fn: Callable[..., None]) -> Callable[..., None]:
            self._pages.append((path, title or fn.__name__.replace("_", " ").title(), fn))
            return fn

        return decorator

    def get_client(self) -> ApiClient:
        return ApiClient()

    @property
    def pages(self) -> list[tuple[str, str, Callable[..., None]]]:
        return list(self._pages)
