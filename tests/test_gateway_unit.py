from __future__ import annotations

import asyncio
import types
from collections.abc import Awaitable, Callable, MutableMapping
from contextlib import contextmanager
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import websockets
from fastapi import FastAPI
from starlette.testclient import TestClient
from starlette.types import Receive, Scope, Send
from starlette.websockets import WebSocketDisconnect
from websockets.frames import Close

import fluxlit.gateway.metrics as metrics_module
from fluxlit.config import FluxlitSettings
from fluxlit.gateway import (
    GatewayProxyOptions,
    _build_target_url,
    _filter_request_headers,
    _forwarded_upstream_header_pairs,
    _not_found,
    _parse_ws_target,
    _port_from_host_header,
    _proxy_http,
    _proxy_websocket,
    _public_host_from_scope,
    _request_id_from_scope,
    _strip_prefix_scope,
    _upstream_host_header,
    build_gateway,
    normalize_root_mount,
    split_gateway_paths,
)
from fluxlit.gateway.dispatch import make_gateway_app
from fluxlit.gateway.paths import location_under_mount
from fluxlit.gateway.responses import (
    bad_streamlit_upstream_ws,
    redirect,
    respond_413_payload_too_large,
)
from fluxlit.tracing import reset_trace_hook, set_trace_hook


def _httpx_getter(client: httpx.AsyncClient) -> Callable[[], Awaitable[httpx.AsyncClient]]:
    async def _g() -> httpx.AsyncClient:
        return client

    return _g


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


def test_public_host_from_scope_uses_client_host() -> None:
    scope: dict[str, Any] = {"headers": [(b"host", b"127.0.0.1:8777")]}
    assert _public_host_from_scope(scope, "http://127.0.0.1:8501") == "127.0.0.1:8777"


def test_public_host_from_scope_fallback_to_upstream() -> None:
    scope: dict[str, Any] = {"headers": []}
    assert _public_host_from_scope(scope, "http://127.0.0.1:8501") == "127.0.0.1:8501"


def test_public_host_from_scope_empty_host_falls_back() -> None:
    scope: dict[str, Any] = {"headers": [(b"host", b"  ")]}
    assert _public_host_from_scope(scope, "http://127.0.0.1:8501") == "127.0.0.1:8501"


def test_filter_request_headers_strips_hop_by_hop_and_host() -> None:
    raw = [
        (b"Host", b"client.example"),
        (b"Connection", b"keep-alive"),
        (b"X-Custom", b"1"),
    ]
    out = _filter_request_headers(raw)
    assert out == [(b"X-Custom", b"1")]


def test_filter_request_headers_strips_x_forwarded() -> None:
    raw = [
        (b"x-forwarded-for", b"evil"),
        (b"X-Forwarded-Host", b"evil"),
        (b"x-forwarded-prefix", b"evil"),
        (b"X-Custom", b"1"),
    ]
    assert _filter_request_headers(raw) == [(b"X-Custom", b"1")]


def test_filter_request_headers_strips_te_trailers_token_and_transfer_encoding() -> None:
    raw = [
        (b"Te", b"trailers"),
        (b"trailers", b"bogus"),
        (b"Transfer-Encoding", b"chunked"),
        (b"X-Custom", b"1"),
    ]
    assert _filter_request_headers(raw) == [(b"X-Custom", b"1")]


def test_port_from_host_header_ipv4_and_bracket_ipv6() -> None:
    assert _port_from_host_header("127.0.0.1:8777") == 8777
    assert _port_from_host_header("[::1]:8777") == 8777
    assert _port_from_host_header("[::1]") is None
    assert _port_from_host_header("example.com") is None


def test_forwarded_upstream_header_pairs() -> None:
    scope: dict[str, Any] = {
        "scheme": "https",
        "client": ("203.0.113.1", 1234),
    }
    pairs = _forwarded_upstream_header_pairs(scope, "h.example:9")
    assert ("X-Forwarded-Host", "h.example:9") in pairs
    assert ("X-Forwarded-Proto", "https") in pairs
    assert ("X-Forwarded-Port", "9") in pairs
    assert ("X-Forwarded-For", "203.0.113.1") in pairs


def test_forwarded_upstream_header_pairs_includes_prefix() -> None:
    scope: dict[str, Any] = {"scheme": "http", "client": None}
    pairs = _forwarded_upstream_header_pairs(scope, "h.example", forwarded_prefix="/content/42")
    assert ("X-Forwarded-Prefix", "/content/42") in pairs


def test_normalize_and_split_gateway_paths() -> None:
    assert normalize_root_mount("myapp/") == "/myapp"
    assert normalize_root_mount(" /myapp/ ") == "/myapp"
    assert normalize_root_mount("/") == ""
    assert normalize_root_mount("") == ""
    assert split_gateway_paths("/myapp/api/x", "/myapp") == ("/api/x", "/myapp/api/x")
    assert split_gateway_paths("myapp/api/x", "/myapp") == ("/api/x", "/myapp/api/x")
    assert split_gateway_paths("/_stcore/stream", "/myapp") == (
        "/_stcore/stream",
        "/myapp/_stcore/stream",
    )
    assert split_gateway_paths("/api/x", "/myapp") == ("/api/x", "/myapp/api/x")
    assert split_gateway_paths("/api/x", "") == ("/api/x", "/api/x")


def test_location_under_mount_normalizes_suffix() -> None:
    assert location_under_mount("/myapp/", "api/docs") == "/myapp/api/docs"
    assert location_under_mount("", "api/docs") == "/api/docs"


def test_split_gateway_paths_defensively_normalizes_rest_without_slash() -> None:
    class OddPath(str):
        def startswith(self, prefix: object, *args: object) -> bool:
            if prefix == "/myapp/":
                return True
            return super().startswith(prefix)  # type: ignore[arg-type]

        def __getitem__(self, key: object) -> str:
            if isinstance(key, slice) and key.start == len("/myapp"):
                return "api/x"
            return super().__getitem__(key)  # type: ignore[index]

    assert split_gateway_paths(OddPath("/myapp/api/x"), "/myapp") == ("/api/x", "/myapp/api/x")


