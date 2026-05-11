"""Dynamic upstream resolver switches Streamlit proxy target per request."""

from __future__ import annotations

import threading
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from fluxlit.gateway import build_gateway
from fluxlit.runtime import find_free_port


class _MarkHandler(BaseHTTPRequestHandler):
    mark: str = "a"

    def do_GET(self) -> None:
        if self.path in {"/", "/index"}:
            body = self.mark.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def log_message(self, _format: str, *_args: Any) -> None:
        return


@pytest.fixture
def two_upstreams() -> Generator[tuple[str, str], None, None]:
    port_a = find_free_port()
    port_b = find_free_port()

    class HandlerA(_MarkHandler):
        mark = "upstream-a"

    class HandlerB(_MarkHandler):
        mark = "upstream-b"

    sa = HTTPServer(("127.0.0.1", port_a), HandlerA)
    sb = HTTPServer(("127.0.0.1", port_b), HandlerB)
    ta = threading.Thread(target=sa.serve_forever, daemon=True)
    tb = threading.Thread(target=sb.serve_forever, daemon=True)
    ta.start()
    tb.start()
    try:
        yield f"http://127.0.0.1:{port_a}", f"http://127.0.0.1:{port_b}"
    finally:
        sa.shutdown()
        sb.shutdown()
        ta.join(timeout=10)
        tb.join(timeout=10)


def test_gateway_respects_upstream_resolver_switch(two_upstreams: tuple[str, str]) -> None:
    url_a, url_b = two_upstreams
    current: list[str] = [url_a]

    def resolver() -> str:
        return current[0]

    gateway = build_gateway(FastAPI(), "", upstream_resolver=resolver, api_prefix="/api")
    client = TestClient(gateway)
    assert client.get("/").text == "upstream-a"
    current[0] = url_b
    assert client.get("/").text == "upstream-b"
