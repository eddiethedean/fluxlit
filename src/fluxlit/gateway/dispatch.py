"""Gateway request dispatch: API vs Streamlit, metrics, docs redirects, access logs."""

from __future__ import annotations

import asyncio
import importlib
import json
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from starlette.types import ASGIApp, Receive, Scope, Send

from fluxlit.gateway._log import gateway_log
from fluxlit.gateway.contracts import GatewayPromCounter, GatewayPromHistogram
from fluxlit.gateway.http_proxy import proxy_http
from fluxlit.gateway.options import GatewayProxyOptions
from fluxlit.gateway.paths import (
    location_under_mount,
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
from fluxlit.logging import redact_query_string, reset_request_id, set_request_id
from fluxlit.tracing import trace_span


def make_gateway_app(
    *,
    api_app: ASGIApp,
    resolve_upstream: Callable[[], str],
    prefix: str,
    mount: str,
    opts: GatewayProxyOptions,
    upstream_sem: asyncio.Semaphore | None,
    shared_httpx_client: Callable[[], Awaitable[httpx.AsyncClient]],
    prom_metrics: tuple[GatewayPromCounter, GatewayPromHistogram] | None,
    prom_path: str,
    access_log: bool,
    log_sensitive_query_keys: frozenset[str],
    debug_mode: bool = False,
    debug_snapshot: dict[str, Any] | None = None,
    debug_path: str = "/__fluxlit/debug",
) -> ASGIApp:
    """Return the ASGI handler for HTTP/WebSocket (not lifespan)."""

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
            if debug_mode:
                from fluxlit.gateway.debug_ring import record_gateway_dispatch

                record_gateway_dispatch(request_id=rid, dispatch=dispatch, path_in=path_in)
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
                await send({"type": "http.response.body", "body": body, "more_body": False})
                return
            if (
                scope["type"] == "http"
                and str(scope.get("method", "GET")).upper() == "GET"
                and path == debug_path
            ):
                skip_prom_observe = True
                if not debug_mode or debug_snapshot is None:
                    await not_found(send)
                    return
                from fluxlit.gateway.debug_ring import recent_gateway_dispatches

                payload = dict(debug_snapshot)
                payload["recent_dispatches"] = recent_gateway_dispatches()
                body = json.dumps(payload, default=str).encode("utf-8")
                await send(
                    {
                        "type": "http.response.start",
                        "status": 200,
                        "headers": [(b"content-type", b"application/json; charset=utf-8")],
                    }
                )
                await send({"type": "http.response.body", "body": body, "more_body": False})
                return
            qs_raw = scope.get("query_string", b"") or b""
            try:
                qs_dec = qs_raw.decode("latin-1")
            except Exception:
                qs_dec = ""
            log_extra = {
                "request_id": rid,
                "fluxlit_dispatch": dispatch,
                "http_method_or_type": method_or_type,
                "path": path_in,
                "query": redact_query_string(qs_dec, sensitive_keys=log_sensitive_query_keys),
            }
            if debug_mode:
                gateway_log.debug(
                    "fluxlit debug split path_in=%r mount=%r api_path=%r streamlit_path=%r",
                    path_in,
                    mount,
                    path,
                    streamlit_path,
                )
            log_msg = "gateway %s %s request_id=%s"
            log_args = (method_or_type, path_in, rid)
            if access_log:
                gateway_log.info(log_msg, *log_args, extra=log_extra)
            else:
                gateway_log.debug(log_msg, *log_args, extra=log_extra)
            attrs = {
                "fluxlit.dispatch": dispatch,
                "http.method_or_type": str(method_or_type),
                "url.path": path_in,
                "request_id": rid,
            }
            with trace_span("fluxlit.gateway.request", attrs):
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
                        httpx_client_getter=shared_httpx_client,
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
                except Exception as exc:
                    gateway_log.debug(
                        "gateway_prometheus_observe_failed dispatch=%s err=%s",
                        dispatch,
                        type(exc).__name__,
                        exc_info=True,
                    )
            reset_request_id(token)

    return app
