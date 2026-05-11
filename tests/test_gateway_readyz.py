"""Readiness route through the full gateway stack."""

from __future__ import annotations

import threading
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest
from starlette.testclient import TestClient

from fluxlit import FluxLit
from fluxlit.gateway import build_gateway
from fluxlit.runtime import find_free_port


class _RootHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in {"/", ""}:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_error(404)

    def log_message(self, _format: str, *_args: Any) -> None:
        return


class _Root404OnlyHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(404)
        self.end_headers()

    def log_message(self, _format: str, *_args: Any) -> None:
        return


@pytest.fixture
def streamlit_upstream_ok() -> Generator[str, None, None]:
    port = find_free_port()
    server = HTTPServer(("127.0.0.1", port), _RootHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=10)


@pytest.fixture
def streamlit_upstream_root_404() -> Generator[str, None, None]:
    port = find_free_port()
    server = HTTPServer(("127.0.0.1", port), _Root404OnlyHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=10)


def test_readyz_200_when_upstream_ok(
    streamlit_upstream_ok: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FLUXLIT_STREAMLIT_UPSTREAM", streamlit_upstream_ok)
    monkeypatch.delenv("FLUXLIT_STREAMLIT_UPSTREAM_FILE", raising=False)
    fl = FluxLit(title="R")
    gateway = build_gateway(fl.api, "http://127.0.0.1:9", api_prefix="/api")
    client = TestClient(gateway)
    r = client.get("/api/readyz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["streamlit"] == "ok"


def test_readyz_503_when_upstream_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLUXLIT_STREAMLIT_UPSTREAM", "http://127.0.0.1:59222")
    monkeypatch.delenv("FLUXLIT_STREAMLIT_UPSTREAM_FILE", raising=False)
    fl = FluxLit(title="R")
    gateway = build_gateway(fl.api, "http://127.0.0.1:9", api_prefix="/api")
    client = TestClient(gateway)
    r = client.get("/api/readyz")
    assert r.status_code == 503
    assert r.json()["status"] == "not_ready"


def test_readyz_503_when_upstream_root_returns_404(
    streamlit_upstream_root_404: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FLUXLIT_STREAMLIT_UPSTREAM", streamlit_upstream_root_404)
    monkeypatch.delenv("FLUXLIT_STREAMLIT_UPSTREAM_FILE", raising=False)
    fl = FluxLit(title="R")
    gateway = build_gateway(fl.api, "http://127.0.0.1:9", api_prefix="/api")
    client = TestClient(gateway)
    r = client.get("/api/readyz")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "not_ready"
    assert "404" in str(body.get("detail", ""))
