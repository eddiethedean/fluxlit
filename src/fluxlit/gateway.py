"""ASGI gateway: dispatch ``api_prefix`` to FastAPI, proxy everything else to Streamlit.

HTTP requests and WebSockets are forwarded to an upstream base URL (the Streamlit
server). The client's ``Host`` header is preserved on the upstream request so
Streamlit sees the **public** gateway host/port (e.g. ``127.0.0.1:8777``), matching
the browser's ``Origin``; otherwise WebSocket same-origin checks fail and the UI
stays blank/black.

Request IDs are taken from ``X-Request-ID`` or generated, stored in
:mod:`fluxlit.logging_context` for the duration of each request, and **re-sent to
Streamlit** on proxied HTTP and WebSocket hops as authoritative ``X-Request-ID`` (the
gateway wins over any client-supplied value on that upstream leg).

Top-level ``/docs``, ``/redoc``, and ``/openapi.json`` redirect to the same paths under
``api_prefix`` so Swagger is not accidentally proxied to Streamlit (which would look
like a blank page).
"""

from __future__ import annotations

import asyncio
import logging
import urllib.parse
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any, cast

import anyio
import httpx
import websockets
from starlette.types import ASGIApp, Receive, Scope, Send

from fluxlit.config import FluxlitSettings
from fluxlit.logging_context import (
    REQUEST_ID_HEADER,
    new_request_id,
    reset_request_id,
    set_request_id,
)

_gateway_log = logging.getLogger("fluxlit.gateway")


@dataclass(frozen=True)
class GatewayProxyOptions:
    """Upstream HTTP/WebSocket tuning for :func:`build_gateway`.

    Mirrors :class:`~fluxlit.config.FluxlitSettings` gateway fields.
    """

    connect_timeout: float = 30.0
    read_timeout: float = 120.0
    max_proxy_body_bytes: int = 0
    max_concurrent_upstream_http: int = 0
    httpx_max_connections: int = 0
    httpx_max_keepalive_connections: int = 0
    ws_open_timeout_s: float = 30.0
    ws_ping_interval_s: float | None = None
    ws_ping_timeout_s: float | None = None
    ws_close_timeout_s: float | None = None
    ws_max_message_bytes: int | None = None


def _gateway_opts(fluxlit_settings: FluxlitSettings | None) -> GatewayProxyOptions:
    if fluxlit_settings is None:
        return GatewayProxyOptions()
    fs = fluxlit_settings
    return GatewayProxyOptions(
        connect_timeout=fs.gateway_upstream_connect_timeout_s,
        read_timeout=fs.gateway_upstream_read_timeout_s,
        max_proxy_body_bytes=fs.gateway_max_proxy_request_body_bytes,
        max_concurrent_upstream_http=fs.gateway_max_concurrent_upstream_http,
        httpx_max_connections=fs.gateway_httpx_max_connections,
        httpx_max_keepalive_connections=fs.gateway_httpx_max_keepalive_connections,
        ws_open_timeout_s=fs.gateway_ws_open_timeout_s,
        ws_ping_interval_s=fs.gateway_ws_ping_interval_s,
        ws_ping_timeout_s=fs.gateway_ws_ping_timeout_s,
        ws_close_timeout_s=fs.gateway_ws_close_timeout_s,
        ws_max_message_bytes=fs.gateway_ws_max_message_bytes,
    )


def normalize_root_mount(raw: str) -> str:
    """Normalize a public URL prefix (e.g. Posit Connect content path) for routing.

    Returns ``""`` when unset, otherwise a path starting with ``/`` and no trailing
    slash (except root ``"/"`` is not used — empty means no mount).
    """
    s = (raw or "").strip()
    if not s:
        return ""
    if not s.startswith("/"):
        s = f"/{s}"
    return s.rstrip("/") or ""


def split_gateway_paths(path: str, root_mount: str) -> tuple[str, str]:
    """Split the ASGI path for dispatch vs Streamlit upstream.

    Some reverse proxies forward the **full** public path (``/content/123/api/...``).
    Others strip the mount and only forward the suffix (``/api/...``) while setting
    ASGI ``root_path``. :func:`normalize_root_mount` should match the browser-visible
    prefix configured for Streamlit ``server.baseUrlPath``.

    Returns:
        ``(dispatch_path, streamlit_path)`` — use *dispatch_path* to choose API vs
        Streamlit; send *streamlit_path* to the Streamlit sidecar when proxying.
    """
    m = normalize_root_mount(root_mount)
    p = path if path.startswith("/") else f"/{path}"
    if not m:
        return p, p
    if p == m or p.startswith(f"{m}/"):
        rest = "/" if p == m else p[len(m) :]
        if not rest.startswith("/"):
            rest = f"/{rest}"
        return rest, p
    return p, f"{m}{p}"


