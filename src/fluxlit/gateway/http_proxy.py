"""HTTP reverse proxy from ASGI to Streamlit upstream (httpx)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable

import httpx
from starlette.types import Receive, Scope, Send

from fluxlit.gateway._log import gateway_log
from fluxlit.gateway.header_filter import filter_request_headers
from fluxlit.gateway.options import GatewayProxyOptions
from fluxlit.gateway.responses import respond_413_payload_too_large
from fluxlit.gateway.upstream_http import (
    build_target_url,
    forwarded_upstream_header_pairs,
    public_host_from_scope,
)
from fluxlit.logging import REQUEST_ID_HEADER


class _GatewayPayloadTooLarge(Exception):
    """Internal: proxied request body exceeded configured max bytes."""


async def proxy_http(
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
        await proxy_http_inner(
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


async def proxy_http_inner(
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
    url = build_target_url(scope, upstream, path=streamlit_path)
    raw_headers = scope.get("headers") or []
    rid_lc = REQUEST_ID_HEADER.lower()
    pairs: list[tuple[str, str]] = []
    for k, v in filter_request_headers(raw_headers):
        kk = k.decode("latin-1")
        if kk.lower() == rid_lc:
            continue
        pairs.append((kk, v.decode("latin-1")))
    headers = httpx.Headers(pairs)
    public_host = public_host_from_scope(scope, upstream)
    headers["host"] = public_host
    for hk, hv in forwarded_upstream_header_pairs(
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

    async def collect_limited_request_body() -> bytes:
        """Buffer a limited request body before contacting the upstream.

        When a maximum body size is configured, fail closed before opening a Streamlit
        upstream connection. This avoids sending a partial oversized request and then
        closing the socket once the limit is discovered.
        """
        chunks: list[bytes] = []
        total = 0
        while True:
            message = await receive()
            if message["type"] != "http.request":
                break
            chunk = message.get("body", b"")
            if chunk:
                total += len(chunk)
                if total > max_body:
                    raise _GatewayPayloadTooLarge
                chunks.append(chunk)
            if not message.get("more_body", False):
                break
        return b"".join(chunks)

    response: httpx.Response | None = None
    try:
        if method in {"GET", "HEAD"}:
            await drain_incoming_request_body()
            content: bytes | AsyncIterator[bytes] | None = None
        elif max_body:
            content = await collect_limited_request_body()
        else:
            content = request_body()

        client = await httpx_client_getter()
        if method in {"GET", "HEAD"}:
            req = client.build_request(method, url, headers=headers)
        else:
            req = client.build_request(method, url, headers=headers, content=content)
        response = await client.send(req, stream=False)
    except _GatewayPayloadTooLarge:
        await respond_413_payload_too_large(send)
        return
    except httpx.RequestError as exc:
        gateway_log.warning(
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
            gateway_log.exception("gateway proxy: error building response body from upstream")
            raise
    finally:
        await response.aclose()


# Test and advanced call sites historically imported ``_proxy_http``.
_proxy_http = proxy_http
