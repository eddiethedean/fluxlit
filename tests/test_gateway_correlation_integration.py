"""Integration tests: upstream ``X-Request-ID`` and gateway ``httpx.AsyncClient`` settings."""

from __future__ import annotations

import json
import threading
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, ClassVar

import httpx
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from fluxlit.config import FluxlitSettings
from fluxlit.gateway import build_gateway
from fluxlit.runtime import find_free_port


class _HeaderEchoHandler(BaseHTTPRequestHandler):
    """Echo selected request headers as JSON (and optional body length for POST)."""

    last_x_request_id: ClassVar[str] = ""
    last_content_length: ClassVar[int | None] = None

    def _echo(self) -> None:
        type(self).last_x_request_id = self.headers.get("X-Request-Id", "")
        cl = self.headers.get("Content-Length")
        type(self).last_content_length = int(cl) if cl and cl.isdigit() else None
        payload = json.dumps(
            {
                "x_request_id": type(self).last_x_request_id,
                "content_length": type(self).last_content_length,
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        if self.path == "/echo":
            self._echo()
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        if self.path == "/echo":
            length = int(self.headers.get("Content-Length", "0"))
            _ = self.rfile.read(length)
            self._echo()
        else:
            self.send_error(404)

    def log_message(self, _format: str, *_args: Any) -> None:
        return


@pytest.fixture
def echo_upstream() -> Generator[str, None, None]:
    _HeaderEchoHandler.last_x_request_id = ""
    _HeaderEchoHandler.last_content_length = None
    port = find_free_port()
    server = HTTPServer(("127.0.0.1", port), _HeaderEchoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=10)


def test_gateway_upstream_receives_resolved_x_request_id_when_client_omits_header(
    echo_upstream: str,
) -> None:
    gateway = build_gateway(FastAPI(), echo_upstream, api_prefix="/api")
    with TestClient(gateway) as client:
        r1 = client.get("/echo")
        r2 = client.get("/echo")
    assert r1.status_code == 200
    assert r2.status_code == 200
    rid1 = r1.json()["x_request_id"]
    rid2 = r2.json()["x_request_id"]
    assert rid1
    assert rid2
    assert rid1 != rid2


def test_gateway_upstream_x_request_id_matches_client_header_when_present(
    echo_upstream: str,
) -> None:
    gateway = build_gateway(FastAPI(), echo_upstream, api_prefix="/api")
    with TestClient(gateway) as client:
        r = client.get("/echo", headers={"X-Request-ID": "  trace-from-client  "})
    assert r.status_code == 200
    assert r.json()["x_request_id"] == "trace-from-client"


@pytest.fixture
def httpx_init_capture(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Capture kwargs passed to ``httpx.AsyncClient`` inside the gateway lazy client."""
    captured: list[dict[str, Any]] = []

    class _RecordingAsyncClient(httpx.AsyncClient):
        def __init__(self, *args: object, **kwargs: object) -> None:
            captured.append(dict(kwargs))
            super().__init__(*args, **kwargs)

    monkeypatch.setattr("fluxlit.gateway.httpx.AsyncClient", _RecordingAsyncClient)
    return captured


def test_build_gateway_passes_custom_httpx_timeouts_to_async_client(
    echo_upstream: str,
    httpx_init_capture: list[dict[str, Any]],
) -> None:
    settings = FluxlitSettings(
        gateway_upstream_connect_timeout_s=2.25,
        gateway_upstream_read_timeout_s=77.5,
    )
    gateway = build_gateway(FastAPI(), echo_upstream, api_prefix="/api", proxy_settings=settings)
    with TestClient(gateway) as client:
        r = client.get("/echo")
    assert r.status_code == 200
    assert len(httpx_init_capture) == 1
    timeout = httpx_init_capture[0]["timeout"]
    assert isinstance(timeout, httpx.Timeout)
    assert timeout.connect == 2.25
    assert timeout.read == 77.5
    assert "limits" not in httpx_init_capture[0]


def test_build_gateway_passes_httpx_limits_when_max_connections_set(
    echo_upstream: str,
    httpx_init_capture: list[dict[str, Any]],
) -> None:
    settings = FluxlitSettings(
        gateway_httpx_max_connections=12,
        gateway_httpx_max_keepalive_connections=4,
    )
    gateway = build_gateway(FastAPI(), echo_upstream, api_prefix="/api", proxy_settings=settings)
    with TestClient(gateway) as client:
        r = client.get("/echo")
    assert r.status_code == 200
    assert len(httpx_init_capture) == 1
    limits = httpx_init_capture[0]["limits"]
    assert isinstance(limits, httpx.Limits)
    assert limits.max_connections == 12
    assert limits.max_keepalive_connections == 4


def test_build_gateway_post_over_max_proxy_body_returns_413(
    echo_upstream: str,
) -> None:
    """``gateway_max_proxy_request_body_bytes`` yields **413** for an oversized POST body."""
    settings = FluxlitSettings(gateway_max_proxy_request_body_bytes=20)
    gateway = build_gateway(FastAPI(), echo_upstream, api_prefix="/api", proxy_settings=settings)
    with TestClient(gateway) as client:
        r = client.post("/echo", content=b"x" * 50)
    assert r.status_code == 413
    assert b"Payload Too Large" in r.content