def _request_id_from_scope(scope: Scope) -> str:
    """Return the client ``X-Request-ID`` header value or a new UUID string."""
    raw = scope.get("headers") or []
    want = REQUEST_ID_HEADER.lower().encode("latin-1")
    for k, v in raw:
        if k.lower() == want:
            return v.decode("latin-1").strip() or new_request_id()
    return new_request_id()


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
    opts = _gateway_opts(proxy_settings)
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

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await api_app(scope, receive, send)
            return
        rid = _request_id_from_scope(scope)
        token = set_request_id(rid)
        try:
            method_or_type = scope.get("method") or scope["type"]
            path_in = scope.get("path") or ""
            path, streamlit_path = split_gateway_paths(path_in, mount)
            is_api = path == prefix or path.startswith(f"{prefix}/")
            dispatch = "api" if is_api else "streamlit"
            log_extra = {
                "fluxlit_dispatch": dispatch,
                "http_method_or_type": method_or_type,
                "path": path_in,
            }
            log_msg = "gateway %s %s request_id=%s"
            log_args = (method_or_type, path_in, rid)
            if access_log:
                _gateway_log.info(log_msg, *log_args, extra=log_extra)
            else:
                _gateway_log.debug(log_msg, *log_args, extra=log_extra)
            if is_api:
                inner = dict(scope)
                inner["path"] = path
                inner["raw_path"] = path.encode("latin-1")
                api_scope = _strip_prefix_scope(inner, prefix)
                await api_app(api_scope, receive, send)
                return
            upstream = resolve_upstream()
            if not upstream:
                if scope["type"] == "http":
                    await _bad_streamlit_upstream_http(send)
                    return
                if scope["type"] == "websocket":
                    await _bad_streamlit_upstream_ws(receive, send)
                    return
            if scope["type"] == "websocket":
                await _proxy_websocket(
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
                        await _redirect(send, _location_under_mount(mount, f"{prefix}/docs"))
                        return
                    if path in {"/redoc", "/redoc/"}:
                        await _redirect(send, _location_under_mount(mount, f"{prefix}/redoc"))
                        return
                    if path in {"/openapi.json"}:
                        loc = _location_under_mount(mount, f"{prefix}/openapi.json")
                        await _redirect(send, loc)
                        return
                await _proxy_http(
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
            await _not_found(send)
        finally:
            reset_request_id(token)

    return app


def _location_under_mount(mount: str, suffix: str) -> str:
    """Build a root-absolute Location (``/app/api/docs``) when mounted under ``/app``."""
    m = normalize_root_mount(mount)
    s = suffix if suffix.startswith("/") else f"/{suffix}"
    return f"{m}{s}" if m else s


def _strip_prefix_scope(scope: Scope, prefix: str) -> Scope:
    """Strip ``prefix`` from the URL path and extend ``root_path`` (ASGI).

    FastAPI's Swagger / ReDoc handlers build ``openapi_url`` as
    ``scope["root_path"] + app.openapi_url``. Without setting ``root_path`` to the
    gateway's API mount (e.g. ``/api``), the embedded URL is ``/openapi.json``; the
    browser then requests the **gateway** root, which is proxied to Streamlit — not
    JSON — and Swagger UI reports a missing OpenAPI version.
    """
    path = scope.get("path") or "/"
    rest = path.removeprefix(prefix) or "/"
    new_scope: Scope = dict(scope)
    new_scope["path"] = rest
    new_scope["raw_path"] = rest.encode("latin-1")
    prior = (scope.get("root_path") or "").rstrip("/")
    mount = prefix.rstrip("/")
    new_scope["root_path"] = f"{prior}{mount}" if prior else mount
    return new_scope


async def _not_found(send: Send) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 404,
            "headers": [(b"content-type", b"text/plain; charset=utf-8")],
        }
    )
    await send({"type": "http.response.body", "body": b"Not Found"})


async def _redirect(send: Send, location: str, *, status: int = 307) -> None:
    """Send a redirect; default 307 so the client keeps the same method (GET/HEAD)."""
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"location", location.encode("ascii")),
                (b"content-length", b"0"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": b""})


_BAD_UPSTREAM_BODY = (
    b"FluxLit: Streamlit upstream URL is missing "
    b"(set FLUXLIT_STREAMLIT_UPSTREAM or fix FLUXLIT_STREAMLIT_UPSTREAM_FILE)."
)


async def _bad_streamlit_upstream_http(send: Send) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 502,
            "headers": [(b"content-type", b"text/plain; charset=utf-8")],
        }
    )
    await send({"type": "http.response.body", "body": _BAD_UPSTREAM_BODY})


