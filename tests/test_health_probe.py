"""Unit tests for :func:`fluxlit.health.probe_streamlit_ready`."""

from __future__ import annotations

import threading
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from fluxlit.health import probe_streamlit_ready
from fluxlit.runtime import find_free_port


class _RootOkHandler(BaseHTTPRequestHandler):
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


class _Root500Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(500)
        self.end_headers()

    def log_message(self, _format: str, *_args: Any) -> None:
        return


class _Root404Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(404)
        self.end_headers()

    def log_message(self, _format: str, *_args: Any) -> None:
        return


@pytest.fixture
def http_root_ok() -> Generator[str, None, None]:
    port = find_free_port()
    server = HTTPServer(("127.0.0.1", port), _RootOkHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=10)


@pytest.fixture
def http_root_500() -> Generator[str, None, None]:
    port = find_free_port()
    server = HTTPServer(("127.0.0.1", port), _Root500Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=10)


@pytest.fixture
def http_root_404() -> Generator[str, None, None]:
    port = find_free_port()
    server = HTTPServer(("127.0.0.1", port), _Root404Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=10)


@pytest.mark.asyncio
async def test_probe_ready_when_upstream_returns_200(
    http_root_ok: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FLUXLIT_STREAMLIT_UPSTREAM", http_root_ok)
    monkeypatch.delenv("FLUXLIT_STREAMLIT_UPSTREAM_FILE", raising=False)
    ok, detail = await probe_streamlit_ready(timeout_s=2.0)
    assert ok is True
    assert detail == "ok"


@pytest.mark.asyncio
async def test_probe_not_ready_on_upstream_500(
    http_root_500: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FLUXLIT_STREAMLIT_UPSTREAM", http_root_500)
    monkeypatch.delenv("FLUXLIT_STREAMLIT_UPSTREAM_FILE", raising=False)
    ok, detail = await probe_streamlit_ready(timeout_s=2.0)
    assert ok is False
    assert "500" in detail


@pytest.mark.asyncio
async def test_probe_not_ready_on_upstream_404(
    http_root_404: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FLUXLIT_STREAMLIT_UPSTREAM", http_root_404)
    monkeypatch.delenv("FLUXLIT_STREAMLIT_UPSTREAM_FILE", raising=False)
    ok, detail = await probe_streamlit_ready(timeout_s=2.0)
    assert ok is False
    assert "404" in detail


@pytest.mark.asyncio
async def test_probe_not_ready_on_connection_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLUXLIT_STREAMLIT_UPSTREAM", "http://127.0.0.1:59111")
    monkeypatch.delenv("FLUXLIT_STREAMLIT_UPSTREAM_FILE", raising=False)
    ok, detail = await probe_streamlit_ready(timeout_s=0.5)
    assert ok is False
    assert detail


@pytest.mark.asyncio
async def test_probe_not_configured_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLUXLIT_STREAMLIT_UPSTREAM", raising=False)
    monkeypatch.delenv("FLUXLIT_STREAMLIT_UPSTREAM_FILE", raising=False)
    ok, detail = await probe_streamlit_ready()
    assert ok is True
    assert detail == "not_configured"
