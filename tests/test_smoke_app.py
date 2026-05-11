"""Canonical smoke app contract tests."""

from __future__ import annotations

from examples.smoke_app.app import app
from fluxlit.testing import FluxLitTestClient


def test_smoke_app_api_contract() -> None:
    client = FluxLitTestClient(app)
    r = client.api_get("/smoke")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "marker": "fluxlit_smoke_ok"}


def test_smoke_app_request_id_echo() -> None:
    client = FluxLitTestClient(app)
    r = client.api_get("/request-id", headers={"X-Request-ID": "smoke-rid"})
    assert r.status_code == 200
    assert r.json() == {"request_id": "smoke-rid"}