async def _bad_streamlit_upstream_ws(receive: Receive, send: Send) -> None:
    """Close the socket when no upstream base URL is available."""
    while True:
        msg = await receive()
        if msg["type"] == "websocket.connect":
            await send(
                {
                    "type": "websocket.close",
                    "code": 1011,
                    "reason": b"Streamlit upstream missing",
                }
            )
            return
        if msg["type"] == "websocket.disconnect":
            return


def _build_target_url(scope: Scope, upstream: str, *, path: str | None = None) -> str:
    use_path = path if path is not None else (scope.get("path") or "/")
    query = scope.get("query_string", b"").decode("latin-1")
    if query:
        return f"{upstream}{use_path}?{query}"
    return f"{upstream}{use_path}"


def _upstream_host_header(upstream: str) -> str:
    parsed = urllib.parse.urlparse(upstream)
    if parsed.port:
        return f"{parsed.hostname}:{parsed.port}"
    return parsed.hostname or "127.0.0.1"


def _public_host_from_scope(scope: Scope, upstream: str) -> str:
    """Host header the browser used (gateway); fallback to upstream netloc."""
    for k, v in scope.get("headers") or []:
        if k.lower() == b"host":
            return v.decode("latin-1").strip() or _upstream_host_header(upstream)
    return _upstream_host_header(upstream)


def _port_from_host_header(host_val: str) -> int | None:
    """Parse a port from ``Host`` (supports ``[ipv6]:port``)."""
    if host_val.startswith("["):
        if "]:" in host_val:
            rest = host_val.split("]:", 1)[1]
            return int(rest) if rest.isdigit() else None
        return None
    if ":" in host_val:
        maybe_port = host_val.rsplit(":", 1)[1]
        if maybe_port.isdigit():
            return int(maybe_port)
    return None


def _forwarded_upstream_header_pairs(
    scope: Scope,
    public_host: str,
    *,
    forwarded_prefix: str | None = None,
) -> list[tuple[str, str]]:
    """Headers that describe the client-facing URL (for servers that read ``X-Forwarded-*``)."""
    proto = scope.get("scheme") or "http"
    pairs: list[tuple[str, str]] = [
        ("X-Forwarded-Host", public_host),
        ("X-Forwarded-Proto", proto),
    ]
    port = _port_from_host_header(public_host)
    if port is not None:
        pairs.append(("X-Forwarded-Port", str(port)))
    if forwarded_prefix:
        pairs.append(("X-Forwarded-Prefix", forwarded_prefix))
    client = scope.get("client")
    if isinstance(client, (list, tuple)) and len(client) >= 1 and client[0]:
        pairs.append(("X-Forwarded-For", client[0]))
    return pairs


def _filter_request_headers(raw: list[tuple[bytes, bytes]]) -> list[tuple[bytes, bytes]]:
    hop_by_hop = {
        b"connection",
        b"keep-alive",
        b"proxy-authenticate",
        b"proxy-authorization",
        b"te",
        b"trailers",
        b"transfer-encoding",
        b"upgrade",
    }
    # Drop client-supplied forwarding headers; the gateway sets authoritative values.
    strip = hop_by_hop | {
        b"x-forwarded-for",
        b"x-forwarded-host",
        b"x-forwarded-proto",
        b"x-forwarded-port",
        b"x-forwarded-prefix",
    }
    out: list[tuple[bytes, bytes]] = []
    for k, v in raw:
        kl = k.lower()
        if kl in strip:
            continue
        if kl == b"host":
            continue
        out.append((k, v))
    return out


class _GatewayPayloadTooLarge(Exception):
    """Internal: proxied request body exceeded configured max bytes."""


async def _respond_413_payload_too_large(send: Send) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [(b"content-type", b"text/plain; charset=utf-8")],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": b"Payload Too Large",
            "more_body": False,
        }
    )


async def _proxy_http(
    scope: Scope,
    receive: Receive,
    send: Send,
    upstream: str,
    streamlit_path: str,
    *,
    forwarded_prefix: str | None = None,
    request_id: str,
    proxy_options: GatewayProxyOptions,
    httpx_client_getter: Callable[[], Awaitable[httpx.AsyncClient]],
    upstream_sem: asyncio.Semaphore | None,
) -> None:
    async def _guarded() -> None:
        await _proxy_http_inner(
            scope,
            receive,
            send,
            upstream,
            streamlit_path,
            forwarded_prefix=forwarded_prefix,
            request_id=request_id,
            proxy_options=proxy_options,
            httpx_client_getter=httpx_client_getter,
        )

    if upstream_sem is not None:
        async with upstream_sem:
            await _guarded()
    else:
        await _guarded()


