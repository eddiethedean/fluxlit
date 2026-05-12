"""Tests for :class:`fluxlit.application.public_urls.FluxLitPublicUrls`."""

from __future__ import annotations

from starlette.requests import Request

from fluxlit import FluxLit


def _request(
    method: str,
    path: str,
    *,
    scheme: str = "http",
    server: tuple[str, int] = ("testserver", 80),
) -> Request:
    p = path if path.startswith("/") else f"/{path}"
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": method,
            "path": p,
            "raw_path": p.encode("latin-1"),
            "root_path": "",
            "scheme": scheme,
            "client": ("127.0.0.1", 12345),
            "server": server,
            "headers": [],
        }
    )


def test_urls_no_mount_matches_gateway_paths() -> None:
    fl = FluxLit(title="T")
    req = _request("GET", "/")
    assert fl.urls.app_base(req) == "http://testserver"
    assert fl.urls.api_base(req) == "http://testserver/api"
    assert fl.urls.docs_url(req) == "http://testserver/api/docs"
    assert fl.urls.redoc_url(req) == "http://testserver/api/redoc"
    assert fl.urls.openapi_url(req) == "http://testserver/api/openapi.json"
    assert fl.urls.health_url(req) == "http://testserver/api/healthz"
    assert fl.urls.ready_url(req) == "http://testserver/api/readyz"


def test_urls_with_root_path_matches_prefixed_docs() -> None:
    base = FluxLit(title="T")
    fl = FluxLit(title="T", settings=base.settings.model_copy(update={"root_path": "/myapp"}))
    req = _request("GET", "/myapp/")
    assert fl.urls.app_base(req) == "http://testserver/myapp"
    assert fl.urls.api_base(req) == "http://testserver/myapp/api"
    assert fl.urls.docs_url(req) == "http://testserver/myapp/api/docs"


def test_urls_custom_api_mount_path() -> None:
    base = FluxLit(title="T")
    fl = FluxLit(
        title="T",
        settings=base.settings.model_copy(update={"api_mount_path": "/v1"}),
    )
    req = _request("GET", "/")
    assert fl.urls.api_base(req) == "http://testserver/v1"
    assert fl.urls.health_url(req) == "http://testserver/v1/healthz"


def test_urls_public_base_url_origin_only_appends_mount() -> None:
    base = FluxLit(title="T")
    fl = FluxLit(
        title="T",
        settings=base.settings.model_copy(
            update={"public_base_url": "https://app.example.com", "root_path": "/myapp"}
        ),
    )
    req = _request("GET", "/")
    assert fl.urls.app_base(req) == "https://app.example.com/myapp"
    assert fl.urls.api_base(req) == "https://app.example.com/myapp/api"


def test_urls_public_base_url_with_path_used_as_app_base() -> None:
    base = FluxLit(title="T")
    fl = FluxLit(
        title="T",
        settings=base.settings.model_copy(
            update={"public_base_url": "https://cdn.example.com/myapp"}
        ),
    )
    req = _request("GET", "/")
    assert fl.urls.app_base(req) == "https://cdn.example.com/myapp"
    assert fl.urls.api_base(req) == "https://cdn.example.com/myapp/api"


def test_urls_for_page_and_query() -> None:
    base = FluxLit(title="T")
    fl = FluxLit(title="T", settings=base.settings.model_copy(update={"root_path": "/x"}))
    req = _request("GET", "/")
    assert fl.urls.for_page(req, "/reports") == "http://testserver/x/reports"
    assert fl.urls.for_page(req, "dash", query={"a": "1 2", "b": "&"}) == (
        "http://testserver/x/dash?a=1+2&b=%26"
    )


def test_urls_docs_redoc_openapi_disabled_when_false() -> None:
    fl = FluxLit(
        title="T",
        fastapi_kwargs={"docs_url": None, "redoc_url": None, "openapi_url": None},
    )
    req = _request("GET", "/")
    assert fl.urls.docs_url(req) is None
    assert fl.urls.redoc_url(req) is None
    assert fl.urls.openapi_url(req) is None


def test_urls_public_base_url_origin_only_no_mount() -> None:
    base = FluxLit(title="T")
    fl = FluxLit(
        title="T",
        settings=base.settings.model_copy(update={"public_base_url": "https://app.example.com"}),
    )
    req = _request("GET", "/")
    assert fl.urls.app_base(req) == "https://app.example.com"
    assert fl.urls.api_base(req) == "https://app.example.com/api"


def test_urls_api_mount_path_without_leading_slash() -> None:
    base = FluxLit(title="T")
    fl = FluxLit(title="T", settings=base.settings.model_copy(update={"api_mount_path": "v2"}))
    req = _request("GET", "/")
    assert fl.urls.api_base(req) == "http://testserver/v2"


def test_urls_docs_url_empty_string_joins_like_disabled_suffix() -> None:
    fl = FluxLit(title="T", fastapi_kwargs={"docs_url": ""})
    req = _request("GET", "/")
    assert fl.urls.docs_url(req) == fl.urls.api_base(req)


def test_urls_for_page_root_path() -> None:
    base = FluxLit(title="T")
    fl = FluxLit(title="T", settings=base.settings.model_copy(update={"root_path": "/x"}))
    req = _request("GET", "/")
    assert fl.urls.for_page(req, "/") == "http://testserver/x/"


def test_urls_public_base_url_invalid_falls_back_to_request() -> None:
    base = FluxLit(title="T")
    fl = FluxLit(
        title="T",
        settings=base.settings.model_copy(update={"public_base_url": "not-an-absolute-url"}),
    )
    req = _request("GET", "/")
    assert fl.urls.app_base(req) == "http://testserver"


def test_flux_lit_public_urls_all_exported() -> None:
    mod = __import__("fluxlit.application.public_urls", fromlist=["*"])
    assert "FluxLitPublicUrls" in mod.__all__
