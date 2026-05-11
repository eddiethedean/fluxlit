"""ASGI gateway factory: API dispatch, Streamlit HTTP/WS proxy, metrics, access logs."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import httpx
from starlette.types import ASGIApp

from fluxlit.config import FluxlitSettings
from fluxlit.gateway._log import gateway_log
from fluxlit.gateway.dispatch import make_gateway_app
from fluxlit.gateway.metrics import get_gateway_prom_metrics
from fluxlit.gateway.options import gateway_opts
from fluxlit.gateway.paths import normalize_root_mount
from fluxlit.logging import DEFAULT_SENSITIVE_QUERY_KEYS


def build_gateway(
    api_app: ASGIApp,
    upstream_base: str,
    *,
    upstream_resolver: Callable[[], str] | None = None,
    access_log: bool = False,
    api_prefix: str = "/api",
    root_mount: str = "",
    proxy_settings: FluxlitSettings | None = None,
) -> ASGIApp:
    """Build the composite ASGI application used as Uvicorn's entrypoint.

    Routes whose path equals ``api_prefix`` or starts with ``api_prefix/`` are
    forwarded to ``api_app`` with that prefix stripped from ``path`` and ``raw_path``.
    All other HTTP traffic and WebSockets are reverse-proxied to ``upstream_base``
    (typically the internal Streamlit origin), or to the URL returned by
    ``upstream_resolver`` when that is provided (evaluated per request).

    Lifespan events are delegated only to ``api_app``.

    Args:
        api_app: Inner FastAPI / Starlette app (mount path not included in its routes).
        upstream_base: Base URL for Streamlit when ``upstream_resolver`` is unset.
        upstream_resolver: If set, called for each proxied request to get the current
            upstream base (e.g. after Streamlit restarts on a new port). ``upstream_base``
            is ignored for proxying when this is set.
        access_log: If True, emit one INFO log per request with structured ``extra`` fields.
        api_prefix: Public URL prefix for the API (default ``/api``).
        root_mount: Optional browser-visible path prefix when the app is published
            under a subpath (e.g. Posit Connect / Workbench). Must match
            :class:`~fluxlit.config.FluxlitSettings.root_path` and Streamlit
            ``server.baseUrlPath``. When the proxy forwards the full path, this
            strip is applied before dispatch; Streamlit still receives paths that
            include the prefix.
        proxy_settings: Optional :class:`~fluxlit.config.FluxlitSettings` for upstream
            timeouts, body limits, concurrency, and WebSocket tuning (defaults match
            historical hardcoded gateway behavior when omitted).

    Returns:
        A callable ASGI3 application.
    """
    fixed_upstream = upstream_base.rstrip("/")
    opts = gateway_opts(proxy_settings)
    http_client: httpx.AsyncClient | None = None
    http_client_lock = asyncio.Lock()

    async def _shared_httpx_client() -> httpx.AsyncClient:
        nonlocal http_client
        async with http_client_lock:
            if http_client is None:
                timeout = httpx.Timeout(opts.read_timeout, connect=opts.connect_timeout)
                limits: httpx.Limits | None = None
                if opts.httpx_max_connections > 0:
                    mk = (
                        opts.httpx_max_keepalive_connections
                        if opts.httpx_max_keepalive_connections > 0
                        else opts.httpx_max_connections
                    )
                    limits = httpx.Limits(
                        max_connections=opts.httpx_max_connections,
                        max_keepalive_connections=mk,
                    )
                client_kw: dict[str, Any] = {"timeout": timeout}
                if limits is not None:
                    client_kw["limits"] = limits
                http_client = httpx.AsyncClient(**client_kw)
        return http_client

    upstream_sem: asyncio.Semaphore | None = None
    if opts.max_concurrent_upstream_http > 0:
        upstream_sem = asyncio.Semaphore(opts.max_concurrent_upstream_http)

    def resolve_upstream() -> str:
        if upstream_resolver is not None:
            return upstream_resolver().strip().rstrip("/")
        return fixed_upstream

    prefix = api_prefix.rstrip("/") or "/api"
    mount = normalize_root_mount(root_mount)

    _log_qs_keys = set(DEFAULT_SENSITIVE_QUERY_KEYS)
    if proxy_settings is not None:
        _p = (getattr(proxy_settings, "url_session_query_param", "") or "").strip()
        if _p:
            _log_qs_keys.add(_p)
    log_sensitive_query_keys: frozenset[str] = frozenset(_log_qs_keys)

    prom_metrics = None
    prom_path = "/__fluxlit/metrics"
    if proxy_settings and proxy_settings.enable_gateway_prometheus_metrics:
        prom_metrics = get_gateway_prom_metrics()
        raw_mp = (proxy_settings.gateway_prometheus_metrics_path or "/__fluxlit/metrics").strip()
        prom_path = raw_mp if raw_mp.startswith("/") else f"/{raw_mp}"
        if prom_path == prefix or prom_path.startswith(f"{prefix}/"):
            gateway_log.warning(
                "gateway_prometheus_metrics_path must not start with api_mount_path %r; "
                "disabling Prometheus metrics for this gateway build",
                prefix,
            )
            prom_metrics = None

    return make_gateway_app(
        api_app=api_app,
        resolve_upstream=resolve_upstream,
        prefix=prefix,
        mount=mount,
        opts=opts,
        upstream_sem=upstream_sem,
        shared_httpx_client=_shared_httpx_client,
        prom_metrics=prom_metrics,
        prom_path=prom_path,
        access_log=access_log,
        log_sensitive_query_keys=log_sensitive_query_keys,
    )