@pytest.mark.parametrize(
    ("path_in", "mount", "dispatch", "streamlit_path"),
    [
        ("/myapp/api/healthz", "/myapp", "/api/healthz", "/myapp/api/healthz"),
        ("/myapp/api/v1/items", "/myapp", "/api/v1/items", "/myapp/api/v1/items"),
        ("/myapp", "/myapp", "/", "/myapp"),
        ("/prefix", "/myapp", "/prefix", "/myapp/prefix"),
        ("/api/healthz", "/myapp", "/api/healthz", "/myapp/api/healthz"),
    ],
)
def test_split_gateway_paths_table(
    path_in: str,
    mount: str,
    dispatch: str,
    streamlit_path: str,
) -> None:
    assert split_gateway_paths(path_in, mount) == (dispatch, streamlit_path)


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
    assert new_scope["root_path"] == "/api"


def test_strip_prefix_scope_raw_path_latin1_non_ascii() -> None:
    """Paths with Latin-1 code points must round-trip via latin-1 bytes (not ascii)."""
    path = "/api/café"
    scope: dict[str, Any] = {
        "type": "http",
        "path": path,
        "raw_path": path.encode("latin-1"),
        "headers": [],
    }
    new_scope = _strip_prefix_scope(scope, "/api")  # type: ignore[arg-type]
    assert new_scope["path"] == "/café"
    assert new_scope["raw_path"] == "/café".encode("latin-1")
    assert new_scope["root_path"] == "/api"


def test_strip_prefix_scope_extends_existing_root_path() -> None:
    scope: dict[str, Any] = {
        "type": "http",
        "path": "/api/ping",
        "raw_path": b"/api/ping",
        "root_path": "/myapp",
        "headers": [],
    }
    new_scope = _strip_prefix_scope(scope, "/api")  # type: ignore[arg-type]
    assert new_scope["path"] == "/ping"
    assert new_scope["root_path"] == "/myapp/api"


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

    async def send(msg: MutableMapping[str, Any]) -> None:
        messages.append(dict(msg))

    await _not_found(send)
    assert messages[0]["type"] == "http.response.start"
    assert messages[0]["status"] == 404
    assert messages[1]["body"] == b"Not Found"


@pytest.mark.asyncio
async def test_redirect_response_defaults_to_307() -> None:
    messages: list[dict[str, Any]] = []

    async def send(msg: MutableMapping[str, Any]) -> None:
        messages.append(dict(msg))

    await redirect(send, "/api/docs")
    assert messages[0]["status"] == 307
    assert (b"location", b"/api/docs") in messages[0]["headers"]
    assert messages[1]["body"] == b""


@pytest.mark.asyncio
async def test_bad_streamlit_upstream_ws_closes_on_connect_and_ignores_disconnect() -> None:
    sent: list[dict[str, Any]] = []

    async def send(msg: MutableMapping[str, Any]) -> None:
        sent.append(dict(msg))

    async def receive_connect() -> dict[str, Any]:
        return {"type": "websocket.connect"}

    await bad_streamlit_upstream_ws(receive_connect, send)
    assert sent == [
        {
            "type": "websocket.close",
            "code": 1011,
            "reason": b"Streamlit upstream missing",
        }
    ]

    async def receive_disconnect() -> dict[str, Any]:
        return {"type": "websocket.disconnect"}

    sent.clear()
    await bad_streamlit_upstream_ws(receive_disconnect, send)
    assert sent == []


@pytest.mark.asyncio
async def test_respond_413_payload_too_large_message() -> None:
    sent: list[dict[str, Any]] = []

    async def send(msg: MutableMapping[str, Any]) -> None:
        sent.append(dict(msg))

    await respond_413_payload_too_large(send)
    assert sent[0]["status"] == 413
    assert b"FLUXLIT_GATEWAY_MAX_PROXY_REQUEST_BODY_BYTES" in sent[1]["body"]


@pytest.mark.asyncio
async def test_gateway_unknown_scope_type_is_404() -> None:
    gateway = build_gateway(FastAPI(), "http://127.0.0.1:9", api_prefix="/api")
    sent: list[dict[str, Any]] = []

    async def send(msg: MutableMapping[str, Any]) -> None:
        sent.append(dict(msg))

    async def receive() -> dict[str, Any]:
        return {"type": "http.disconnect"}

    scope: dict[str, Any] = {
        "type": "lifespan-not-this",
        "path": "/anything",
        "headers": [],
    }
    await gateway(scope, receive, send)
    assert sent[0]["status"] == 404


def test_gateway_trace_hook_observes_dispatch_span() -> None:
    seen: list[tuple[str, dict[str, object]]] = []

    @contextmanager
    def hook(name: str, attrs):
        seen.append((name, dict(attrs)))
        yield

    token = set_trace_hook(hook)
    try:
        gateway = build_gateway(FastAPI(), "http://127.0.0.1:9", api_prefix="/api")
        with TestClient(gateway) as client:
            client.get("/api/healthz", headers={"X-Request-ID": "trace-hook-test"})
    finally:
        reset_trace_hook(token)

    assert seen
    assert seen[0][0] == "fluxlit.gateway.request"
    assert seen[0][1]["fluxlit.dispatch"] == "api"
    assert seen[0][1]["request_id"] == "trace-hook-test"


def test_websocket_proxy_upstream_refused_closes() -> None:
    gateway = build_gateway(FastAPI(), "http://127.0.0.1:9", api_prefix="/api")
    with TestClient(gateway) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                "/_stcore/stream",
                subprotocols=["streamlit"],
            ):
                pass


