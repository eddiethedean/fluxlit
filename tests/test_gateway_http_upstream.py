"""HTTP proxy integration against a real threaded ``HTTPServer`` (gzip + redirect)."""

from __future__ import annotations

import gzip
import threading
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from fluxlit.gateway import build_gateway
from fluxlit.runtime import find_free_port


class _UpstreamHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/gz":
            body = gzip.compress(b'{"gzip": true}')
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/redir":
            self.send_response(302)
            self.send_header("Location", "/after-redir")
            self.end_headers()
        elif self.path == "/after-redir":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"after-redir-body")
        elif self.path == "/plain":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", "5")
            self.end_headers()
            self.wfile.write(b"plain")
        else:
            self.send_error(404)

    def log_message(self, _format: str, *_args: Any) -> None:
        return


@pytest.fixture
def http_upstream() -> Generator[str, None, None]:
    port = find_free_port()
    server = HTTPServer(("127.0.0.1", port), _UpstreamHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=10)


def test_proxy_plain_body_from_upstream(http_upstream: str) -> None:
    gateway = build_gateway(FastAPI(), http_upstream, api_prefix="/api")
    client = TestClient(gateway)
    r = client.get("/plain")
    assert r.status_code == 200
    assert r.text == "plain"


def test_proxy_gzip_upstream_decoded_for_client(http_upstream: str) -> None:
    gateway = build_gateway(FastAPI(), http_upstream, api_prefix="/api")
    client = TestClient(gateway)
    r = client.get("/gz")
    assert r.status_code == 200
    assert r.json() == {"gzip": True}
    assert "content-encoding" not in {k.lower() for k in r.headers.keys()}


def test_proxy_follows_redirect_from_upstream(http_upstream: str) -> None:
    gateway = build_gateway(FastAPI(), http_upstream, api_prefix="/api")
    client = TestClient(gateway)
    r = client.get("/redir")
    assert r.status_code == 200
    assert r.text == "after-redir-body"
