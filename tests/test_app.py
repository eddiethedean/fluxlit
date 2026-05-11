from __future__ import annotations

import logging
import sys
import types

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from fluxlit import FluxLit
from fluxlit.config import FluxlitSettings
from fluxlit.gateway import build_gateway


def test_fluxlit_constructor_merges_streamlit_settings() -> None:
    base = FluxlitSettings(
        streamlit_page_config={"layout": "wide"},
        streamlit_run_cli_args=["--logger.level", "error"],
    )
    fl = FluxLit(
        settings=base,
        streamlit_page_config={"page_icon": "🚀"},
        streamlit_run_args=["--theme.base", "dark"],
    )
    assert fl.settings.streamlit_page_config == {"layout": "wide", "page_icon": "🚀"}
    assert fl.settings.streamlit_run_cli_args == [
        "--logger.level",
        "error",
        "--theme.base",
        "dark",
    ]


def test_fastapi_kwargs_cannot_override_root_path() -> None:
    settings = FluxlitSettings(root_path="/app")
    fl = FluxLit(
        settings=settings,
        fastapi_kwargs={"root_path": "/wrong", "openapi_url": "/o.json"},
    )
    assert fl.api.root_path == "/app"
    assert fl.api.openapi_url == "/o.json"


def test_cors_middleware_kwargs_duplicate_allow_origins_is_ignored() -> None:
    """allow_origins in cors_middleware_kwargs would duplicate the middleware kw and crash."""
    settings = FluxlitSettings(
        cors_allow_origins=["http://localhost:3000"],
        cors_middleware_kwargs={
            "allow_origins": ["http://evil.example"],
            "max_age": 10,
        },
    )
    fl = FluxLit(settings=settings)
    client = TestClient(fl.api)
    r = client.get("/healthz", headers={"Origin": "http://localhost:3000"})
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_fastapi_kwargs_passthrough_openapi_url() -> None:
    fl = FluxLit(title="T", fastapi_kwargs={"openapi_url": "/custom-openapi.json"})
    client = TestClient(fl.api)
    r = client.get("/custom-openapi.json")
    assert r.status_code == 200
    assert "openapi" in r.json()
    assert client.get("/openapi.json").status_code == 404


def test_cors_middleware_expose_headers_visible_to_browser() -> None:
    settings = FluxlitSettings(
        cors_allow_origins=["https://app.example"],
        cors_middleware_kwargs={"expose_headers": ["X-App-Version"]},
    )
    fl = FluxLit(settings=settings)

    @fl.api.get("/versioned", include_in_schema=False)
    def versioned() -> dict[str, str]:
        from starlette.responses import JSONResponse

        return JSONResponse(
            content={"v": "1"},
            headers={"X-App-Version": "1.0.0"},
        )

    client = TestClient(fl.api)
    r = client.get(
        "/versioned",
        headers={"Origin": "https://app.example"},
    )
    assert r.status_code == 200
    exposed = (r.headers.get("access-control-expose-headers") or "").lower()
    assert "x-app-version" in exposed


def test_cors_middleware_merges_extra_kwargs() -> None:
    settings = FluxlitSettings(
        cors_allow_origins=["http://localhost:3000"],
        cors_middleware_kwargs={"max_age": 1234},
    )
    fl = FluxLit(settings=settings)
    client = TestClient(fl.api)
    r = client.options(
        "/healthz",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.status_code == 200
    assert r.headers.get("access-control-max-age") == "1234"


def test_replacing_api_clears_unified_asgi_cache() -> None:
    fl = FluxLit(title="T")
    fl._unified_asgi_cache = object()  # type: ignore[assignment]
    fl.api = FastAPI(title="replaced")
    assert fl._unified_asgi_cache is None
    assert fl.api.title == "replaced"


def test_page_registration() -> None:
    app = FluxLit(title="T")

    @app.page("/dash", title="Dash")
    def dash(st, client) -> None:  # noqa: ARG001
        pass

    paths = {p[0]: p[1] for p in app.pages}
    assert paths["/dash"] == "Dash"


def test_discover_pages_requires_package() -> None:
    fl = FluxLit(title="T")
    bare = types.ModuleType("fluxlit_test_bare_mod")
    sys.modules["fluxlit_test_bare_mod"] = bare
    try:
        with pytest.raises(TypeError, match="must be a package"):
            fl.discover_pages("pages", package="fluxlit_test_bare_mod")
    finally:
        sys.modules.pop("fluxlit_test_bare_mod", None)


def test_discover_pages_import_error_for_missing_subpackage(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pkg = tmp_path / "pkg_pages"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    fl = FluxLit(title="T")
    with pytest.raises(ImportError, match="Cannot import page package"):
        fl.discover_pages("missing_pages", package="pkg_pages")


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


def test_readyz_streamlit_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLUXLIT_STREAMLIT_UPSTREAM", raising=False)
    monkeypatch.delenv("FLUXLIT_STREAMLIT_UPSTREAM_FILE", raising=False)
    fl = FluxLit(title="T")
    client = TestClient(fl.api)
    r = client.get("/readyz")
    assert r.status_code == 200
    assert r.json() == {"status": "ready", "streamlit": "not_configured"}


def test_readyz_fails_when_upstream_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLUXLIT_STREAMLIT_UPSTREAM", "http://127.0.0.1:59123")
    fl = FluxLit(title="T")
    client = TestClient(fl.api)
    r = client.get("/readyz")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "not_ready"
    assert "detail" in body


def test_enable_security_headers_adds_x_content_type_options() -> None:
    settings = FluxlitSettings(enable_security_headers=True)
    fl = FluxLit(title="T", settings=settings)
    gateway = build_gateway(fl.api, "http://127.0.0.1:9", api_prefix="/api")
    client = TestClient(gateway)
    r = client.get("/api/healthz")
    assert r.status_code == 200
    assert r.headers.get("x-content-type-options") == "nosniff"