@pytest.mark.asyncio
async def test_proxy_http_aclose_on_body_error() -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = httpx.Headers({})
    mock_resp.aclose = AsyncMock()

    def _bad_content() -> bytes:
        raise RuntimeError("body broken")

    type(mock_resp).content = property(lambda self: _bad_content())

    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> _FakeAsyncClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        def build_request(self, *args: object, **kwargs: object) -> object:
            return object()

        async def send(self, *args: object, **kwargs: object) -> object:
            return mock_resp

    fake = cast(httpx.AsyncClient, _FakeAsyncClient())
    sent: list[dict[str, Any]] = []

    async def send_asgi(msg: MutableMapping[str, Any]) -> None:
        sent.append(dict(msg))

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    scope: dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "path": "/x",
        "headers": [],
        "query_string": b"",
    }
    with pytest.raises(RuntimeError, match="body broken"):
        await _proxy_http(
            scope,
            receive,
            send_asgi,
            "http://127.0.0.1:9",
            "/x",
            request_id="rid-aclose",
            proxy_options=GatewayProxyOptions(),
            httpx_client_getter=_httpx_getter(fake),
            upstream_sem=None,
        )

    mock_resp.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_proxy_http_strips_gzip_headers_and_sets_body_length() -> None:
    """Upstream may advertise gzip + wire length while httpx exposes decoded bytes."""
    decoded = b"<html>" + b"x" * 200
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = httpx.Headers(
        {
            "content-type": "text/html",
            "content-encoding": "gzip",
            "content-length": "9",
        }
    )
    mock_resp.content = decoded
    mock_resp.aclose = AsyncMock()

    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> _FakeAsyncClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        def build_request(self, *args: object, **kwargs: object) -> object:
            return object()

        async def send(self, *args: object, **kwargs: object) -> object:
            return mock_resp

    fake = cast(httpx.AsyncClient, _FakeAsyncClient())
    sent: list[dict[str, Any]] = []

    async def send(msg: MutableMapping[str, Any]) -> None:
        sent.append(dict(msg))

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    scope: dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
    }
    await _proxy_http(
        scope,
        receive,
        send,
        "http://127.0.0.1:9",
        "/",
        request_id="rid-gzip",
        proxy_options=GatewayProxyOptions(),
        httpx_client_getter=_httpx_getter(fake),
        upstream_sem=None,
    )

    start = sent[0]
    assert start["type"] == "http.response.start"
    hdrs = {k.decode(): v.decode() for k, v in start["headers"]}
    assert hdrs["content-type"] == "text/html"
    assert "content-encoding" not in hdrs
    assert hdrs["content-length"] == str(len(decoded))
    assert sent[1]["type"] == "http.response.body"
    assert sent[1]["body"] == decoded
    assert sent[1].get("more_body") is False
    mock_resp.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_proxy_http_head_sends_empty_body_and_zero_content_length() -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = httpx.Headers(
        {
            "content-type": "text/html",
            "content-encoding": "gzip",
            "content-length": "9999",
        }
    )
    mock_resp.content = b"<ignored for HEAD>"
    mock_resp.aclose = AsyncMock()

    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> _FakeAsyncClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        def build_request(self, *args: object, **kwargs: object) -> object:
            return object()

        async def send(self, *args: object, **kwargs: object) -> object:
            return mock_resp

    fake = cast(httpx.AsyncClient, _FakeAsyncClient())
    sent: list[dict[str, Any]] = []

    async def send(msg: MutableMapping[str, Any]) -> None:
        sent.append(dict(msg))

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    scope: dict[str, Any] = {
        "type": "http",
        "method": "HEAD",
        "path": "/",
        "headers": [],
        "query_string": b"",
    }
    await _proxy_http(
        scope,
        receive,
        send,
        "http://127.0.0.1:9",
        "/",
        request_id="rid-head",
        proxy_options=GatewayProxyOptions(),
        httpx_client_getter=_httpx_getter(fake),
        upstream_sem=None,
    )

    hdrs = {k.decode(): v.decode() for k, v in sent[0]["headers"]}
    assert hdrs["content-length"] == "0"
    assert "content-encoding" not in hdrs
    assert sent[1]["body"] == b""
    mock_resp.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_inject_public_root_path_does_not_touch_lifespan() -> None:
    from fluxlit.runtime import _inject_public_root_path

    seen: list[str] = []

    async def inner(scope: Scope, receive: Receive, send: Send) -> None:  # noqa: ARG001
        seen.append(scope["type"])  # type: ignore[typeddict-item]

    app = _inject_public_root_path(inner, "/myapp")
    await app({"type": "lifespan"}, None, None)  # type: ignore[arg-type]
    assert seen == ["lifespan"]


