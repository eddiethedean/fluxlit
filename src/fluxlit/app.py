"""The :class:`FluxLit` application object: FastAPI (``.api``) plus Streamlit pages."""

from __future__ import annotations

import importlib
import logging
import pkgutil
from collections.abc import Callable
from types import FunctionType
from typing import Any

from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

from fluxlit.client import ApiClient
from fluxlit.config import FluxlitSettings
from fluxlit.health import probe_streamlit_ready
from fluxlit.jwt_auth import JWTBearer
from fluxlit.logging_context import (
    REQUEST_ID_HEADER,
    new_request_id,
    reset_request_id,
    set_request_id,
)
from fluxlit.oidc import GenericOIDCClient, OIDCBFFConfig, register_oidc_bff_routes
from fluxlit.security_middleware import SecurityHeadersMiddleware

_api_log = logging.getLogger("fluxlit.api")


class FluxLit:
    """Combine a FastAPI application and registered Streamlit pages in one object.

    Use :attr:`api` for HTTP routes, dependencies, and OpenAPI (mounted under
    :attr:`~fluxlit.config.FluxlitSettings.api_mount_path` on the public gateway).
    Use :meth:`page` or :meth:`discover_pages` to register Streamlit UI; the runtime
    builds ``st.navigation`` from registered pages.

    **Security (optional):** :meth:`make_jwt_bearer` reads ``FLUXLIT_JWT_*`` from
    :attr:`settings`; :meth:`attach_oidc_login` registers OIDC BFF routes (call **at most once**
    per instance) using ``FLUXLIT_PUBLIC_BASE_URL`` and ``FLUXLIT_OIDC_BFF_SECRET`` when you do
    not pass secrets explicitly.

    ``GET /healthz`` (liveness) and ``GET /readyz`` (readiness vs Streamlit) are
    registered on :attr:`api` (hidden from OpenAPI).

    Args:
        title: If set, overrides ``FluxlitSettings.title`` for this instance.
        settings: Explicit settings; default is :class:`~fluxlit.config.FluxlitSettings`
            loaded from env / ``.env``.
        import_target: Optional ``module:attr`` string for this instance (same as
            ``FLUXLIT_APP`` / ``fluxlit.toml`` ``target``). Use when the module name is not
            ``app`` (e.g. ``main:app``) so ``uvicorn`` and the Streamlit child import the
            right object. If unset, resolution follows env and project file; see
            :func:`fluxlit.runtime.resolve_import_target_for_unified`.
        fastapi_kwargs: Extra keyword arguments forwarded to :class:`fastapi.FastAPI`.
    """

    def __init__(
        self,
        *,
        title: str | None = None,
        settings: FluxlitSettings | None = None,
        import_target: str | None = None,
        fastapi_kwargs: dict[str, Any] | None = None,
    ) -> None:
        self.import_target = import_target.strip() if import_target else None
        self._unified_asgi_cache: ASGIApp | None = None
        self.settings = settings or FluxlitSettings()
        if title is not None:
            self.settings.title = title

        fa_kwargs: dict[str, Any] = {
            "title": self.settings.title,
            "root_path": self.settings.public_mount_path(),
        }
        if fastapi_kwargs:
            fa_kwargs.update(fastapi_kwargs)

        self.api = FastAPI(**fa_kwargs)
        self._pages: list[tuple[str, str, Callable[..., None]]] = []
        self._oidc_bff_attached: bool = False

        if self.settings.enable_security_headers:
            self.api.add_middleware(SecurityHeadersMiddleware)
        if self.settings.cors_allow_origins:
            self.api.add_middleware(
                CORSMiddleware,
                allow_origins=list(self.settings.cors_allow_origins),
                allow_credentials=self.settings.cors_allow_credentials,
                allow_methods=["*"],
                allow_headers=["*"],
            )

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

        @self.api.get("/readyz", include_in_schema=False, response_model=None)
        async def _readyz() -> JSONResponse:
            ok, detail = await probe_streamlit_ready()
            if ok:
                return JSONResponse(content={"status": "ready", "streamlit": detail})
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "detail": detail},
            )

    def _unified_asgi(self) -> ASGIApp:
        """Lazily build gateway + Streamlit ASGI (see :meth:`__call__`)."""
        if self._unified_asgi_cache is None:
            from fluxlit.runtime import asgi_from_fluxlit, resolve_import_target_for_unified

            self._unified_asgi_cache = asgi_from_fluxlit(
                self,
                resolve_import_target_for_unified(self),
            )
        return self._unified_asgi_cache

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI entrypoint: run ``uvicorn main:app`` like a normal FastAPI app."""
        await self._unified_asgi()(scope, receive, send)

    def discover_pages(self, directory: str, *, package: str) -> FluxLit:
        """Load Streamlit page modules and call ``register(self)`` on each.

        Imports the subpackage ``{package}.{directory}``, then every submodule
        (skipping packages and names starting with ``_``). If a module defines
        ``register(app: FluxLit) -> None``, it is invoked; implementations typically
        attach handlers with :meth:`page` inside ``register``.

        Registered pages are sorted by ``(path, title)`` for stable navigation order.

        Args:
            directory: Subpackage name under ``package`` (e.g. ``"pages"``).
            package: Importable parent package (must have ``__path__``).

        Returns:
            ``self`` for chaining.

        Raises:
            TypeError: If ``package`` is not a package.
            ImportError: If ``{package}.{directory}`` cannot be imported.

        Note:
            If a page module's ``register(app)`` raises after earlier modules ran,
            pages from those modules remain registered (best-effort; no rollback).
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
        """Decorator registering a Streamlit page at a URL path.

        The decorated callable should accept ``(st, client)`` where ``st`` is the
        Streamlit module and ``client`` is an :class:`~fluxlit.client.ApiClient` for
        your mounted API.

        Args:
            path: URL path segment for Streamlit (e.g. ``"/"``, ``"/reports"``).
            title: Sidebar / navigation title; defaults from the function name.

        Returns:
            Decorator that registers the function and returns it unchanged.
        """

        def decorator(fn: Callable[..., None]) -> Callable[..., None]:
            default_title = "Page"
            if isinstance(fn, FunctionType):
                default_title = fn.__name__.replace("_", " ").title()
            self._pages.append((path, title or default_title, fn))
            return fn

        return decorator

    def get_client(self) -> ApiClient:
        """Return an :class:`~fluxlit.client.ApiClient` for server-side API calls.

        Uses ``FLUXLIT_INTERNAL_API_BASE`` when set (as in the managed runtime).
        """
        return ApiClient()

    def make_jwt_bearer(self) -> JWTBearer:
        """JWT :class:`~fluxlit.jwt_auth.JWTBearer` from :attr:`settings` (``FLUXLIT_JWT_*``).

        Requires ``jwt_issuer``, ``jwt_audience``, and either ``jwt_hs256_secret`` or
        ``jwt_jwks_url``. Raises :class:`ValueError` with env-oriented hints if misconfigured.
        """
        return JWTBearer.from_fluxlit_settings(self.settings)

    def attach_oidc_login(
        self,
        oidc: GenericOIDCClient,
        *,
        first_party_secret: str | None = None,
        **bff_overrides: Any,
    ) -> APIRouter:
        """Register OIDC login / callback / token-exchange routes on :attr:`api`.

        Uses :attr:`~fluxlit.config.FluxlitSettings.public_base_url` for redirects unless
        you pass ``public_base_url=...`` in ``bff_overrides``. The first-party JWT signing
        secret comes from ``first_party_secret`` or
        :attr:`~fluxlit.config.FluxlitSettings.oidc_bff_secret` (``FLUXLIT_OIDC_BFF_SECRET``).

        Returns the :class:`fastapi.APIRouter` that was included (same as
        :func:`fluxlit.oidc.register_oidc_bff_routes`).

        Raises:
            ValueError: If this method is called more than once on the same :class:`FluxLit`
                instance (duplicate auth routes).
        """
        if self._oidc_bff_attached:
            msg = "attach_oidc_login() was already called on this FluxLit instance"
            raise ValueError(msg)
        secret = (first_party_secret or self.settings.oidc_bff_secret or "").strip()
        if not secret:
            msg = (
                "OIDC BFF needs a signing secret: pass first_party_secret=... or set "
                "FLUXLIT_OIDC_BFF_SECRET on FluxlitSettings"
            )
            raise ValueError(msg)
        public_raw = bff_overrides.pop("public_base_url", None)
        if public_raw is not None:
            public_base = str(public_raw).strip()
        else:
            public_base = (self.settings.public_base_url or "").strip()
        cfg = OIDCBFFConfig(
            oidc=oidc,
            first_party_secret=secret,
            public_base_url=public_base,
            **bff_overrides,
        )
        router = register_oidc_bff_routes(self.api, cfg)
        self._oidc_bff_attached = True
        return router

    @property
    def pages(self) -> list[tuple[str, str, Callable[..., None]]]:
        """``(path, title, handler)`` tuples for registered Streamlit pages."""
        return list(self._pages)
