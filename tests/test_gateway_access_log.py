"""Gateway access_log emits structured INFO logs when enabled."""

from __future__ import annotations

import logging

import pytest
from fastapi import FastAPI

from fluxlit.config import FluxlitSettings


def _mini_api() -> FastAPI:
    api = FastAPI()

    @api.get("/healthz")
    def _healthz() -> dict[str, str]:
        return {"status": "ok"}

    return api


def test_gateway_access_log_emits_info_with_extra(
    caplog: pytest.LogCaptureFixture,
    gateway_test_client_factory,
) -> None:
    caplog.set_level(logging.INFO, logger="fluxlit.gateway")
    client = gateway_test_client_factory(
        api_app=_mini_api(),
        access_log=True,
    )
    client.get("/api/healthz", headers={"X-Request-ID": "access-log-test"})
    api_records = [
        r for r in caplog.records if r.name == "fluxlit.gateway" and r.levelno == logging.INFO
    ]
    assert api_records, "expected INFO from fluxlit.gateway"
    assert any(getattr(r, "fluxlit_dispatch", None) == "api" for r in api_records)
    assert any("access-log-test" in r.getMessage() for r in api_records)


def test_gateway_debug_log_extra_includes_redacted_query(
    caplog: pytest.LogCaptureFixture,
    gateway_test_client_factory,
) -> None:
    caplog.set_level(logging.DEBUG, logger="fluxlit.gateway")
    client = gateway_test_client_factory(
        api_app=_mini_api(),
        access_log=False,
        proxy_settings=FluxlitSettings(url_session_query_param="fluxlit_sid"),
    )
    client.get("/api/healthz?fluxlit_sid=topsecret&other=ok")
    rec = next(r for r in caplog.records if r.name == "fluxlit.gateway")
    q = getattr(rec, "query", "")
    assert "topsecret" not in q
    assert "redacted" in q.lower()
    assert "other" in q


def test_gateway_access_log_default_stays_debug_for_streamlit_path(
    caplog: pytest.LogCaptureFixture,
    gateway_test_client_factory,
) -> None:
    caplog.set_level(logging.INFO, logger="fluxlit.gateway")
    client = gateway_test_client_factory(api_app=_mini_api(), access_log=False)
    client.get("/some-streamlit-path")
    info_gateway = [
        r for r in caplog.records if r.name == "fluxlit.gateway" and r.levelno == logging.INFO
    ]
    assert not info_gateway
