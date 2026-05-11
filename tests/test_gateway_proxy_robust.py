"""Extra gateway proxy tests: settings mapping, HTTP error subclasses, WS connect kwargs."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, cast

import httpx
import pytest
import websockets
from websockets.frames import Close

from fluxlit.config import FluxlitSettings
from fluxlit.gateway import (
    GatewayProxyOptions,
    _gateway_opts,
    _proxy_http,
    _proxy_websocket,
)


def _httpx_getter(client: httpx.AsyncClient) -> Callable[[], Awaitable[httpx.AsyncClient]]:
    async def _g() -> httpx.AsyncClient:
        return client

    return _g


def test_gateway_opts_maps_fluxlit_settings_fields() -> None:
    fs = FluxlitSettings(
        gateway_upstream_connect_timeout_s=1.5,
        gateway_upstream_read_timeout_s=9.25,
        gateway_max_proxy_request_body_bytes=2048,
        gateway_max_concurrent_upstream_http=7,
        gateway_httpx_max_connections=100,
        gateway_httpx_max_keepalive_connections=10,
        gateway_ws_open_timeout_s=11.0,
        gateway_ws_ping_interval_s=22.0,
        gateway_ws_ping_timeout_s=33.0,
        gateway_ws_close_timeout_s=44.0,
        gateway_ws_max_message_bytes=55,
    )
    o = _gateway_opts(fs)
    assert o == GatewayProxyOptions(
        connect_timeout=1.5,
        read_timeout=9.25,
        max_proxy_body_bytes=2048,
        max_concurrent_upstream_http=7,
        httpx_max_connections=100,
        httpx_max_keepalive_connections=10,
        ws_open_timeout_s=11.0,
        ws_ping_interval_s=22.0,
        ws_ping_timeout_s=33.0,
        ws_close_timeout_s=44.0,
        ws_max_message_bytes=55,
    )


def test_gateway_opts_none_uses_defaults() -> None:
    o = _gateway_opts(None)
    assert o == GatewayProxyOptions()


@pytest.mark.asyncio
async def test_proxy_http_connect_error_returns_502() -> None:
    class _ConnErrClient:
        def build_request(self, *args: object, **kwargs: object) -> object:
            return object()

        async def send(self, *args: object, **kwargs: object) -> httpx.Response:
            raise httpx.ConnectError("refused", request=httpx.Request("GET", "http://127.0.0.1:9"))

    sent: list[dict[str, Any]] = []

    async def send_asgi(msg: dict[str, Any]) -> None:
        sent.append(msg)

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    await _proxy_http(
        {"type": "http", "method": "GET", "path": "/", "headers": [], "query_string": b""},
        receive,
        send_asgi,
        "http://127.0.0.1:9",
        "/",
        request_id="ce-1",
        proxy_options=GatewayProxyOptions(),
        httpx_client_getter=_httpx_getter(cast(httpx.AsyncClient, _ConnErrClient())),
        upstream_sem=None,
    )
    assert sent[0]["status"] == 502


@pytest.mark.asyncio
async def test_proxy_http_read_timeout_returns_502() -> None:
    class _TimeoutClient:
        def build_request(self, *args: object, **kwargs: object) -> object:
            return object()

        async def send(self, *args: object, **kwargs: object) -> httpx.Response:
            raise httpx.ReadTimeout("slow", request=httpx.Request("GET", "http://127.0.0.1:9"))

    sent: list[dict[str, Any]] = []

    async def send_asgi(msg: dict[str, Any]) -> None:
        sent.append(msg)

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    await _proxy_http(
        {"type": "http", "method": "GET", "path": "/", "headers": [], "query_string": b""},
        receive,
        send_asgi,
        "http://127.0.0.1:9",
        "/",
        request_id="rt-1",
        proxy_options=GatewayProxyOptions(),
        httpx_client_getter=_httpx_getter(cast(httpx.AsyncClient, _TimeoutClient())),
        upstream_sem=None,
    )
    assert sent[0]["status"] == 502


@pytest.mark.asyncio
async def test_proxy_http_get_chunked_drain_exceeds_max_returns_413() -> None:
    """GET drain path: exceed ``max_proxy_body_bytes`` on a second ``http.request`` chunk."""
    queue: list[dict[str, Any]] = [
        {"type": "http.request", "body": b"a" * 6, "more_body": True},
        {"type": "http.request", "body": b"b" * 6, "more_body": False},
    ]

    async def receive() -> dict[str, Any]:
        if queue:
            return queue.pop(0)
        return {"type": "http.disconnect"}

    sent: list[dict[str, Any]] = []

    async def send_asgi(msg: dict[str, Any]) -> None:
        sent.append(msg)

    class _NeverSendClient:
        def build_request(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("upstream must not be contacted after 413 drain")

        async def send(self, *args: object, **kwargs: object) -> httpx.Response:
            raise AssertionError("upstream must not be contacted after 413 drain")

    await _proxy_http(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "query_string": b"",
        },
        receive,
        send_asgi,
        "http://127.0.0.1:9",
        "/",
        request_id="get-drain-chunk-413",
        proxy_options=GatewayProxyOptions(max_proxy_body_bytes=10),
        httpx_client_getter=_httpx_getter(cast(httpx.AsyncClient, _NeverSendClient())),
        upstream_sem=None,
    )
    assert sent[0]["status"] == 413


@pytest.mark.asyncio
async def test_proxy_websocket_forwards_ws_tuning_kwargs_to_connect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class _FakeUpstreamWs:
        subprotocol = "streamlit"

        async def send(self, *_a: object, **_kw: object) -> None:
            return None

        async def recv(self) -> bytes:
            raise websockets.ConnectionClosed(rcvd=Close(1000, ""), sent=None)

        async def close(self) -> None:
            return None

    class _FakeConnectCM:
        async def __aenter__(self) -> _FakeUpstreamWs:
            return _FakeUpstreamWs()

        async def __aexit__(self, *_exc: object) -> None:
            return None

    def _fake_connect(*_a: object, **kwargs: object) -> _FakeConnectCM:
        captured.clear()
        captured.update(kwargs)
        return _FakeConnectCM()

    monkeypatch.setattr("fluxlit.gateway.websockets.connect", _fake_connect)

    opts = GatewayProxyOptions(
        ws_open_timeout_s=12.5,
        ws_ping_interval_s=20.0,
        ws_ping_timeout_s=8.0,
        ws_close_timeout_s=4.0,
        ws_max_message_bytes=16384,
    )
    sent: list[dict[str, Any]] = []
    n = 0

    async def send(msg: dict[str, Any]) -> None:
        sent.append(msg)

    async def receive() -> dict[str, Any]:
        nonlocal n
        n += 1
        if n == 1:
            return {"type": "websocket.connect"}
        return {"type": "websocket.disconnect", "code": 1000}

    await _proxy_websocket(
        {
            "type": "websocket",
            "path": "/_stcore/stream",
            "headers": [(b"host", b"h")],
            "query_string": b"",
            "subprotocols": ["streamlit"],
            "scheme": "http",
            "client": ("127.0.0.1", 1),
        },
        receive,
        send,
        "http://127.0.0.1:8501",
        "/_stcore/stream",
        request_id="ws-tune",
        proxy_options=opts,
    )
    assert captured["open_timeout"] == 12.5
    assert captured["ping_interval"] == 20.0
    assert captured["ping_timeout"] == 8.0
    assert captured["close_timeout"] == 4.0
    assert captured["max_size"] == 16384


@pytest.mark.asyncio
async def test_proxy_websocket_omits_optional_ws_kwargs_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class _FakeUpstreamWs:
        subprotocol = "streamlit"

        async def send(self, *_a: object, **_kw: object) -> None:
            return None

        async def recv(self) -> bytes:
            raise websockets.ConnectionClosed(rcvd=Close(1000, ""), sent=None)

        async def close(self) -> None:
            return None

    class _FakeConnectCM:
        async def __aenter__(self) -> _FakeUpstreamWs:
            return _FakeUpstreamWs()

        async def __aexit__(self, *_exc: object) -> None:
            return None

    def _fake_connect(*_a: object, **kwargs: object) -> _FakeConnectCM:
        captured.clear()
        captured.update(kwargs)
        return _FakeConnectCM()

    monkeypatch.setattr("fluxlit.gateway.websockets.connect", _fake_connect)

    n = 0

    async def send(msg: dict[str, Any]) -> None:
        del msg

    async def receive() -> dict[str, Any]:
        nonlocal n
        n += 1
        if n == 1:
            return {"type": "websocket.connect"}
        return {"type": "websocket.disconnect", "code": 1000}

    await _proxy_websocket(
        {
            "type": "websocket",
            "path": "/",
            "headers": [(b"host", b"h")],
            "query_string": b"",
            "subprotocols": ["streamlit"],
            "scheme": "http",
            "client": None,
        },
        receive,
        send,
        "http://127.0.0.1:9",
        "/",
        request_id="ws-min",
        proxy_options=GatewayProxyOptions(),
    )
    assert set(captured.keys()) >= {"open_timeout", "additional_headers", "subprotocols"}
    assert captured["open_timeout"] == 30.0
    assert "ping_interval" not in captured
    assert "max_size" not in captured