@pytest.mark.asyncio
async def test_proxy_websocket_connect_passes_x_request_id_header(
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
        captured["connect_kwargs"] = kwargs
        return _FakeConnectCM()

    monkeypatch.setattr("fluxlit.gateway.websockets.connect", _fake_connect)

    sent: list[dict[str, Any]] = []
    _ws_recv_calls = 0

    async def send(msg: MutableMapping[str, Any]) -> None:
        sent.append(dict(msg))

    async def receive() -> dict[str, Any]:
        nonlocal _ws_recv_calls
        _ws_recv_calls += 1
        if _ws_recv_calls == 1:
            return {"type": "websocket.connect"}
        return {"type": "websocket.disconnect", "code": 1000}

    scope: dict[str, Any] = {
        "type": "websocket",
        "path": "/_stcore/stream",
        "headers": [(b"host", b"p.example:9")],
        "query_string": b"",
        "subprotocols": ["streamlit"],
        "scheme": "http",
        "client": ("1.2.3.4", 1),
    }
    await _proxy_websocket(
        scope,
        receive,
        send,
        "http://127.0.0.1:8501",
        "/_stcore/stream",
        request_id="ws-rid-99",
        proxy_options=GatewayProxyOptions(),
    )

    extra = captured["connect_kwargs"]["additional_headers"]
    assert ("X-Request-ID", "ws-rid-99") in extra


@pytest.mark.asyncio
async def test_proxy_websocket_rejects_non_connect_first_message() -> None:
    sent: list[dict[str, Any]] = []

    async def send(msg: MutableMapping[str, Any]) -> None:
        sent.append(dict(msg))

    async def receive() -> dict[str, Any]:
        return {"type": "websocket.receive", "text": "too soon"}

    await _proxy_websocket(
        {"type": "websocket", "path": "/_stcore/stream", "headers": [], "query_string": b""},
        receive,
        send,
        "http://127.0.0.1:8501",
        "/_stcore/stream",
        request_id="bad-ws",
        proxy_options=GatewayProxyOptions(),
    )
    assert sent == [{"type": "websocket.close", "code": 1002}]


@pytest.mark.asyncio
async def test_proxy_websocket_connect_timeout_closes_cleanly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``websockets.connect`` open_timeout raises ``TimeoutError``; must not escape ASGI."""

    class _TimeoutOnEnterCM:
        async def __aenter__(self) -> object:
            raise TimeoutError()

        async def __aexit__(self, *_exc: object) -> None:
            return None

    def _fake_connect(*_a: object, **_kw: object) -> _TimeoutOnEnterCM:
        return _TimeoutOnEnterCM()

    monkeypatch.setattr("fluxlit.gateway.websocket_proxy.websockets.connect", _fake_connect)

    sent: list[dict[str, Any]] = []

    async def send(msg: MutableMapping[str, Any]) -> None:
        sent.append(dict(msg))

    async def receive() -> dict[str, Any]:
        return {"type": "websocket.connect"}

    await _proxy_websocket(
        {
            "type": "websocket",
            "path": "/_stcore/stream",
            "headers": [(b"host", b"example")],
            "query_string": b"",
            "subprotocols": ["streamlit"],
            "scheme": "http",
            "client": ("1.2.3.4", 1),
        },
        receive,
        send,
        "http://127.0.0.1:8501",
        "/_stcore/stream",
        request_id="ws-timeout-rid",
        proxy_options=GatewayProxyOptions(),
    )
    assert sent == [{"type": "websocket.close", "code": 1011}]


@pytest.mark.asyncio
async def test_proxy_websocket_options_and_bidirectional_bytes_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {"sent_upstream": []}

    class _FakeUpstreamWs:
        subprotocol = None

        async def send(self, data: object) -> None:
            captured["sent_upstream"].append(data)

        async def recv(self) -> object:
            calls = captured.setdefault("recv_calls", 0)
            captured["recv_calls"] = calls + 1
            if calls == 0:
                return b"from-upstream"
            if calls == 1:
                return "text-upstream"
            raise websockets.ConnectionClosed(rcvd=Close(1000, ""), sent=None)

        async def close(self) -> None:
            captured["closed"] = True

    class _FakeConnectCM:
        async def __aenter__(self) -> _FakeUpstreamWs:
            return _FakeUpstreamWs()

        async def __aexit__(self, *_exc: object) -> None:
            return None

    def fake_connect(*args: object, **kwargs: object) -> _FakeConnectCM:
        captured["connect_kwargs"] = kwargs
        return _FakeConnectCM()

    class _FakeTaskGroup:
        def __init__(self) -> None:
            self.cancel_scope = types.SimpleNamespace(cancel=lambda: None)
            self._funcs: list[Callable[[], Awaitable[None]]] = []

        async def __aenter__(self) -> _FakeTaskGroup:
            return self

        async def __aexit__(self, *args: object) -> None:
            for fn in self._funcs:
                await fn()

        def start_soon(self, fn: Callable[[], Awaitable[None]]) -> None:
            self._funcs.append(fn)

    monkeypatch.setattr("fluxlit.gateway.websocket_proxy.websockets.connect", fake_connect)
    monkeypatch.setattr("fluxlit.gateway.websocket_proxy.anyio.create_task_group", _FakeTaskGroup)

    messages = [
        {"type": "websocket.connect"},
        {"type": "websocket.receive", "bytes": b"client-bytes"},
        {"type": "websocket.receive", "text": "client-text"},
        {"type": "websocket.disconnect", "code": 1000},
    ]

    async def receive() -> dict[str, Any]:
        return messages.pop(0)

    sent: list[dict[str, Any]] = []

    async def send(msg: MutableMapping[str, Any]) -> None:
        sent.append(dict(msg))

    await _proxy_websocket(
        {
            "type": "websocket",
            "path": "/_stcore/stream",
            "headers": [(b"sec-websocket-extensions", b"skip")],
            "query_string": b"",
            "subprotocols": ["browser-only"],
            "scheme": "http",
            "client": ("1.2.3.4", 1),
        },
        receive,
        send,
        "http://127.0.0.1:8501",
        "/_stcore/stream",
        request_id="ws-options",
        proxy_options=GatewayProxyOptions(
            ws_max_message_bytes=123,
            ws_ping_interval_s=5,
            ws_ping_timeout_s=6,
            ws_close_timeout_s=7,
        ),
    )
    kwargs = captured["connect_kwargs"]
    assert kwargs["max_size"] == 123
    assert kwargs["ping_interval"] == 5
    assert kwargs["ping_timeout"] == 6
    assert kwargs["close_timeout"] == 7
    assert captured["sent_upstream"] == [b"client-bytes", "client-text"]
    assert {"type": "websocket.accept"} in sent
    assert {"type": "websocket.send", "bytes": b"from-upstream"} in sent
    assert {"type": "websocket.send", "text": "text-upstream"} in sent


@pytest.mark.asyncio
async def test_proxy_http_get_body_over_max_returns_413() -> None:
    sent: list[dict[str, Any]] = []

    async def send(msg: MutableMapping[str, Any]) -> None:
        sent.append(dict(msg))

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"x" * 50, "more_body": False}

    scope: dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
    }

    class _NoSendClient:
        def build_request(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("build_request should not run after 413 drain")

        async def send(self, *args: object, **kwargs: object) -> httpx.Response:
            raise AssertionError("send should not run after 413 drain")

    fake = cast(httpx.AsyncClient, _NoSendClient())
    await _proxy_http(
        scope,
        receive,
        send,
        "http://127.0.0.1:9",
        "/",
        request_id="rid-413",
        proxy_options=GatewayProxyOptions(max_proxy_body_bytes=10),
        httpx_client_getter=_httpx_getter(fake),
        upstream_sem=None,
    )
    assert sent[0]["type"] == "http.response.start"
    assert sent[0]["status"] == 413
    assert b"Payload Too Large" in sent[1]["body"]


@pytest.mark.asyncio
async def test_proxy_http_get_drain_stops_on_disconnect_message() -> None:
    class _Client:
        def build_request(self, method: str, url: str, **kwargs: object) -> httpx.Request:
            return httpx.Request(method, url)

        async def send(self, request: httpx.Request, *, stream: bool) -> httpx.Response:
            return httpx.Response(200, content=b"ok")

    async def receive() -> dict[str, Any]:
        return {"type": "http.disconnect"}

    sent: list[dict[str, Any]] = []

    async def send(msg: MutableMapping[str, Any]) -> None:
        sent.append(dict(msg))

    await _proxy_http(
        {"type": "http", "method": "GET", "path": "/", "headers": [], "query_string": b""},
        receive,
        send,
        "http://127.0.0.1:9",
        "/",
        request_id="rid-drain-disconnect",
        proxy_options=GatewayProxyOptions(max_proxy_body_bytes=100),
        httpx_client_getter=_httpx_getter(cast(httpx.AsyncClient, _Client())),
        upstream_sem=None,
    )
    assert sent[0]["status"] == 200


@pytest.mark.asyncio
async def test_proxy_http_semaphore_blocks_second_request_until_first_finishes() -> None:
    first_in_send = asyncio.Event()
    second_in_send = asyncio.Event()
    release_first = asyncio.Event()

    class _FirstClient:
        def build_request(self, *args: object, **kwargs: object) -> object:
            return object()

        async def send(self, *args: object, **kwargs: object) -> httpx.Response:
            first_in_send.set()
            await release_first.wait()
            return httpx.Response(200, content=b"one")

    class _SecondClient:
        def build_request(self, *args: object, **kwargs: object) -> object:
            return object()

        async def send(self, *args: object, **kwargs: object) -> httpx.Response:
            second_in_send.set()
            return httpx.Response(200, content=b"two")

    sem = asyncio.Semaphore(1)
    opts = GatewayProxyOptions()

    async def receive_empty() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def run_first() -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []

        async def send(msg: MutableMapping[str, Any]) -> None:
            out.append(dict(msg))

        await _proxy_http(
            {"type": "http", "method": "GET", "path": "/a", "headers": [], "query_string": b""},
            receive_empty,
            send,
            "http://127.0.0.1:9",
            "/a",
            request_id="r1",
            proxy_options=opts,
            httpx_client_getter=_httpx_getter(cast(httpx.AsyncClient, _FirstClient())),
            upstream_sem=sem,
        )
        return out

    async def run_second() -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []

        async def send(msg: MutableMapping[str, Any]) -> None:
            out.append(dict(msg))

        await _proxy_http(
            {"type": "http", "method": "GET", "path": "/b", "headers": [], "query_string": b""},
            receive_empty,
            send,
            "http://127.0.0.1:9",
            "/b",
            request_id="r2",
            proxy_options=opts,
            httpx_client_getter=_httpx_getter(cast(httpx.AsyncClient, _SecondClient())),
            upstream_sem=sem,
        )
        return out

    t1 = asyncio.create_task(run_first())
    await asyncio.wait_for(first_in_send.wait(), timeout=2.0)
    t2 = asyncio.create_task(run_second())
    await asyncio.sleep(0.05)
    assert not second_in_send.is_set()
    release_first.set()
    await asyncio.gather(t1, t2)
    assert second_in_send.is_set()


@pytest.mark.asyncio
async def test_proxy_http_upstream_request_error_returns_502() -> None:
    class _ErrClient:
        def build_request(self, *args: object, **kwargs: object) -> object:
            return object()

        async def send(self, *args: object, **kwargs: object) -> httpx.Response:
            raise httpx.RequestError("boom", request=httpx.Request("GET", "http://127.0.0.1:9"))

    sent: list[dict[str, Any]] = []

    async def send(msg: MutableMapping[str, Any]) -> None:
        sent.append(dict(msg))

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    scope: dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
    }
    await _proxy_http(
        scope,
        receive,
        send,
        "http://127.0.0.1:9",
        "/",
        request_id="rid-502",
        proxy_options=GatewayProxyOptions(),
        httpx_client_getter=_httpx_getter(cast(httpx.AsyncClient, _ErrClient())),
        upstream_sem=None,
    )
    assert sent[0]["type"] == "http.response.start"
    assert sent[0]["status"] == 502
    assert sent[1]["body"] == b"Bad Gateway"


@pytest.mark.asyncio
async def test_proxy_http_post_streams_request_body_without_limit() -> None:
    captured: dict[str, Any] = {}

    class _Client:
        def build_request(self, method: str, url: str, **kwargs: object) -> httpx.Request:
            captured["method"] = method
            captured["url"] = url
            captured["content"] = kwargs["content"]
            return httpx.Request(method, url)

        async def send(self, request: httpx.Request, *, stream: bool) -> httpx.Response:
            body = b""
            async for chunk in captured["content"]:
                body += chunk
            captured["body"] = body
            return httpx.Response(201, content=b"ok")

    messages = [
        {"type": "http.request", "body": b"hello-", "more_body": True},
        {"type": "http.request", "body": b"world", "more_body": False},
    ]

    async def receive() -> dict[str, Any]:
        return messages.pop(0)

    sent: list[dict[str, Any]] = []

    async def send(msg: MutableMapping[str, Any]) -> None:
        sent.append(dict(msg))

    await _proxy_http(
        {"type": "http", "method": "POST", "path": "/submit", "headers": [], "query_string": b""},
        receive,
        send,
        "http://127.0.0.1:9",
        "/submit",
        request_id="rid-post",
        proxy_options=GatewayProxyOptions(max_proxy_body_bytes=0),
        httpx_client_getter=_httpx_getter(cast(httpx.AsyncClient, _Client())),
        upstream_sem=None,
    )
    assert captured["method"] == "POST"
    assert captured["body"] == b"hello-world"
    assert sent[0]["status"] == 201


@pytest.mark.asyncio
async def test_proxy_http_post_streaming_body_over_limit_raises_413_when_consumed() -> None:
    class ToggleMax:
        def __init__(self) -> None:
            self.calls = 0

        def __bool__(self) -> bool:
            self.calls += 1
            return self.calls > 1

        def __lt__(self, other: int) -> bool:
            return True

    class _Client:
        def build_request(self, method: str, url: str, **kwargs: object) -> object:
            return types.SimpleNamespace(content=kwargs["content"])

        async def send(self, request: object, *, stream: bool) -> httpx.Response:
            async for _chunk in request.content:
                pass
            raise AssertionError("oversized stream should not produce upstream response")

    messages = [
        {"type": "http.request", "body": b"x" * 5, "more_body": True},
        {"type": "http.request", "body": b"y" * 10, "more_body": False},
    ]

    async def receive() -> dict[str, Any]:
        return messages.pop(0)

    sent: list[dict[str, Any]] = []

    async def send(msg: MutableMapping[str, Any]) -> None:
        sent.append(dict(msg))

    await _proxy_http(
        {"type": "http", "method": "POST", "path": "/submit", "headers": [], "query_string": b""},
        receive,
        send,
        "http://127.0.0.1:9",
        "/submit",
        request_id="rid-stream-413",
        proxy_options=GatewayProxyOptions(max_proxy_body_bytes=cast(int, ToggleMax())),
        httpx_client_getter=_httpx_getter(cast(httpx.AsyncClient, _Client())),
        upstream_sem=None,
    )
    assert sent[0]["status"] == 413


@pytest.mark.asyncio
async def test_proxy_http_post_streaming_body_stops_on_disconnect_message() -> None:
    captured: dict[str, object] = {}

    class _Client:
        def build_request(self, method: str, url: str, **kwargs: object) -> object:
            return types.SimpleNamespace(content=kwargs["content"])

        async def send(self, request: object, *, stream: bool) -> httpx.Response:
            chunks: list[bytes] = []
            async for chunk in request.content:
                chunks.append(chunk)
            captured["chunks"] = chunks
            return httpx.Response(200, content=b"ok")

    async def receive() -> dict[str, Any]:
        return {"type": "http.disconnect"}

    async def send(msg: MutableMapping[str, Any]) -> None:
        return None

    await _proxy_http(
        {"type": "http", "method": "POST", "path": "/submit", "headers": [], "query_string": b""},
        receive,
        send,
        "http://127.0.0.1:9",
        "/submit",
        request_id="rid-stream-disconnect",
        proxy_options=GatewayProxyOptions(max_proxy_body_bytes=0),
        httpx_client_getter=_httpx_getter(cast(httpx.AsyncClient, _Client())),
        upstream_sem=None,
    )
    assert captured["chunks"] == []


@pytest.mark.asyncio
async def test_proxy_http_post_collects_limited_body_and_413s_before_upstream() -> None:
    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"x" * 20, "more_body": False}

    sent: list[dict[str, Any]] = []

    async def send(msg: MutableMapping[str, Any]) -> None:
        sent.append(dict(msg))

    class _Client:
        def build_request(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("upstream request should not be built")

        async def send(self, *args: object, **kwargs: object) -> httpx.Response:
            raise AssertionError("upstream should not be contacted")

    await _proxy_http(
        {"type": "http", "method": "POST", "path": "/submit", "headers": [], "query_string": b""},
        receive,
        send,
        "http://127.0.0.1:9",
        "/submit",
        request_id="rid-post-413",
        proxy_options=GatewayProxyOptions(max_proxy_body_bytes=10),
        httpx_client_getter=_httpx_getter(cast(httpx.AsyncClient, _Client())),
        upstream_sem=None,
    )
    assert sent[0]["status"] == 413


@pytest.mark.asyncio
async def test_proxy_http_post_collects_limited_body_success() -> None:
    captured: dict[str, object] = {}
    messages = [
        {"type": "http.request", "body": b"a", "more_body": True},
        {"type": "http.request", "body": b"b", "more_body": False},
    ]

    async def receive() -> dict[str, Any]:
        return messages.pop(0)

    async def send(msg: MutableMapping[str, Any]) -> None:
        return None

    class _Client:
        def build_request(self, method: str, url: str, **kwargs: object) -> httpx.Request:
            captured["content"] = kwargs["content"]
            return httpx.Request(method, url)

        async def send(self, request: httpx.Request, *, stream: bool) -> httpx.Response:
            return httpx.Response(200, content=b"ok")

    await _proxy_http(
        {"type": "http", "method": "POST", "path": "/submit", "headers": [], "query_string": b""},
        receive,
        send,
        "http://127.0.0.1:9",
        "/submit",
        request_id="rid-limited-ok",
        proxy_options=GatewayProxyOptions(max_proxy_body_bytes=10),
        httpx_client_getter=_httpx_getter(cast(httpx.AsyncClient, _Client())),
        upstream_sem=None,
    )
    assert captured["content"] == b"ab"


@pytest.mark.asyncio
async def test_proxy_http_stops_body_collection_on_disconnect_message() -> None:
    captured: dict[str, object] = {}
    messages = [{"type": "http.disconnect"}]

    async def receive() -> dict[str, Any]:
        return messages.pop(0)

    async def send(msg: MutableMapping[str, Any]) -> None:
        return None

    class _Client:
        def build_request(self, method: str, url: str, **kwargs: object) -> httpx.Request:
            captured["content"] = kwargs["content"]
            return httpx.Request(method, url)

        async def send(self, request: httpx.Request, *, stream: bool) -> httpx.Response:
            assert captured["content"] == b""
            return httpx.Response(204, content=b"")

    await _proxy_http(
        {"type": "http", "method": "POST", "path": "/submit", "headers": [], "query_string": b""},
        receive,
        send,
        "http://127.0.0.1:9",
        "/submit",
        request_id="rid-disconnect",
        proxy_options=GatewayProxyOptions(max_proxy_body_bytes=10),
        httpx_client_getter=_httpx_getter(cast(httpx.AsyncClient, _Client())),
        upstream_sem=None,
    )


@pytest.mark.asyncio
async def test_proxy_http_filters_incoming_request_id_header() -> None:
    captured: dict[str, object] = {}

    class _Client:
        def build_request(self, method: str, url: str, **kwargs: object) -> httpx.Request:
            captured["headers"] = httpx.Headers(kwargs["headers"])
            return httpx.Request(method, url)

        async def send(self, request: httpx.Request, *, stream: bool) -> httpx.Response:
            return httpx.Response(200, content=b"ok")

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(msg: MutableMapping[str, Any]) -> None:
        return None

    await _proxy_http(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"x-request-id", b"client-rid")],
            "query_string": b"",
        },
        receive,
        send,
        "http://127.0.0.1:9",
        "/",
        request_id="gateway-rid",
        proxy_options=GatewayProxyOptions(),
        httpx_client_getter=_httpx_getter(cast(httpx.AsyncClient, _Client())),
        upstream_sem=None,
    )
    headers = captured["headers"]
    assert isinstance(headers, httpx.Headers)
    assert headers["x-request-id"] == "gateway-rid"


@pytest.mark.asyncio
async def test_proxy_http_logs_and_reraises_send_body_failure() -> None:
    response = httpx.Response(200, content=b"ok")

    class _Client:
        def build_request(self, *args: object, **kwargs: object) -> httpx.Request:
            return httpx.Request("GET", "http://127.0.0.1:9")

        async def send(self, request: httpx.Request, *, stream: bool) -> httpx.Response:
            return response

    calls = {"n": 0}

    async def send(msg: MutableMapping[str, Any]) -> None:
        calls["n"] += 1
        if msg["type"] == "http.response.body":
            raise RuntimeError("send failed")

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    with pytest.raises(RuntimeError, match="send failed"):
        await _proxy_http(
            {"type": "http", "method": "GET", "path": "/", "headers": [], "query_string": b""},
            receive,
            send,
            "http://127.0.0.1:9",
            "/",
            request_id="rid-send-fail",
            proxy_options=GatewayProxyOptions(),
            httpx_client_getter=_httpx_getter(cast(httpx.AsyncClient, _Client())),
            upstream_sem=None,
        )
    assert calls["n"] == 2


def test_build_gateway_502_when_upstream_resolver_returns_empty() -> None:
    inner = FastAPI()

    @inner.get("/x")
    def _x() -> str:
        return "a"

    gw = build_gateway(
        inner,
        "http://127.0.0.1:8501",
        upstream_resolver=lambda: "",
        api_prefix="/api",
    )
    client = TestClient(gw)
    r = client.get("/streamlit-only-path")
    assert r.status_code == 502
    assert "Streamlit upstream" in r.text


def test_build_gateway_websocket_502_when_upstream_resolver_returns_empty() -> None:
    gw = build_gateway(FastAPI(), "http://127.0.0.1:8501", upstream_resolver=lambda: "")
    with TestClient(gw) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/_stcore/stream"):
                pass


def test_build_gateway_prometheus_path_conflict_disables_metrics() -> None:
    settings = FluxlitSettings(
        enable_gateway_prometheus_metrics=True,
        gateway_prometheus_metrics_path="/api/metrics",
    )
    gw = build_gateway(
        FastAPI(),
        "http://127.0.0.1:9",
        api_prefix="/api",
        proxy_settings=settings,
    )
    client = TestClient(gw)
    assert client.get("/api/metrics").status_code == 404


def test_build_gateway_shared_http_client_uses_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    created: dict[str, object] = {}

    class FakeAsyncClient:
        def __init__(self, **kwargs: object) -> None:
            created["kwargs"] = kwargs

        def build_request(self, method: str, url: str, **kwargs: object) -> httpx.Request:
            return httpx.Request(method, url)

        async def send(self, request: httpx.Request, *, stream: bool) -> httpx.Response:
            return httpx.Response(200, content=b"ok")

    monkeypatch.setattr("fluxlit.gateway.builder.httpx.AsyncClient", FakeAsyncClient)
    settings = FluxlitSettings(
        gateway_httpx_max_connections=3,
        gateway_httpx_max_keepalive_connections=0,
    )
    gw = build_gateway(FastAPI(), "http://127.0.0.1:9", proxy_settings=settings)
    client = TestClient(gw)
    assert client.get("/proxied").status_code == 200
    kwargs = created["kwargs"]
    assert isinstance(kwargs, dict)
    assert "limits" in kwargs


def test_build_gateway_creates_upstream_semaphore() -> None:
    settings = FluxlitSettings(gateway_max_concurrent_upstream_http=1)
    gw = build_gateway(FastAPI(), "http://127.0.0.1:9", proxy_settings=settings)
    client = TestClient(gw)
    assert client.get("/anything").status_code == 502


def test_build_gateway_prometheus_metrics_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("prometheus_client")
    import importlib

    pc = importlib.import_module("prometheus_client")
    monkeypatch.setattr(pc, "CONTENT_TYPE_LATEST", "text/plain; version=0.0.4")
    from fluxlit.config import FluxlitSettings

    settings = FluxlitSettings(enable_gateway_prometheus_metrics=True)
    gw = build_gateway(
        FastAPI(),
        "http://127.0.0.1:9",
        api_prefix="/api",
        proxy_settings=settings,
    )
    client = TestClient(gw)
    r = client.get("/__fluxlit/metrics")
    assert r.status_code == 200
    assert "fluxlit_gateway_requests_total" in r.text


def test_build_gateway_prometheus_metrics_endpoint_bytes_content_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("prometheus_client")
    import importlib

    pc = importlib.import_module("prometheus_client")
    monkeypatch.setattr(pc, "CONTENT_TYPE_LATEST", b"text/plain; version=0.0.4")
    settings = FluxlitSettings(enable_gateway_prometheus_metrics=True)
    gw = build_gateway(
        FastAPI(),
        "http://127.0.0.1:9",
        api_prefix="/api",
        proxy_settings=settings,
    )
    client = TestClient(gw)
    r = client.get("/__fluxlit/metrics")
    assert r.status_code == 200
    assert "fluxlit_gateway_requests_total" in r.text


def test_gateway_prometheus_metric_contract_documents_stable_names_and_labels() -> None:
    from fluxlit.gateway.metrics import GATEWAY_PROMETHEUS_METRICS

    by_name = {str(item["name"]): item for item in GATEWAY_PROMETHEUS_METRICS}
    assert by_name["fluxlit_gateway_requests_total"]["labels"] == ("dispatch", "method_kind")
    assert by_name["fluxlit_gateway_request_duration_seconds"]["labels"] == ("dispatch",)
    assert {item["stability"] for item in GATEWAY_PROMETHEUS_METRICS} == {"stable"}


def test_gateway_prometheus_metrics_returns_none_when_dependency_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cached = metrics_module._gateway_prom_cached  # noqa: SLF001
    metrics_module._gateway_prom_cached = None  # noqa: SLF001

    def missing(name: str):
        raise ImportError("missing prometheus")

    try:
        monkeypatch.setattr(metrics_module.importlib, "import_module", missing)
        assert metrics_module.get_gateway_prom_metrics() is None
        assert metrics_module.get_gateway_prom_metrics() is None
    finally:
        metrics_module._gateway_prom_cached = cached  # noqa: SLF001


def test_gateway_redirects_api_docs_routes_under_prefix() -> None:
    gw = build_gateway(FastAPI(), "http://127.0.0.1:9", api_prefix="/api", root_mount="/root")
    client = TestClient(gw)
    assert client.get("/root/docs", follow_redirects=False).headers["location"] == "/root/api/docs"
    assert (
        client.get("/root/redoc", follow_redirects=False).headers["location"] == "/root/api/redoc"
    )
    assert (
        client.get("/root/openapi.json", follow_redirects=False).headers["location"]
        == "/root/api/openapi.json"
    )


@pytest.mark.asyncio
async def test_gateway_query_decode_failure_falls_back_empty_query() -> None:
    class BadQuery:
        def decode(self, encoding: str) -> str:
            raise UnicodeError("bad")

    async def api(scope: Scope, receive: Receive, send: Send) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    gw = make_gateway_app(
        api_app=api,
        resolve_upstream=lambda: "http://127.0.0.1:9",
        prefix="/api",
        mount="",
        opts=GatewayProxyOptions(),
        upstream_sem=None,
        shared_httpx_client=lambda: None,  # type: ignore[arg-type]
        prom_metrics=None,
        prom_path="/metrics",
        access_log=True,
        log_sensitive_query_keys=frozenset(),
    )
    sent: list[dict[str, Any]] = []

    async def send(msg: MutableMapping[str, Any]) -> None:
        sent.append(dict(msg))

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    await gw(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/healthz",
            "headers": [],
            "query_string": BadQuery(),
        },
        receive,
        send,
    )
    assert sent[0]["status"] == 200


@pytest.mark.asyncio
async def test_gateway_metrics_observe_errors_are_ignored() -> None:
    class Counter:
        def labels(self, **kwargs: object) -> Counter:
            return self

        def inc(self) -> None:
            return None

    class Histogram:
        def labels(self, **kwargs: object) -> Histogram:
            return self

        def observe(self, value: float) -> None:
            raise RuntimeError("metrics broken")

    async def api(scope: Scope, receive: Receive, send: Send) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    gw = make_gateway_app(
        api_app=api,
        resolve_upstream=lambda: "http://127.0.0.1:9",
        prefix="/api",
        mount="",
        opts=GatewayProxyOptions(),
        upstream_sem=None,
        shared_httpx_client=lambda: None,  # type: ignore[arg-type]
        prom_metrics=(Counter(), Histogram()),
        prom_path="/metrics",
        access_log=False,
        log_sensitive_query_keys=frozenset(),
    )
    sent: list[dict[str, Any]] = []

    async def send(msg: MutableMapping[str, Any]) -> None:
        sent.append(dict(msg))

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    await gw({"type": "http", "method": "GET", "path": "/api/x", "headers": []}, receive, send)
    assert sent[0]["status"] == 200


@pytest.mark.asyncio
async def test_gateway_metrics_endpoint_accepts_bytes_content_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Counter:
        def labels(self, **kwargs: object) -> Counter:
            return self

        def inc(self) -> None:
            return None

    class Histogram:
        def labels(self, **kwargs: object) -> Histogram:
            return self

        def observe(self, value: float) -> None:
            return None

    fake_pc = types.SimpleNamespace(
        generate_latest=lambda: b"metrics",
        CONTENT_TYPE_LATEST=b"text/plain; version=0.0.4",
    )
    monkeypatch.setattr("fluxlit.gateway.dispatch.importlib.import_module", lambda name: fake_pc)
    gw = make_gateway_app(
        api_app=FastAPI(),
        resolve_upstream=lambda: "http://127.0.0.1:9",
        prefix="/api",
        mount="",
        opts=GatewayProxyOptions(),
        upstream_sem=None,
        shared_httpx_client=lambda: None,  # type: ignore[arg-type]
        prom_metrics=(Counter(), Histogram()),
        prom_path="/metrics",
        access_log=False,
        log_sensitive_query_keys=frozenset(),
    )
    sent: list[dict[str, Any]] = []

    async def send(msg: MutableMapping[str, Any]) -> None:
        sent.append(dict(msg))

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    await gw({"type": "http", "method": "GET", "path": "/metrics", "headers": []}, receive, send)
    assert sent[0]["headers"] == [(b"content-type", b"text/plain; version=0.0.4")]
    assert sent[1]["body"] == b"metrics"


def _fluxlit_gateway_requests_total(text: str, *, dispatch: str, method_kind: str) -> float:
    for line in text.splitlines():
        if not line.startswith("fluxlit_gateway_requests_total{"):
            continue
        if f'dispatch="{dispatch}"' in line and f'method_kind="{method_kind}"' in line:
            return float(line.rsplit(None, 1)[-1])
    return 0.0


def test_prometheus_request_counter_increments_for_streamlit_and_api_dispatch() -> None:
    pytest.importorskip("prometheus_client")
    from fluxlit.config import FluxlitSettings

    settings = FluxlitSettings(enable_gateway_prometheus_metrics=True)
    gw = build_gateway(
        FastAPI(),
        "http://127.0.0.1:9",
        api_prefix="/api",
        proxy_settings=settings,
    )
    client = TestClient(gw)
    m0 = client.get("/__fluxlit/metrics").text
    n_st_0 = _fluxlit_gateway_requests_total(m0, dispatch="streamlit", method_kind="GET")
    client.get("/some-proxied-path")
    m1 = client.get("/__fluxlit/metrics").text
    n_st_1 = _fluxlit_gateway_requests_total(m1, dispatch="streamlit", method_kind="GET")
    assert n_st_1 >= n_st_0 + 1.0

    n_api_0 = _fluxlit_gateway_requests_total(m1, dispatch="api", method_kind="GET")
    client.get("/api/healthz")
    m2 = client.get("/__fluxlit/metrics").text
    n_api_1 = _fluxlit_gateway_requests_total(m2, dispatch="api", method_kind="GET")
    assert n_api_1 >= n_api_0 + 1.0
