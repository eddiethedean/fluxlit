from __future__ import annotations

import urllib.parse
from collections.abc import AsyncIterator
from typing import cast

import anyio
import httpx
import websockets
from starlette.types import ASGIApp, Receive, Scope, Send


def build_gateway(api_app: ASGIApp, upstream_base: str, *, api_prefix: str = "/api") -> ASGIApp:
    """ASGI app: forwards `api_prefix` to `api_app`.

    Everything else is proxied to `upstream_base` (Streamlit).
    """
    upstream = upstream_base.rstrip("/")
    prefix = api_prefix.rstrip("/") or "/api"

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await api_app(scope, receive, send)
            return
        path = scope.get("path") or ""
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

    return app


def _strip_prefix_scope(scope: Scope, prefix: str) -> Scope:
    path = scope.get("path") or "/"
    rest = path.removeprefix(prefix) or "/"
    new_scope: Scope = dict(scope)
    new_scope["path"] = rest
    new_scope["raw_path"] = rest.encode("ascii")
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
    async for chunk in response.aiter_raw():
        await send({"type": "http.response.body", "body": chunk, "more_body": True})
    await send({"type": "http.response.body", "body": b""})


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
    return cast(str, urllib.parse.urlunparse((scheme, netloc, full_path, "", "", "")))


async def _proxy_websocket(scope: Scope, receive: Receive, send: Send, upstream: str) -> None:
    first = await receive()
    if first["type"] != "websocket.connect":
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
