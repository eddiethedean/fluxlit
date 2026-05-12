"""Tests for ``fluxlit.deep_links`` and ``FluxLitPublicUrls.page_url``."""

from __future__ import annotations

import textwrap
from types import SimpleNamespace
from typing import Any

import pytest
from starlette.requests import Request

from fluxlit import FluxLit, FluxLitTestClient, match_nav_page, query_params
from fluxlit.application import public_urls as public_urls_mod


def _request(path: str = "/") -> Request:
    p = path if path.startswith("/") else f"/{path}"
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "path": p,
            "raw_path": p.encode("latin-1"),
            "root_path": "",
            "scheme": "http",
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "headers": [],
        }
    )


def test_page_url_alias_matches_for_page() -> None:
    base = FluxLit(title="T")
    fl = FluxLit(title="T", settings=base.settings.model_copy(update={"root_path": "/app"}))
    req = _request("/")
    assert fl.urls.page_url(req, "/", query={"token": "abc"}) == fl.urls.for_page(
        req, "/", query={"token": "abc"}
    )


def test_query_params_normalizes_lists_and_strings() -> None:
    st = SimpleNamespace(
        query_params={"a": "1", "b": ["x", "y"], "c": [], "d": None},
    )
    assert query_params(st) == {"a": "1", "b": "x"}


def test_query_params_missing_or_empty() -> None:
    assert query_params(SimpleNamespace()) == {}
    assert query_params(SimpleNamespace(query_params=None)) == {}


def test_query_params_keys_raises_falls_back_to_dict() -> None:
    class KeysRaise(dict[str, Any]):
        def keys(self) -> Any:  # type: ignore[override]
            raise RuntimeError("boom")

    st = SimpleNamespace(query_params=KeysRaise(x="1"))
    assert query_params(st) == {"x": "1"}


def test_query_params_keys_raises_logs_when_debug(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    class KeysRaise(dict[str, Any]):
        def keys(self) -> Any:  # type: ignore[override]
            raise RuntimeError("boom")

    monkeypatch.setenv("FLUXLIT_DEBUG", "1")
    st = SimpleNamespace(query_params=KeysRaise(x="1"))
    caplog.set_level(10, logger="fluxlit.deep_links")
    assert query_params(st) == {"x": "1"}
    assert any("query_params" in rec.message for rec in caplog.records)


def test_query_params_get_failure_logs_when_debug(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    class BadQP:
        def keys(self) -> list[str]:
            return ["ok", "bad"]

        def get(self, key: str) -> Any:
            if key == "bad":
                raise RuntimeError("no get")
            return "v"

    monkeypatch.setenv("FLUXLIT_DEBUG", "1")
    caplog.set_level(10, logger="fluxlit.deep_links")
    assert query_params(SimpleNamespace(query_params=BadQP())) == {"ok": "v"}
    assert any("could not read key" in rec.message for rec in caplog.records)


def test_query_params_non_dict_without_keys_returns_empty() -> None:
    st = SimpleNamespace(query_params=object())
    assert query_params(st) == {}


def test_query_params_get_failure_skips_key() -> None:
    class BadQP:
        def keys(self) -> list[str]:
            return ["ok", "bad"]

        def get(self, key: str) -> Any:
            if key == "bad":
                raise RuntimeError("no get")
            return "v"

    assert query_params(SimpleNamespace(query_params=BadQP())) == {"ok": "v"}


def test_match_nav_page_by_title_path_slug_and_stripped() -> None:
    pages = [
        ("/", "Home", None),
        ("/reset", "Reset password", None),
        ("/nested/here", "Deep", None),
    ]
    assert match_nav_page({"page": "Reset password"}, pages) == ("/reset", "Reset password")
    assert match_nav_page({"page": "home"}, pages) == ("/", "Home")
    assert match_nav_page({"page": "/reset"}, pages) == ("/reset", "Reset password")
    assert match_nav_page({"page": "nested/here"}, pages) == ("/nested/here", "Deep")


def test_match_nav_page_custom_key_and_no_match() -> None:
    pages = [("/", "Home")]
    assert match_nav_page({"tab": "Home"}, pages, page_key="tab") == ("/", "Home")
    assert match_nav_page({"page": ""}, pages) is None
    assert match_nav_page({"page": "missing"}, pages) is None


def test_match_nav_page_accepts_two_tuple_pages() -> None:
    pages = [("/", "Home")]
    assert match_nav_page({"page": "Home"}, pages) == ("/", "Home")


def test_public_urls_module_all() -> None:
    assert "FluxLitPublicUrls" in public_urls_mod.__all__


def test_fluxlit_test_client_api_can_return_page_url_under_mount() -> None:
    base = FluxLit(title="T")
    app = FluxLit(title="T", settings=base.settings.model_copy(update={"root_path": "/my"}))

    @app.api.get("/deeplink-demo")
    def deeplink_demo(request: Request) -> dict[str, str]:
        return {"url": app.urls.page_url(request, "/", query={"token": "t"})}

    client = FluxLitTestClient(app)
    res = client.api_get("/deeplink-demo")
    assert res.status_code == 200
    assert res.json()["url"] == "http://testserver/my/?token=t"


def test_match_nav_page_strips_slashes_for_segment_match() -> None:
    pages = [("/reports", "Reports")]
    assert match_nav_page({"page": "reports/"}, pages) == ("/reports", "Reports")


def test_query_params_mapping_without_get_uses_getitem() -> None:
    class NoGet:
        def keys(self) -> list[str]:
            return ["k"]

        def __getitem__(self, key: str) -> str:
            if key == "k":
                return "v"
            raise KeyError(key)

    assert query_params(SimpleNamespace(query_params=NoGet())) == {"k": "v"}


def test_match_nav_page_accepts_page_record_rows() -> None:
    from fluxlit.pages.records import PageRecord

    def _fn(st, client):
        del st, client

    recs = [
        PageRecord("/reports", "Reports", _fn),
        PageRecord("/", "Home", _fn),
    ]
    assert match_nav_page({"page": "Home"}, recs) == ("/", "Home")
    assert match_nav_page({"page": "reports"}, recs) == ("/reports", "Reports")


def test_apptest_prefills_from_query_params(requires_streamlit_apptest: None) -> None:
    from streamlit.testing.v1 import AppTest

    script = textwrap.dedent(
        """
        import streamlit as st
        from fluxlit import query_params

        params = query_params(st)
        st.text_input("Token", value=params.get("token", ""), key="tok_field")
        """
    )
    at = AppTest.from_string(script, default_timeout=10)
    at.query_params["token"] = "opaque-from-email"
    at.run()
    assert at.text_input(key="tok_field").value == "opaque-from-email"
