"""Assert upstream HTTP requests get expected Host and X-Forwarded-* headers."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from fluxlit.gateway import _proxy_http


@pytest.mark.asyncio
async def test_proxy_http_sets_host_and_forwarded_headers() -> None:
    captured: dict[str, Any] = {}

    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> _FakeAsyncClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        def build_request(
            self,
            method: str,
            url: str,
            headers: httpx.Headers | None = None,
        ) -> object:
            captured["method"] = method
            captured["url"] = url
            captured["headers"] = dict(headers) if headers is not None else {}
            return object()

        async def send(self, *args: object, **kwargs: object) -> httpx.Response:
            return httpx.Response(200, content=b"ok")

    with patch("fluxlit.gateway.httpx.AsyncClient", _FakeAsyncClient):
        sent: list[dict[str, Any]] = []

        async def send(msg: MutableMapping[str, Any]) -> None:
            sent.append(dict(msg))

        async def receive() -> dict[str, Any]:
            return {"type": "http.request", "body": b"", "more_body": False}

        scope: dict[str, Any] = {
            "type": "http",
            "method": "GET",
            "path": "/st/asset.js",
            "headers": [
                (b"host", b"public.example:8443"),
                (b"x-request-id", b"abc"),
            ],
            "query_string": b"",
            "scheme": "https",
            "client": ("198.51.100.2", 4444),
        }
        await _proxy_http(
            scope,
            receive,
            send,
            "http://127.0.0.1:8501",
            "/st/asset.js",
            forwarded_prefix="/myapp",
        )

    h = captured["headers"]
    assert captured["url"] == "http://127.0.0.1:8501/st/asset.js"
    assert h.get("host") == "public.example:8443"
    assert h.get("x-forwarded-host") == "public.example:8443"
    assert h.get("x-forwarded-proto") == "https"
    assert h.get("x-forwarded-port") == "8443"
    assert h.get("x-forwarded-for") == "198.51.100.2"
    assert h.get("x-forwarded-prefix") == "/myapp"
    assert h.get("x-request-id") == "abc"


@pytest.mark.asyncio
async def test_proxy_http_https_scope_sets_forwarded_proto() -> None:
    captured: dict[str, Any] = {}

    class _FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> _FakeAsyncClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        def build_request(
            self,
            method: str,
            url: str,
            headers: httpx.Headers | None = None,
        ) -> object:
            captured["headers"] = dict(headers) if headers is not None else {}
            return object()

        async def send(self, *args: object, **kwargs: object) -> httpx.Response:
            return httpx.Response(200, content=b"ok")

    with patch("fluxlit.gateway.httpx.AsyncClient", _FakeAsyncClient):
        sent: list[dict[str, Any]] = []

        async def send_asgi(msg: MutableMapping[str, Any]) -> None:
            sent.append(dict(msg))

        async def receive() -> dict[str, Any]:
            return {"type": "http.request", "body": b"", "more_body": False}

        scope: dict[str, Any] = {
            "type": "http",
            "method": "GET",
            "path": "/x",
            "headers": [(b"host", b"h.example")],
            "query_string": b"",
            "scheme": "https",
            "client": None,
        }
        await _proxy_http(scope, receive, send_asgi, "http://10.0.0.1:8501", "/x")

    assert captured["headers"]["x-forwarded-proto"] == "https"