async def _proxy_http_inner(
    scope: Scope,
    receive: Receive,
    send: Send,
    upstream: str,
    streamlit_path: str,
    *,
    forwarded_prefix: str | None,
    request_id: str,
    proxy_options: GatewayProxyOptions,
    httpx_client_getter: Callable[[], Awaitable[httpx.AsyncClient]],
) -> None:
    method = scope.get("method", "GET").upper()
    url = _build_target_url(scope, upstream, path=streamlit_path)
    raw_headers = scope.get("headers") or []
    rid_lc = REQUEST_ID_HEADER.lower()
    pairs: list[tuple[str, str]] = []
    for k, v in _filter_request_headers(raw_headers):
        kk = k.decode("latin-1")
        if kk.lower() == rid_lc:
            continue
        pairs.append((kk, v.decode("latin-1")))
    headers = httpx.Headers(pairs)
    public_host = _public_host_from_scope(scope, upstream)
    headers["host"] = public_host
    for hk, hv in _forwarded_upstream_header_pairs(
        scope, public_host, forwarded_prefix=forwarded_prefix
    ):
        headers[hk] = hv
    headers[REQUEST_ID_HEADER] = request_id

    max_body = proxy_options.max_proxy_body_bytes

    async def request_body() -> AsyncIterator[bytes]:
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.request":
                chunk = message.get("body", b"")
                if chunk:
                    total += len(chunk)
                    if max_body and total > max_body:
                        raise _GatewayPayloadTooLarge
                    yield chunk
                if not message.get("more_body", False):
                    break
            else:
                break

    async def drain_incoming_request_body() -> None:
        """Consume the ASGI request body before opening the upstream call.

        When the gateway runs inside another ASGI caller (tests, nested clients), unread
        ``http.request`` events share the same event loop with ``httpx``'s connection to
        Streamlit; deferring ``receive()`` until after the upstream stream starts can
        trigger premature ``ReadError`` on the upstream socket (empty HTML to browsers).
        """
        total = 0
        while True:
            message = await receive()
            if message["type"] != "http.request":
                break
            chunk = message.get("body", b"")
            total += len(chunk)
            if max_body and total > max_body:
                raise _GatewayPayloadTooLarge
            if not message.get("more_body", False):
                break

    response: httpx.Response | None = None
    try:
        client = await httpx_client_getter()
        if method in {"GET", "HEAD"}:
            await drain_incoming_request_body()
            req = client.build_request(method, url, headers=headers)
        else:
            req = client.build_request(method, url, headers=headers, content=request_body())
        response = await client.send(req, stream=False)
    except _GatewayPayloadTooLarge:
        await _respond_413_payload_too_large(send)
        return
    except httpx.RequestError as exc:
        _gateway_log.warning(
            "gateway upstream HTTP error for %s request_id=%s: %s", url, request_id, exc
        )
        await send(
            {
                "type": "http.response.start",
                "status": 502,
                "headers": [(b"content-type", b"text/plain; charset=utf-8")],
            }
        )
        await send({"type": "http.response.body", "body": b"Bad Gateway", "more_body": False})
        return

    assert response is not None
    try:
        out_body = b"" if method == "HEAD" else response.content
        _skip_resp_hdr = frozenset(
            {"transfer-encoding", "connection", "content-encoding", "content-length"}
        )
        response_headers = [
            (k.lower().encode("latin-1"), v.encode("latin-1"))
            for k, v in response.headers.multi_items()
            if k.lower() not in _skip_resp_hdr
        ]
        response_headers.append((b"content-length", str(len(out_body)).encode("latin-1")))
        await send(
            {
                "type": "http.response.start",
                "status": response.status_code,
                "headers": response_headers,
            }
        )
        try:
            await send({"type": "http.response.body", "body": out_body, "more_body": False})
        except Exception:  # noqa: BLE001 — log then re-raise; ASGI send can fail for many reasons
            _gateway_log.exception("gateway proxy: error building response body from upstream")
            raise
    finally:
        await response.aclose()


def _parse_ws_target(scope: Scope, upstream: str, *, path: str | None = None) -> str:
    use_path = path if path is not None else (scope.get("path") or "/")
    qs = scope.get("query_string", b"")
    if qs:
        use_path = f"{use_path}?{qs.decode('latin-1')}"
    parsed = urllib.parse.urlparse(upstream)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port
    netloc = f"{host}:{port}" if port else host
    base_path = parsed.path.rstrip("/")
    full_path = f"{base_path}{use_path}" if base_path else use_path
    return str(urllib.parse.urlunparse((scheme, netloc, full_path, "", "", "")))


