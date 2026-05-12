"""Tests for ``FLUXLIT_DEBUG`` / ``--debug`` and the ``/__fluxlit/debug`` gateway endpoint."""

from __future__ import annotations

from starlette.testclient import TestClient

from fluxlit import FluxLit
from fluxlit.config import FluxlitSettings
from fluxlit.gateway import build_gateway
from fluxlit.gateway.debug_ring import recent_gateway_dispatches, record_gateway_dispatch
from fluxlit.runtime.debug_settings import merge_debug_settings


def test_merge_debug_settings_bootstrap() -> None:
    s = merge_debug_settings(
        FluxlitSettings(debug=True, enable_gateway_access_log=False, log_level="info")
    )
    assert s.enable_gateway_access_log is True
    assert s.enable_request_logging is True
    assert s.log_level == "debug"


def test_merge_debug_settings_respects_explicit_log_level() -> None:
    s = merge_debug_settings(FluxlitSettings(debug=True, log_level="warning"))
    assert s.log_level == "warning"


def test_merge_debug_settings_idempotent() -> None:
    s = merge_debug_settings(
        FluxlitSettings(
            debug=True,
            enable_gateway_access_log=True,
            enable_request_logging=True,
            log_level="debug",
        )
    )
    assert s is merge_debug_settings(s)


def test_fluxlit_applies_debug_merge_before_wiring() -> None:
    fl = FluxLit(title="D", settings=FluxlitSettings(debug=True, enable_gateway_access_log=False))
    assert fl.settings.enable_gateway_access_log is True


def test_debug_endpoint_returns_json_when_debug_enabled() -> None:
    fl = FluxLit(title="D", settings=FluxlitSettings(debug=True))
    client = TestClient(build_gateway(fl.api, "http://127.0.0.1:9", proxy_settings=fl.settings))
    res = client.get("/__fluxlit/debug")
    assert res.status_code == 200
    body = res.json()
    assert body.get("fluxlit_debug") is True
    assert "settings" in body
    assert "recent_dispatches" in body


def test_debug_gateway_emits_split_log_on_non_snapshot_paths() -> None:
    fl = FluxLit(title="D", settings=FluxlitSettings(debug=True))
    client = TestClient(build_gateway(fl.api, "http://127.0.0.1:9", proxy_settings=fl.settings))
    assert client.get("/api/healthz").status_code == 200


def test_debug_endpoint_disabled_when_api_prefix_conflicts() -> None:
    fl = FluxLit(
        title="D",
        settings=FluxlitSettings(debug=True, api_mount_path="/__fluxlit/debug"),
    )
    client = TestClient(
        build_gateway(
            fl.api,
            "http://127.0.0.1:9",
            api_prefix=fl.settings.api_mount_path,
            proxy_settings=fl.settings,
        )
    )
    assert client.get("/__fluxlit/debug").status_code == 404


def test_debug_endpoint_not_found_when_debug_disabled() -> None:
    fl = FluxLit(title="D")
    client = TestClient(build_gateway(fl.api, "http://127.0.0.1:9", proxy_settings=fl.settings))
    assert client.get("/__fluxlit/debug").status_code == 404


def test_debug_ring_records_and_lists() -> None:
    record_gateway_dispatch(request_id="r1", dispatch="api", path_in="/api/x")
    rows = recent_gateway_dispatches()
    assert rows and rows[-1]["request_id"] == "r1"


def test_fluxlit_get_client_propagates_request_id_when_debug() -> None:
    fl = FluxLit(title="T", settings=FluxlitSettings(debug=True))
    assert fl.get_client()._propagate_request_id is True
    assert (
        FluxLit(title="T", settings=FluxlitSettings(debug=False)).get_client()._propagate_request_id
        is False
    )
