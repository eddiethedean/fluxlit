from __future__ import annotations

import logging
import re

import pytest
from fastapi import FastAPI, Request
from starlette.testclient import TestClient

from fluxlit import FluxLit
from fluxlit.gateway import build_gateway


@pytest.fixture
def api() -> FastAPI:
    app = FastAPI()

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"ok": "pong"}

    return app


def test_api_routes_are_prefixed_with_api(api: FastAPI) -> None:
    gateway = build_gateway(api, "http://127.0.0.1:9", api_prefix="/api")
    client = TestClient(gateway)
    res = client.get("/api/ping")
    assert res.status_code == 200
    assert res.json() == {"ok": "pong"}


def test_openapi_available_under_api_prefix(api: FastAPI) -> None:
    gateway = build_gateway(api, "http://127.0.0.1:9", api_prefix="/api")
    client = TestClient(gateway)
    res = client.get("/api/openapi.json")
    assert res.status_code == 200
    body = res.json()
    assert "/ping" in body.get("paths", {})


def test_swagger_ui_loads_openapi_under_api_prefix(api: FastAPI) -> None:
    """Embedded OpenAPI URL must include the gateway prefix (ASGI root_path)."""
    gateway = build_gateway(api, "http://127.0.0.1:9", api_prefix="/api")
    client = TestClient(gateway)
    html = client.get("/api/docs").text
    m = re.search(r"url: '([^']+)'", html)
    assert m is not None
    assert m.group(1) == "/api/openapi.json"
    spec = client.get(m.group(1)).json()
    assert spec.get("openapi", "").startswith("3.")


def test_custom_api_prefix(api: FastAPI) -> None:
    gateway = build_gateway(api, "http://127.0.0.1:9", api_prefix="/x")
    client = TestClient(gateway)
    assert client.get("/x/ping").status_code == 200
    assert client.get("/api/ping").status_code != 200


def test_healthz_available_under_api_prefix() -> None:
    fl = FluxLit(title="T")
    gateway = build_gateway(fl.api, "http://127.0.0.1:9", api_prefix="/api")
    client = TestClient(gateway)
    res = client.get("/api/healthz")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_healthz_not_in_openapi() -> None:
    fl = FluxLit(title="T")
    gateway = build_gateway(fl.api, "http://127.0.0.1:9", api_prefix="/api")
    client = TestClient(gateway)
    body = client.get("/api/openapi.json").json()
    assert "/healthz" not in body.get("paths", {})


def test_gateway_log_includes_request_id(api: FastAPI, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="fluxlit.gateway")
    gateway = build_gateway(api, "http://127.0.0.1:9", api_prefix="/api")
    client = TestClient(gateway)
    client.get("/api/ping", headers={"X-Request-ID": "unit-test-rid"})
    assert any(
        "unit-test-rid" in r.getMessage() for r in caplog.records if r.name == "fluxlit.gateway"
    )


def test_root_docs_redirects_to_prefixed_docs(api: FastAPI) -> None:
    gateway = build_gateway(api, "http://127.0.0.1:9", api_prefix="/api")
    client = TestClient(gateway)
    res = client.get("/docs", follow_redirects=False)
    assert res.status_code == 307
    assert res.headers["location"] == "/api/docs"
    assert client.get("/api/docs").status_code == 200


def test_root_redoc_and_openapi_redirect(api: FastAPI) -> None:
    gateway = build_gateway(api, "http://127.0.0.1:9", api_prefix="/v1")
    client = TestClient(gateway)
    assert client.get("/redoc", follow_redirects=False).headers["location"] == "/v1/redoc"
    assert (
        client.get("/openapi.json", follow_redirects=False).headers["location"]
        == "/v1/openapi.json"
    )


def test_non_api_path_returns_502_when_upstream_unreachable(api: FastAPI) -> None:
    """Proxy targets a closed port → httpx.RequestError → 502 Bad Gateway."""
    gateway = build_gateway(api, "http://127.0.0.1:9", api_prefix="/api")
    client = TestClient(gateway)
    res = client.get("/some-streamlit-path")
    assert res.status_code == 502
    assert b"Bad Gateway" in res.content


def test_api_accepts_post_json_body(api: FastAPI) -> None:
    @api.post("/echo")
    async def echo(request: Request) -> dict[str, str]:
        data = await request.json()
        got = data.get("k", "") if isinstance(data, dict) else ""
        return {"got": str(got)}

    gateway = build_gateway(api, "http://127.0.0.1:9", api_prefix="/api")
    client = TestClient(gateway)
    res = client.post("/api/echo", json={"k": "v"})
    assert res.status_code == 200
    assert res.json() == {"got": "v"}
