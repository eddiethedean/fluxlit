from __future__ import annotations

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from fluxlit.security_middleware import SecurityHeadersMiddleware


async def _hello(_: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


def test_security_headers_middleware_sets_baseline_headers() -> None:
    app = Starlette(
        routes=[Route("/", _hello)],
        middleware=[Middleware(SecurityHeadersMiddleware)],
    )
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "SAMEORIGIN"


def test_security_headers_adds_hsts_when_forwarded_proto_https() -> None:
    app = Starlette(
        routes=[Route("/", _hello)],
        middleware=[Middleware(SecurityHeadersMiddleware)],
    )
    client = TestClient(app)
    r = client.get("/", headers={"X-Forwarded-Proto": "https"})
    assert r.headers.get("strict-transport-security", "").startswith("max-age=")