async def _proxy_websocket(
    scope: Scope,
    receive: Receive,
    send: Send,
    upstream: str,
    streamlit_path: str,
    *,
    forwarded_prefix: str | None = None,
    request_id: str,
    proxy_options: GatewayProxyOptions,
) -> None:
    first = await receive()
    if first["type"] != "websocket.connect":
        await send({"type": "websocket.close", "code": 1002})
        return

    target = _parse_ws_target(scope, upstream, path=streamlit_path)
    headers = scope.get("headers") or []
    public_host = _public_host_from_scope(scope, upstream)
    extra: list[tuple[str, str]] = [("Host", public_host)]
    extra.extend(
        _forwarded_upstream_header_pairs(scope, public_host, forwarded_prefix=forwarded_prefix)
    )
    skip_ws = {
        "host",
        "connection",
        "upgrade",
        "sec-websocket-key",
        "sec-websocket-version",
        # Negotiate extensions only on this hop. Forwarding the browser's
        # Sec-WebSocket-Extensions while this client also adds permessage-deflate breaks
        # the upstream handshake (endless "Connecting" / WS 403). Streamlit's
        # Sec-WebSocket-Protocol line (XSRF + session) is forwarded as-is from the client.
        "sec-websocket-extensions",
        "x-forwarded-for",
        "x-forwarded-host",
        "x-forwarded-proto",
        "x-forwarded-port",
        "x-request-id",
    }
    for k, v in headers:
        key = k.decode("latin-1")
        lk = key.lower()
        if lk in skip_ws:
            continue
        extra.append((key, v.decode("latin-1")))
    extra.append(("X-Request-ID", request_id))

    ws_connect_kw: dict[str, Any] = {"open_timeout": proxy_options.ws_open_timeout_s}
    if proxy_options.ws_max_message_bytes is not None:
        ws_connect_kw["max_size"] = proxy_options.ws_max_message_bytes
    if proxy_options.ws_ping_interval_s is not None:
        ws_connect_kw["ping_interval"] = proxy_options.ws_ping_interval_s
    if proxy_options.ws_ping_timeout_s is not None:
        ws_connect_kw["ping_timeout"] = proxy_options.ws_ping_timeout_s
    if proxy_options.ws_close_timeout_s is not None:
        ws_connect_kw["close_timeout"] = proxy_options.ws_close_timeout_s

    try:
        # Streamlit responds with ``Sec-WebSocket-Protocol: streamlit``. The ``websockets``
        # client requires ``subprotocols=[...]`` whenever the server picks a subprotocol;
        # we still merge *additional_headers* after building the request, so the browser's
        # full ``streamlit, <xsrf>, <session>`` line is sent on the wire.
        async with websockets.connect(
            target,
            additional_headers=extra,
            subprotocols=cast(Any, ["streamlit"]),
            **ws_connect_kw,
        ) as upstream_ws:
            subprotocols = scope.get("subprotocols") or []
            accepted = upstream_ws.subprotocol
            if accepted and accepted in subprotocols:
                await send({"type": "websocket.accept", "subprotocol": accepted})
            else:
                await send({"type": "websocket.accept"})

            async with anyio.create_task_group() as tg:

                async def client_to_upstream() -> None:
                    while True:
                        message = await receive()
                        mtype = message["type"]
                        if mtype == "websocket.receive":
                            if message.get("bytes") is not None:
                                await upstream_ws.send(message["bytes"])
                            elif message.get("text") is not None:
                                await upstream_ws.send(message["text"])
                        elif mtype == "websocket.disconnect":
                            with anyio.move_on_after(0.1):
                                await upstream_ws.close()
                            tg.cancel_scope.cancel()
                            return

                async def upstream_to_client() -> None:
                    try:
                        while True:
                            msg = await upstream_ws.recv()
                            if isinstance(msg, bytes):
                                await send({"type": "websocket.send", "bytes": msg})
                            else:
                                await send({"type": "websocket.send", "text": msg})
                    except websockets.ConnectionClosed:
                        tg.cancel_scope.cancel()

                tg.start_soon(client_to_upstream)
                tg.start_soon(upstream_to_client)
    except (
        OSError,
        websockets.InvalidURI,
        websockets.InvalidHandshake,
        websockets.NegotiationError,
    ) as exc:
        _gateway_log.warning("gateway websocket upstream failed: %s", exc)
        await send({"type": "websocket.close", "code": 1011})
