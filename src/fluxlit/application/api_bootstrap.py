"""FastAPI middleware and built-in routes for a :class:`~fluxlit.app.FluxLit` instance."""

from __future__ import annotations

import logging
from typing import Any, cast

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import Response

from fluxlit.config import FluxlitSettings, JsonValue
from fluxlit.health import probe_streamlit_ready
from fluxlit.logging import REQUEST_ID_HEADER, new_request_id, reset_request_id, set_request_id
from fluxlit.security import SecurityHeadersMiddleware

_api_log = logging.getLogger("fluxlit.api")
_STATE_SETTINGS = "fluxlit_settings"
_STATE_UPSTREAM_RESOLVER = "fluxlit_streamlit_upstream_resolver"

_CORS_MIDDLEWARE_EXCLUSIVE_KWARGS = frozenset(
    {"allow_origins", "allow_credentials", "allow_methods", "allow_headers"}
)


def _cors_middleware_extras(
    cors_middleware_kwargs: dict[str, JsonValue],
) -> dict[str, JsonValue]:
    skip = _CORS_MIDDLEWARE_EXCLUSIVE_KWARGS
    return {k: v for k, v in cors_middleware_kwargs.items() if k not in skip}


def wire_fluxlit_api(api: FastAPI, settings: FluxlitSettings) -> None:
    """Apply security/CORS/request logging and register ``/healthz`` / ``/readyz``."""
    setattr(api.state, _STATE_SETTINGS, settings)

    if settings.enable_security_headers:
        api.add_middleware(SecurityHeadersMiddleware)
    if settings.cors_allow_origins:
        api.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_allow_origins),
            allow_credentials=settings.cors_allow_credentials,
            allow_methods=["*"],
            allow_headers=["*"],
            **cast(
                dict[str, Any],
                _cors_middleware_extras(settings.cors_middleware_kwargs),
            ),
        )

    if settings.enable_request_logging:

        @api.middleware("http")
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

    @api.get("/healthz", include_in_schema=False)
    def _healthz() -> dict[str, str]:
        return {"status": "ok"}

    @api.get("/readyz", include_in_schema=False, response_model=None)
    async def _readyz() -> JSONResponse:
        active_settings = getattr(api.state, _STATE_SETTINGS, settings)
        resolver = getattr(api.state, _STATE_UPSTREAM_RESOLVER, None)
        upstream = resolver() if callable(resolver) else None
        ok, detail = await probe_streamlit_ready(
            upstream=upstream,
            settings=active_settings,
        )
        if ok:
            return JSONResponse(content={"status": "ready", "streamlit": detail})
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "detail": detail},
        )
