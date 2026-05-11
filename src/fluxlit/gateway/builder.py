"""ASGI gateway factory: API dispatch, Streamlit HTTP/WS proxy, metrics, access logs."""

from __future__ import annotations

import asyncio
import importlib
import time
from collections.abc import Callable
from typing import Any

import httpx
from starlette.types import ASGIApp, Receive, Scope, Send

from fluxlit.config import FluxlitSettings
from fluxlit.gateway._log import gateway_log
from fluxlit.gateway.http_proxy import proxy_http
from fluxlit.gateway.metrics import get_gateway_prom_metrics
from fluxlit.gateway.options import gateway_opts
from fluxlit.gateway.paths import (
    location_under_mount,
    normalize_root_mount,
    split_gateway_paths,
    strip_prefix_scope,
)
from fluxlit.gateway.request_id import request_id_from_scope
from fluxlit.gateway.responses import (
    bad_streamlit_upstream_http,
    bad_streamlit_upstream_ws,
    not_found,
    redirect,
)
from fluxlit.gateway.websocket_proxy import proxy_websocket
from fluxlit.logging_context import reset_request_id, set_request_id
from fluxlit.logging_redact import DEFAULT_SENSITIVE_QUERY_KEYS, redact_query_string


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

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await api_app(scope, receive, send)
            return
        rid = request_id_from_scope(scope)
        token = set_request_id(rid)
        t0 = time.perf_counter()
        dispatch = "unknown"
        skip_prom_observe = False
        try:
            method_or_type = scope.get("method") or scope["type"]
            path_in = scope.get("path") or ""
            path, streamlit_path = split_gateway_paths(path_in, mount)
            is_api = path == prefix or path.startswith(f"{prefix}/")
            dispatch = "api" if is_api else "streamlit"
            if (
                prom_metrics
                and scope["type"] == "http"
                and str(scope.get("method", "GET")).upper() == "GET"
                and path == prom_path
            ):
                pc = importlib.import_module("prometheus_client")
                generate_latest = pc.generate_latest
                CONTENT_TYPE_LATEST = pc.CONTENT_TYPE_LATEST

                skip_prom_observe = True
                body = generate_latest()
                ct = CONTENT_TYPE_LATEST
                if isinstance(ct, str):
                    ct_b = ct.encode("ascii")
                else:
                    ct_b = ct
                await send(
                    {
                        "type": "http.response.start",
                        "status": 200,
                        "headers": [(b"content-type", ct_b)],
                    }
                )
                await send({"type": "http.response.body", "body": body})
                return
            qs_raw = scope.get("query_string", b"") or b""
            try:
                qs_dec = qs_raw.decode("latin-1")
            except Exception:
                qs_dec = ""
            log_extra = {
                "fluxlit_dispatch": dispatch,
                "http_method_or_type": method_or_type,
                "path": path_in,
                "query": redact_query_string(qs_dec, sensitive_keys=log_sensitive_query_keys),
            }
            log_msg = "gateway %s %s request_id=%s"
            log_args = (method_or_type, path_in, rid)
            if access_log:
                gateway_log.info(log_msg, *log_args, extra=log_extra)
            else:
                gateway_log.debug(log_msg, *log_args, extra=log_extra)
            if prom_metrics:
                mk = (
                    "WEBSOCKET"
                    if scope["type"] == "websocket"
                    else str(scope.get("method", "GET")).upper()
                )
                prom_metrics[0].labels(dispatch=dispatch, method_kind=mk).inc()
            if is_api:
                inner = dict(scope)
                inner["path"] = path
                inner["raw_path"] = path.encode("latin-1")
                api_scope = strip_prefix_scope(inner, prefix)
                await api_app(api_scope, receive, send)
                return
            upstream = resolve_upstream()
            if not upstream:
                if scope["type"] == "http":
                    await bad_streamlit_upstream_http(send)
                    return
                if scope["type"] == "websocket":
                    await bad_streamlit_upstream_ws(receive, send)
                    return
            if scope["type"] == "websocket":
                await proxy_websocket(
                    scope,
                    receive,
                    send,
                    upstream,
                    streamlit_path,
                    forwarded_prefix=mount or None,
                    request_id=rid,
                    proxy_options=opts,
                )
                return
            if scope["type"] == "http":
                method = scope.get("method", "GET").upper()
                if method in {"GET", "HEAD"}:
                    if path in {"/docs", "/docs/"}:
                        await redirect(send, location_under_mount(mount, f"{prefix}/docs"))
                        return
                    if path in {"/redoc", "/redoc/"}:
                        await redirect(send, location_under_mount(mount, f"{prefix}/redoc"))
                        return
                    if path in {"/openapi.json"}:
                        loc = location_under_mount(mount, f"{prefix}/openapi.json")
                        await redirect(send, loc)
                        return
                await proxy_http(
                    scope,
                    receive,
                    send,
                    upstream,
                    streamlit_path,
                    forwarded_prefix=mount or None,
                    request_id=rid,
                    proxy_options=opts,
                    httpx_client_getter=_shared_httpx_client,
                    upstream_sem=upstream_sem,
                )
                return
            await not_found(send)
        finally:
            if (
                prom_metrics
                and not skip_prom_observe
                and scope.get("type") in {"http", "websocket"}
            ):
                try:
                    prom_metrics[1].labels(dispatch=dispatch).observe(time.perf_counter() - t0)
                except Exception:  # noqa: S110
                    pass
            reset_request_id(token)

    return app
