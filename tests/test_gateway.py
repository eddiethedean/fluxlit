from __future__ import annotations

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from fluxlit.gateway import build_gateway


@pytest.fixture
def api() -> FastAPI:
    app = FastAPI()

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"ok": "pong"}

    return app


def test_api_routes_are_prefixed_with_api(api: FastAPI) -> None:
    gateway = build_gateway(api, "http://127.0.0.1:9")
    client = TestClient(gateway)
    res = client.get("/api/ping")
    assert res.status_code == 200
    assert res.json() == {"ok": "pong"}


def test_openapi_available_under_api_prefix(api: FastAPI) -> None:
    gateway = build_gateway(api, "http://127.0.0.1:9")
    client = TestClient(gateway)
    res = client.get("/api/openapi.json")
    assert res.status_code == 200
    body = res.json()
    assert "/ping" in body.get("paths", {})
