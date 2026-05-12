"""Tests for FluxLit 0.9 page modules (DI, manifest, query, navigation, flags, signature)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Annotated, Any

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from fluxlit import FluxLit, NavigationModel
from fluxlit.application.page_registry import register_streamlit_page
from fluxlit.config import FluxlitSettings
from fluxlit.pages.apply_meta import (
    coerce_page_return,
    page_meta_to_set_page_config_kwargs,
    try_set_page_config_first,
)
from fluxlit.pages.di import (
    Cookie,
    Depends,
    Header,
    env_page_overrides,
    resolve_and_call_page,
    resolve_page_kwargs,
)
from fluxlit.pages.flags import FluxlitFeatureFlags
from fluxlit.pages.manifest import build_page_manifest
from fluxlit.pages.meta import PageMeta
from fluxlit.pages.query import (
    parse_query_params,
    parse_query_params_adapter,
    query_dict_for_manifest,
)
from fluxlit.pages.records import PageRecord
from fluxlit.pages.session_state import SessionModel
from fluxlit.pages.signature import validate_strict_page_signature
from fluxlit.url_session import InMemorySessionStore, SessionStore, hydrate_url_session_typed


def _manifest_dep() -> None:
    return None


def _resolve_dep() -> int:
    return 42


def test_page_meta_to_set_page_config_kwargs_partial() -> None:
    m = PageMeta(page_title="T", layout="wide")
    kw = page_meta_to_set_page_config_kwargs(m)
    assert kw["page_title"] == "T" and kw["layout"] == "wide"


def test_try_set_page_config_first_swallows_second_call(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def setcfg(*_args: Any, **kw: Any) -> None:
        calls.append(kw)
        if len(calls) > 1:
            raise RuntimeError("set_page_config only once")

    st = type("S", (), {"set_page_config": setcfg})()
    try_set_page_config_first(st, PageMeta(page_title="A"))
    try_set_page_config_first(st, PageMeta(page_title="B"))
    assert len(calls) == 2


def test_coerce_page_return_invalid_dict_shows_error() -> None:
    errors: list[str] = []

    st = SimpleNamespace(error=lambda m: errors.append(m))
    assert coerce_page_return(st, {"layout": "invalid"}) is None
    assert errors and "Invalid" in errors[0]


def test_fluxlit_feature_flags_from_environ(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLUXLIT_EXPERIMENTAL_YIELD_PAGES", raising=False)
    assert not FluxlitFeatureFlags.from_environ().experimental_yield_pages
    monkeypatch.setenv("FLUXLIT_EXPERIMENTAL_YIELD_PAGES", "1")
    assert FluxlitFeatureFlags.from_environ().experimental_yield_pages


def test_env_page_overrides_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLUXLIT_TEST_PAGE_OVERRIDES", json.dumps({"x": 1}))
    assert env_page_overrides() == {"x": 1}
    monkeypatch.setenv("FLUXLIT_TEST_PAGE_OVERRIDES", "not-json")
    assert env_page_overrides() == {}


def test_resolve_page_kwargs_depends_header_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FluxLit()

    def fn(
        st,
        client,
        x: Annotated[int, Depends(_resolve_dep)],
        h: Annotated[str | None, Header("X-Req")],
        c: Annotated[str | None, Cookie("sid")],
    ) -> None:
        del st, client, x, h, c

    monkeypatch.setenv("FLUXLIT_TEST_PAGE_OVERRIDES", json.dumps({"h": "hv", "c": "cv"}))
    kw = resolve_page_kwargs(fn, st=object(), client=app.get_client(), app=app, overrides=None)
    assert kw["x"] == 42 and kw["h"] == "hv" and kw["c"] == "cv"


def test_resolve_page_kwargs_session_store() -> None:
    store = InMemorySessionStore()
    app = FluxLit(session_store=store)

    def fn2(st, client, store_: SessionStore) -> None:
        del st, client, store_

    kw = resolve_page_kwargs(fn2, st=0, client=app.get_client(), app=app, overrides=None)
    assert kw["store_"] is store


def test_resolve_and_call_page_generator_experimental(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLUXLIT_EXPERIMENTAL_YIELD_PAGES", "1")
    app = FluxLit()

    def gen(st, client):
        yield PageMeta(breadcrumb="a")
        yield None

    rec = PageRecord(path="/", title="G", fn=gen)
    cap: list[str] = []

    class SB:
        def caption(self, t: str) -> None:
            cap.append(t)

    st = type("S", (), {"sidebar": SB()})()
    resolve_and_call_page(rec, st, app.get_client(), app, None)
    assert "a" in cap


def test_build_page_manifest_contains_dep() -> None:
    app = FluxLit()

    @app.page("/z")
    def zpage(st, client, x: Annotated[None, Depends(_manifest_dep)]):
        del st, client, x

    man = build_page_manifest(app)
    assert man["manifest_stability"] == "experimental"
    assert man["pages"][0]["dependencies"]


def test_strict_page_signature_rejects_unknown() -> None:
    app = FluxLit(settings=FluxlitSettings(strict_page_signatures=True))

    def bad(st, client, mystery: int) -> None:
        del st, client, mystery

    with pytest.raises(TypeError, match="Unknown page parameter"):
        register_streamlit_page(app, "/", title="x")(bad)


def test_parse_query_params_soft_and_strict() -> None:
    class M(BaseModel):
        n: int = 1

    class Q(BaseModel):
        n: int

    st = SimpleNamespace(
        query_params={"n": "x"},
        error=lambda *a, **k: None,
    )
    with pytest.raises(ValidationError):
        parse_query_params(st, Q, strict=True)
    m = parse_query_params(st, M)
    assert m.n == 1


def test_parse_query_params_adapter() -> None:
    from typing import TypedDict

    from pydantic import TypeAdapter

    class TD(TypedDict, total=False):
        a: int

    st = SimpleNamespace(query_params={"a": "3"})
    ta = TypeAdapter(TD)
    v = parse_query_params_adapter(st, ta)
    assert v["a"] == 3


def test_strict_depends_without_callable() -> None:
    def bad(st, client, x: Annotated[int, Depends()]):
        del st, client, x

    with pytest.raises(TypeError, match="without a callable"):
        validate_strict_page_signature(bad)


def test_query_dict_for_manifest() -> None:
    st = type("S", (), {"query_params": {"a": ["1", "2"]}})()
    assert query_dict_for_manifest(st)["a"] == ["1", "2"]


def test_session_model_roundtrip() -> None:
    class S(BaseModel):
        a: int = 0

    ss: dict[str, Any] = {"a": 3}
    st = type("ST", (), {"session_state": ss})()
    sm = SessionModel(st)
    assert sm.read_into(S).a == 3
    sm.write_from(S(a=5))
    assert ss["a"] == 5


def test_session_model_forbid_extra() -> None:
    class M(BaseModel):
        model_config = ConfigDict(extra="allow")
        a: int = 0

    ss: dict[str, Any] = {}
    st = type("ST", (), {"session_state": ss})()
    sm = SessionModel(st, extra="forbid")
    m = M.model_validate({"a": 1, "oops": 2})
    with pytest.raises(ValueError, match="Unexpected session keys"):
        sm.write_from(m)


def test_hydrate_url_session_typed_strict() -> None:
    class Blob(BaseModel):
        k: int

    store = InMemorySessionStore()
    store.set("sid1", {"k": "not-int"})
    qp = {"fluxlit_sid": "sid1"}

    class ST:
        query_params = qp
        session_state: dict[str, Any] = {}

    st = ST()
    with pytest.raises(ValidationError):
        hydrate_url_session_typed(st, store, Blob, strict=True)
    sid, m = hydrate_url_session_typed(st, store, Blob, strict=False)
    assert sid == "sid1" and m is None


def test_navigation_model_stored() -> None:
    app = FluxLit()

    @app.page("/b")
    def b(st, client):
        del st, client

    @app.page("/a")
    def a(st, client):
        del st, client

    app.navigation(NavigationModel(order=("/a", "/b")))
    assert app._navigation_model is not None
    assert app._navigation_model.order == ("/a", "/b")


def test_match_nav_page_accepts_record_like() -> None:
    from fluxlit.deep_links import match_nav_page

    class R:
        path = "/"
        title = "Home"

    hit = match_nav_page({"page": "Home"}, [R()])
    assert hit == ("/", "Home")


def test_match_nav_page_accepts_page_record() -> None:
    from fluxlit.deep_links import match_nav_page
    from fluxlit.pages.records import PageRecord

    def _fn(st, client):
        del st, client

    rec = PageRecord(path="/reports", title="Reports", fn=_fn)
    assert match_nav_page({"page": "Reports"}, [rec]) == ("/reports", "Reports")


def test_pages_manifest_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    p = tmp_path / "mapp.py"
    p.write_text(
        "from fluxlit import FluxLit\napp=FluxLit()\n@app.page('/')\ndef h(st,client): pass\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("FLUXLIT_TESTS", "1")
    from fluxlit.cli import app as cli_app

    runner = CliRunner()
    r = runner.invoke(cli_app, ["pages", "manifest", "--target", "mapp:app"])
    assert r.exit_code == 0
    data = json.loads(r.stdout)
    assert data["manifest_version"] == 1 and data["pages"]
