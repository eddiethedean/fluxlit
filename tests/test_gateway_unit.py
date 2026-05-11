from __future__ import annotations

import asyncio
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
    assert normalize_root_mount(" /myapp/ ") == "/myapp"
    assert normalize_root_mount("") == ""
    assert split_gateway_paths("/myapp/api/x", "/myapp") == ("/api/x", "/myapp/api/x")
    assert split_gateway_paths("/_stcore/stream", "/myapp") == (
        "/_stcore/stream",
        "/myapp/_stcore/stream",
    )
    assert split_gateway_paths("/api/x", "/myapp") == ("/api/x", "/myapp/api/x")
    assert split_gateway_paths("/api/x", "") == ("/api/x", "/api/x")


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


def test_build_gateway_prometheus_metrics_endpoint() -> None:
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
    r = client.get("/__fluxlit/metrics")
    assert r.status_code == 200
    assert "fluxlit_gateway_requests_total" in r.text


def test_gateway_prometheus_metric_contract_documents_stable_names_and_labels() -> None:
    from fluxlit.gateway.metrics import GATEWAY_PROMETHEUS_METRICS

    by_name = {str(item["name"]): item for item in GATEWAY_PROMETHEUS_METRICS}
    assert by_name["fluxlit_gateway_requests_total"]["labels"] == ("dispatch", "method_kind")
    assert by_name["fluxlit_gateway_request_duration_seconds"]["labels"] == ("dispatch",)
    assert {item["stability"] for item in GATEWAY_PROMETHEUS_METRICS} == {"stable"}


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
