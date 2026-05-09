from __future__ import annotations

import logging

import pytest
from starlette.testclient import TestClient

from fluxlit import FluxLit
from fluxlit.config import FluxlitSettings
from fluxlit.gateway import build_gateway


def test_page_registration() -> None:
    app = FluxLit(title="T")

    @app.page("/dash", title="Dash")
    def dash(st, client) -> None:  # noqa: ARG001
        pass

    paths = {p[0]: p[1] for p in app.pages}
    assert paths["/dash"] == "Dash"


def test_enable_request_logging_emits_api_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = FluxlitSettings(enable_request_logging=True)
    fl = FluxLit(title="T", settings=settings)

    @fl.api.get("/echo")
    def echo() -> dict[str, str]:
        return {"ok": "1"}

    caplog.set_level(logging.INFO, logger="fluxlit.api")
    gateway = build_gateway(fl.api, "http://127.0.0.1:9", api_prefix="/api")
    client = TestClient(gateway)
    client.get("/api/echo")
    assert any(r.name == "fluxlit.api" and "GET" in r.getMessage() for r in caplog.records)
