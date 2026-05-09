from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from fluxlit.gateway import (
    _build_target_url,
    _filter_request_headers,
    _not_found,
    _parse_ws_target,
    _request_id_from_scope,
    _strip_prefix_scope,
    _upstream_host_header,
    build_gateway,
)


def test_build_target_url_with_query() -> None:
    scope: dict[str, Any] = {"path": "/foo", "query_string": b"a=1&b=2"}
    assert _build_target_url(scope, "http://127.0.0.1:9") == "http://127.0.0.1:9/foo?a=1&b=2"


def test_build_target_url_without_query() -> None:
    scope: dict[str, Any] = {"path": "/bar", "query_string": b""}
    assert _build_target_url(scope, "http://h") == "http://h/bar"


def test_upstream_host_header_with_port() -> None:
    assert _upstream_host_header("http://127.0.0.1:8501") == "127.0.0.1:8501"


def test_upstream_host_header_default_host_when_no_netloc() -> None:
    assert _upstream_host_header("http:///path-only") in {"127.0.0.1", "localhost"}


def test_filter_request_headers_strips_hop_by_hop_and_host() -> None:
    raw = [
        (b"Host", b"client.example"),
        (b"Connection", b"keep-alive"),
        (b"X-Custom", b"1"),
    ]
    out = _filter_request_headers(raw)
    assert out == [(b"X-Custom", b"1")]


def test_parse_ws_target_https_and_base_path() -> None:
    scope: dict[str, Any] = {"path": "/_stcore/stream", "query_string": b"x=1"}
    url = _parse_ws_target(scope, "https://example.com/prefix/")
    assert url.startswith("wss://")
    assert "/prefix/_stcore/stream" in url
    assert "x=1" in url


def test_parse_ws_target_ws_without_port() -> None:
    scope: dict[str, Any] = {"path": "/", "query_string": b""}
    url = _parse_ws_target(scope, "http://10.0.0.5")
    assert url.startswith("ws://10.0.0.5/")


def test_strip_prefix_scope_normalizes_raw_path() -> None:
    scope: dict[str, Any] = {
        "type": "http",
        "path": "/api/v1/ping",
        "raw_path": b"/api/v1/ping",
        "headers": [],
    }
    new_scope = _strip_prefix_scope(scope, "/api")  # type: ignore[arg-type]
    assert new_scope["path"] == "/v1/ping"
    assert new_scope["raw_path"] == b"/v1/ping"


def test_request_id_from_scope_header_or_generated() -> None:
    scope_gen: dict[str, Any] = {"headers": []}
    rid1 = _request_id_from_scope(scope_gen)  # type: ignore[arg-type]
    assert len(rid1) >= 32

    scope_hdr: dict[str, Any] = {
        "headers": [(b"x-request-id", b"  fixed  ")],
    }
    assert _request_id_from_scope(scope_hdr) == "fixed"  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_not_found_sends_404() -> None:
    messages: list[dict[str, Any]] = []

    async def send(msg: dict[str, Any]) -> None:
        messages.append(msg)

    await _not_found(send)
    assert messages[0]["type"] == "http.response.start"
    assert messages[0]["status"] == 404
    assert messages[1]["body"] == b"Not Found"


@pytest.mark.asyncio
async def test_gateway_unknown_scope_type_is_404() -> None:
    gateway = build_gateway(FastAPI(), "http://127.0.0.1:9", api_prefix="/api")
    sent: list[dict[str, Any]] = []

    async def send(msg: dict[str, Any]) -> None:
        sent.append(msg)

    async def receive() -> dict[str, Any]:
        return {"type": "http.disconnect"}

    scope: dict[str, Any] = {
        "type": "lifespan-not-this",
        "path": "/anything",
        "headers": [],
    }
    await gateway(scope, receive, send)  # type: ignore[arg-type]
    assert sent[0]["status"] == 404


def test_websocket_proxy_upstream_refused_closes() -> None:
    gateway = build_gateway(FastAPI(), "http://127.0.0.1:9", api_prefix="/api")
    with TestClient(gateway) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/_stcore/ws"):
                pass
