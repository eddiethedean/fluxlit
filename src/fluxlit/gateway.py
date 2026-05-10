"""ASGI gateway: dispatch ``api_prefix`` to FastAPI, proxy everything else to Streamlit.

HTTP requests and WebSockets are forwarded to an upstream base URL (the Streamlit
server). Request IDs are taken from ``X-Request-ID`` or generated, and stored in
:mod:`fluxlit.logging_context` for the duration of each request.
"""

from __future__ import annotations

import logging
import urllib.parse
from collections.abc import AsyncIterator

import anyio
import httpx
import websockets
from starlette.types import ASGIApp, Receive, Scope, Send

from fluxlit.logging_context import (
    REQUEST_ID_HEADER,
    new_request_id,
    reset_request_id,
    set_request_id,
)

_gateway_log = logging.getLogger("fluxlit.gateway")


def _request_id_from_scope(scope: Scope) -> str:
    """Return the client ``X-Request-ID`` header value or a new UUID string."""
    raw = scope.get("headers") or []
    want = REQUEST_ID_HEADER.lower().encode("latin-1")
    for k, v in raw:
        if k.lower() == want:
            return v.decode("latin-1").strip() or new_request_id()
    return new_request_id()


def build_gateway(api_app: ASGIApp, upstream_base: str, *, api_prefix: str = "/api") -> ASGIApp:
    """Build the composite ASGI application used as Uvicorn's entrypoint.

    Routes whose path equals ``api_prefix`` or starts with ``api_prefix/`` are
    forwarded to ``api_app`` with that prefix stripped from ``path`` and ``raw_path``.
    All other HTTP traffic and WebSockets are reverse-proxied to ``upstream_base``
    (typically the internal Streamlit origin).

    Lifespan events are delegated only to ``api_app``.

    Args:
        api_app: Inner FastAPI / Starlette app (mount path not included in its routes).
        upstream_base: Base URL for Streamlit, e.g. ``http://127.0.0.1:8501``.
        api_prefix: Public URL prefix for the API (default ``/api``).

    Returns:
        A callable ASGI3 application.
    """
    upstream = upstream_base.rstrip("/")
    prefix = api_prefix.rstrip("/") or "/api"

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await api_app(scope, receive, send)
            return
        rid = _request_id_from_scope(scope)
        token = set_request_id(rid)
        try:
            method_or_type = scope.get("method") or scope["type"]
            path = scope.get("path") or ""
            _gateway_log.debug(
                "gateway %s %s request_id=%s",
                method_or_type,
                path,
                rid,
            )
            if path == prefix or path.startswith(f"{prefix}/"):
                api_scope = _strip_prefix_scope(scope, prefix)
                await api_app(api_scope, receive, send)
                return
            if scope["type"] == "websocket":
                await _proxy_websocket(scope, receive, send, upstream)
                return
            if scope["type"] == "http":
                await _proxy_http(scope, receive, send, upstream)
                return
            await _not_found(send)
        finally:
            reset_request_id(token)

    return app


def _strip_prefix_scope(scope: Scope, prefix: str) -> Scope:
    path = scope.get("path") or "/"
    rest = path.removeprefix(prefix) or "/"
    new_scope: Scope = dict(scope)
    new_scope["path"] = rest
    new_scope["raw_path"] = rest.encode("latin-1")
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


def _build_target_url(scope: Scope, upstream: str) -> str:
    path = scope.get("path") or "/"
    query = scope.get("query_string", b"").decode("latin-1")
    if query:
        return f"{upstream}{path}?{query}"
    return f"{upstream}{path}"


def _upstream_host_header(upstream: str) -> str:
    parsed = urllib.parse.urlparse(upstream)
    if parsed.port:
        return f"{parsed.hostname}:{parsed.port}"
    return parsed.hostname or "127.0.0.1"


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
    out: list[tuple[bytes, bytes]] = []
    for k, v in raw:
        kl = k.lower()
        if kl in hop_by_hop:
            continue
        if kl == b"host":
            continue
        out.append((k, v))
    return out


async def _proxy_http(scope: Scope, receive: Receive, send: Send, upstream: str) -> None:
    method = scope.get("method", "GET").upper()
    url = _build_target_url(scope, upstream)
    raw_headers = scope.get("headers") or []
    pairs = [
        (k.decode("latin-1"), v.decode("latin-1")) for k, v in _filter_request_headers(raw_headers)
    ]
    headers = httpx.Headers(pairs)
    headers["host"] = _upstream_host_header(upstream)

    async def request_body() -> AsyncIterator[bytes]:
        while True:
            message = await receive()
            if message["type"] == "http.request":
                chunk = message.get("body", b"")
                if chunk:
                    yield chunk
                if not message.get("more_body", False):
                    break
            else:
                break

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            req = client.build_request(method, url, headers=headers, content=request_body())
            response = await client.send(req, stream=True)
    except httpx.RequestError:
        await send(
            {
                "type": "http.response.start",
                "status": 502,
                "headers": [(b"content-type", b"text/plain; charset=utf-8")],
            }
        )
        await send({"type": "http.response.body", "body": b"Bad Gateway"})
        return

    try:
        response_headers = [
            (k.lower().encode("latin-1"), v.encode("latin-1"))
            for k, v in response.headers.multi_items()
            if k.lower() not in {"transfer-encoding", "connection"}
        ]
        await send(
            {
                "type": "http.response.start",
                "status": response.status_code,
                "headers": response_headers,
            }
        )
        try:
            async for chunk in response.aiter_raw():
                await send({"type": "http.response.body", "body": chunk, "more_body": True})
            await send({"type": "http.response.body", "body": b""})
        except Exception:
            _gateway_log.exception("gateway proxy: error streaming response body from upstream")
            raise
    finally:
        await response.aclose()


def _parse_ws_target(scope: Scope, upstream: str) -> str:
    path = scope.get("path") or "/"
    qs = scope.get("query_string", b"")
    if qs:
        path = f"{path}?{qs.decode('latin-1')}"
    parsed = urllib.parse.urlparse(upstream)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port
    netloc = f"{host}:{port}" if port else host
    base_path = parsed.path.rstrip("/")
    full_path = f"{base_path}{path}" if base_path else path
    return str(urllib.parse.urlunparse((scheme, netloc, full_path, "", "", "")))


async def _proxy_websocket(scope: Scope, receive: Receive, send: Send, upstream: str) -> None:
    first = await receive()
    if first["type"] != "websocket.connect":
        await send({"type": "websocket.close", "code": 1002})
        return

    target = _parse_ws_target(scope, upstream)
    headers = scope.get("headers") or []
    extra: list[tuple[str, str]] = []
    for k, v in headers:
        key = k.decode("latin-1")
        lk = key.lower()
        if lk in {"host", "connection", "upgrade", "sec-websocket-key", "sec-websocket-version"}:
            continue
        extra.append((key, v.decode("latin-1")))

    try:
        async with websockets.connect(
            target,
            additional_headers=extra,
            max_size=None,
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
    except (OSError, websockets.InvalidURI, websockets.InvalidHandshake):
        await send({"type": "websocket.close", "code": 1011})
