"""Gateway behavior and OpenAPI via :class:`fluxlit.testing.FluxLitTestClient`."""

from __future__ import annotations

from fluxlit.testing import FluxLitTestClient


def test_healthz_on_gateway(fluxlit_client: FluxLitTestClient) -> None:
    r = fluxlit_client.api_get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_openapi_excludes_healthz(fluxlit_client: FluxLitTestClient) -> None:
    paths = fluxlit_client.openapi().get("paths", {})
    assert "/healthz" not in paths
    assert "/readyz" not in paths


def test_openapi_includes_demo_routes(fluxlit_client: FluxLitTestClient) -> None:
    paths = fluxlit_client.openapi().get("paths", {})
    assert "/auth/register" in paths
    assert "/auth/login" in paths
    assert "/users/me" in paths
    assert "/health/db" in paths
