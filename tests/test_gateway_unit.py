from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient
from starlette.types import Receive, Scope, Send
from starlette.websockets import WebSocketDisconnect

from fluxlit.gateway import (
    _build_target_url,
    _filter_request_headers,
    _forwarded_upstream_header_pairs,
    _not_found,
    _parse_ws_target,
    _port_from_host_header,
    _proxy_http,
    _public_host_from_scope,
    _request_id_from_scope,
    _strip_prefix_scope,
    _upstream_host_header,
    build_gateway,
    normalize_root_mount,
    split_gateway_paths,
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

    with patch("fluxlit.gateway.httpx.AsyncClient", _FakeAsyncClient):
        sent: list[dict[str, Any]] = []

        async def send(msg: MutableMapping[str, Any]) -> None:
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
            await _proxy_http(scope, receive, send, "http://127.0.0.1:9", "/x")

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

    with patch("fluxlit.gateway.httpx.AsyncClient", _FakeAsyncClient):
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
        await _proxy_http(scope, receive, send, "http://127.0.0.1:9", "/")

    start = sent[0]
    assert start["type"] == "http.response.start"
    hdrs = {k.decode(): v.decode() for k, v in start["headers"]}
    assert hdrs["content-type"] == "text/html"
    assert "content-encoding" not in hdrs
    assert hdrs["content-length"] == str(len(decoded))
    assert sent[1] == {"type": "http.response.body", "body": decoded}
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

    with patch("fluxlit.gateway.httpx.AsyncClient", _FakeAsyncClient):
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
        await _proxy_http(scope, receive, send, "http://127.0.0.1:9", "/")

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
