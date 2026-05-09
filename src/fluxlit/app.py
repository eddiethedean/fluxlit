from __future__ import annotations

import importlib
import logging
import pkgutil
from collections.abc import Callable
from types import FunctionType
from typing import Any

from fastapi import FastAPI
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from fluxlit.client import ApiClient
from fluxlit.config import FluxlitSettings
from fluxlit.logging_context import (
    REQUEST_ID_HEADER,
    new_request_id,
    reset_request_id,
    set_request_id,
)

_api_log = logging.getLogger("fluxlit.api")


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

        if self.settings.enable_request_logging:

            @self.api.middleware("http")
            async def _fluxlit_request_log(
                request: Request, call_next: RequestResponseEndpoint
            ) -> Response:
                rid = request.headers.get(REQUEST_ID_HEADER) or new_request_id()
                token = set_request_id(rid)
                try:
                    response = await call_next(request)
                    _api_log.info(
                        "%s %s -> %s",
                        request.method,
                        request.url.path,
                        response.status_code,
                    )
                    return response
                finally:
                    reset_request_id(token)

        @self.api.get("/healthz", include_in_schema=False)
        def _healthz() -> dict[str, str]:
            return {"status": "ok"}

    def discover_pages(self, directory: str, *, package: str) -> FluxLit:
        """Import ``<package>.<directory>.*`` modules and call ``register(app)`` when present.

        Each module (except ``_``-prefixed) may define ``register(app: FluxLit) -> None`` and
        use ``@app.page`` inside that function.
        """
        parent = importlib.import_module(package)
        paths = getattr(parent, "__path__", None)
        if paths is None:
            msg = f"{package!r} must be a package to discover pages"
            raise TypeError(msg)
        subpkg = f"{package}.{directory}"
        try:
            importlib.import_module(subpkg)
        except ImportError as e:
            msg = f"Cannot import page package {subpkg!r}: {e}"
            raise ImportError(msg) from e

        pkg = importlib.import_module(subpkg)
        for modinfo in sorted(
            pkgutil.iter_modules(pkg.__path__, f"{subpkg}."),
            key=lambda m: m.name,
        ):
            if modinfo.ispkg or modinfo.name.rpartition(".")[-1].startswith("_"):
                continue
            mod = importlib.import_module(modinfo.name)
            register = getattr(mod, "register", None)
            if register is None:
                continue
            register(self)

        self._pages.sort(key=lambda t: (t[0], t[1]))
        return self

    def page(
        self, path: str, *, title: str | None = None
    ) -> Callable[[Callable[..., None]], Callable[..., None]]:
        """Register a Streamlit page reachable at `path` (Streamlit `url_path`)."""

        def decorator(fn: Callable[..., None]) -> Callable[..., None]:
            default_title = "Page"
            if isinstance(fn, FunctionType):
                default_title = fn.__name__.replace("_", " ").title()
            self._pages.append((path, title or default_title, fn))
            return fn

        return decorator

    def get_client(self) -> ApiClient:
        return ApiClient()

    @property
    def pages(self) -> list[tuple[str, str, Callable[..., None]]]:
        return list(self._pages)
