"""Extra coverage for FluxLit 0.9 page stack edge cases."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Annotated, Any, get_type_hints

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from fluxlit import FluxLit
from fluxlit.application.page_registry import register_streamlit_page
from fluxlit.application.public_urls import FluxLitPublicUrls
from fluxlit.client import ApiClient
from fluxlit.config import FluxlitSettings
from fluxlit.pages.apply_meta import page_meta_to_set_page_config_kwargs, try_set_page_config_first
from fluxlit.pages.di import (
    Cookie,
    Depends,
    Header,
    _call_kw_for_fn,
    reset_page_cookie_context,
    reset_page_header_context,
    resolve_and_call_page,
    resolve_page_kwargs,
    set_page_cookie_context,
    set_page_header_context,
)
from fluxlit.pages.flags import FluxlitFeatureFlags
from fluxlit.pages.manifest import build_page_manifest
from fluxlit.pages.meta import PageMeta
from fluxlit.pages.query import (
    Query,
    _query_dict_from_st,
    parse_query_params,
    parse_query_params_adapter,
)
from fluxlit.pages.records import PageRecord
from fluxlit.pages.session_state import SessionModel
from fluxlit.pages.signature import validate_strict_page_signature
from fluxlit.streamlit.page_runner import run_page_record
from fluxlit.url_session import InMemorySessionStore, SessionStore, hydrate_url_session_typed
from tests.test_fluxlit_pages_09 import _manifest_dep, _resolve_dep


def _ok_with_fluxlit_arg(st: Any, client: Any, app: FluxLit) -> None:
    del st, client, app


def _sig_puburls(st: Any, client: Any, x: FluxLitPublicUrls) -> None:
    del st, client, x


def _sig_sessionstore(st: Any, client: Any, x: SessionStore) -> None:
    del st, client, x


def _sig_apiclient(st: Any, client: Any, x: ApiClient) -> None:
    del st, client, x


def _resolve_kw_apiclient(st: Any, client: Any, x: ApiClient) -> None:
    del st, client, x


def test_docstring_first_line_nonempty() -> None:
    app = FluxLit()

    def g(st, client) -> None:
        """My summary
        more"""
        del st, client

    register_streamlit_page(app, "/")(g)
    assert app.page_records[0].description == "My summary"


def test_resolve_page_kwargs_skips_union_annotation() -> None:
    app = FluxLit()

    def fn(st, client, x: str | None) -> None:
        del st, client, x

    kw = resolve_page_kwargs(fn, st=0, client=app.get_client(), app=app, overrides=None)
    assert "x" not in kw


def test_page_registry_description_when_no_docstring() -> None:
    app = FluxLit()

    def f(st, client) -> None:
        del st, client

    f.__doc__ = None
    register_streamlit_page(app, "/")(f)
    assert app.page_records[0].description == ""


def test_apply_meta_icon_sidebar_state_and_empty_meta() -> None:
    kw = page_meta_to_set_page_config_kwargs(
        PageMeta(page_icon="x", initial_sidebar_state="collapsed")
    )
    assert "page_icon" in kw and "initial_sidebar_state" in kw
    st = SimpleNamespace(set_page_config=lambda **k: None)
    try_set_page_config_first(st, PageMeta())
    try_set_page_config_first(st, PageMeta(page_title=None))


def test_coerce_non_dict_returns_none() -> None:
    from fluxlit.pages.apply_meta import coerce_page_return

    st = SimpleNamespace(error=lambda m: None)
    assert coerce_page_return(st, 123) is None


def test_resolve_and_call_page_requires_record() -> None:
    with pytest.raises(TypeError, match="PageRecord"):
        resolve_and_call_page(object(), object(), FluxLit().get_client(), FluxLit(), None)


def test_call_kw_for_fn_var_keyword() -> None:
    def fn(st: Any, client: Any, **kw: Any) -> dict[str, Any]:
        return kw

    merged = _call_kw_for_fn(fn, {"st": 0, "client": 1, "extra": 2})
    assert merged == {"st": 0, "client": 1, "extra": 2}


def test_resolve_page_kwargs_depends_default() -> None:
    app = FluxLit()

    def fn(st, client, lab: int = Depends(_resolve_dep)) -> None:  # noqa: B008
        del st, client, lab

    kw = resolve_page_kwargs(fn, st=0, client=app.get_client(), app=app, overrides=None)
    assert kw["lab"] == 42


def test_resolve_page_kwargs_header_from_context() -> None:
    app = FluxLit()

    def fn(st, client, h: Annotated[str | None, Header("X-Test")]) -> None:
        del st, client, h

    tok = set_page_header_context({"x-test": "ctx"})
    try:
        kw = resolve_page_kwargs(fn, st=0, client=app.get_client(), app=app, overrides=None)
        assert kw["h"] == "ctx"
    finally:
        reset_page_header_context(tok)


def test_resolve_page_kwargs_header_from_streamlit_context_fallback() -> None:
    app = FluxLit()

    def fn(st, client, h: Annotated[str | None, Header("x-trace")]) -> None:
        del st, client, h

    headers_obj = SimpleNamespace(
        get=lambda name, default=None: "tp" if str(name).lower() == "x-trace" else default,
        items=lambda: [("x-trace", "tp")],
    )
    st = SimpleNamespace(context=SimpleNamespace(headers=headers_obj))
    kw = resolve_page_kwargs(fn, st=st, client=app.get_client(), app=app, overrides=None)
    assert kw["h"] == "tp"


def test_resolve_page_kwargs_header_streamlit_items_when_get_misses() -> None:
    app = FluxLit()

    def fn(st, client, h: Annotated[str | None, Header("x-trace")]) -> None:
        del st, client, h

    class _Hdr:
        def get(self, name: str, default: object = None) -> object:
            return default

        def items(self) -> list[tuple[str, str]]:
            return [("X-Trace", "from-items")]

    st = SimpleNamespace(context=SimpleNamespace(headers=_Hdr()))
    kw = resolve_page_kwargs(fn, st=st, client=app.get_client(), app=app, overrides=None)
    assert kw["h"] == "from-items"


def test_resolve_page_kwargs_header_streamlit_context_exception_returns_none() -> None:
    app = FluxLit()

    def fn(st, client, h: Annotated[str | None, Header("x-trace")]) -> None:
        del st, client, h

    class _Ctx:
        @property
        def headers(self) -> object:
            raise RuntimeError("no headers")

    st = SimpleNamespace(context=_Ctx())
    kw = resolve_page_kwargs(fn, st=st, client=app.get_client(), app=app, overrides=None)
    assert kw["h"] is None


def test_resolve_page_kwargs_header_context_var_beats_streamlit_context() -> None:
    """``set_page_header_context`` wins over ``st.context.headers`` (explicit trusted path)."""
    app = FluxLit()

    def fn(st, client, h: Annotated[str | None, Header("x-trace")]) -> None:
        del st, client, h

    headers_obj = SimpleNamespace(
        get=lambda name, default=None: "from-st" if str(name).lower() == "x-trace" else default,
        items=lambda: [],
    )
    st = SimpleNamespace(context=SimpleNamespace(headers=headers_obj))
    tok = set_page_header_context({"x-trace": "from-ctxvar"})
    try:
        kw = resolve_page_kwargs(fn, st=st, client=app.get_client(), app=app, overrides=None)
        assert kw["h"] == "from-ctxvar"
    finally:
        reset_page_header_context(tok)


def test_resolve_page_kwargs_header_context_without_headers_attr() -> None:
    app = FluxLit()

    def fn(st, client, h: Annotated[str | None, Header("x-trace")]) -> None:
        del st, client, h

    st = SimpleNamespace(context=SimpleNamespace(headers=None))
    kw = resolve_page_kwargs(fn, st=st, client=app.get_client(), app=app, overrides=None)
    assert kw["h"] is None


def test_resolve_page_kwargs_header_object_without_get() -> None:
    app = FluxLit()

    def fn(st, client, h: Annotated[str | None, Header("x-trace")]) -> None:
        del st, client, h

    st = SimpleNamespace(context=SimpleNamespace(headers=object()))
    kw = resolve_page_kwargs(fn, st=st, client=app.get_client(), app=app, overrides=None)
    assert kw["h"] is None


def test_resolve_page_kwargs_header_items_empty_no_match() -> None:
    app = FluxLit()

    def fn(st, client, h: Annotated[str | None, Header("x-trace")]) -> None:
        del st, client, h

    class _Hdr:
        def get(self, name: str, default: object = None) -> object:
            return default

        def items(self) -> list[tuple[str, str]]:
            return []

    st = SimpleNamespace(context=SimpleNamespace(headers=_Hdr()))
    kw = resolve_page_kwargs(fn, st=st, client=app.get_client(), app=app, overrides=None)
    assert kw["h"] is None


def test_resolve_page_kwargs_fluxlit_feature_flags() -> None:
    app = FluxLit()

    def fn(st, client, f: FluxlitFeatureFlags) -> None:
        del st, client, f

    kw = resolve_page_kwargs(fn, st=0, client=app.get_client(), app=app, overrides=None)
    assert isinstance(kw["f"], FluxlitFeatureFlags)


def test_run_page_record_invokes_handler() -> None:
    app = FluxLit()
    seen: list[str] = []

    def h(st, client):
        seen.append("ok")

    rec = PageRecord(path="/", title="T", fn=h)
    run_page_record(rec, object(), app.get_client(), app, None)
    assert seen == ["ok"]


def test_generator_empty_first(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLUXLIT_EXPERIMENTAL_YIELD_PAGES", "1")
    app = FluxLit()

    def gen(st, client):
        yield from ()

    rec = PageRecord(path="/", title="G", fn=gen)
    assert resolve_and_call_page(rec, object(), app.get_client(), app, None) is None


def test_generator_two_yields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLUXLIT_EXPERIMENTAL_YIELD_PAGES", "1")
    app = FluxLit()

    def gen(st, client):
        yield PageMeta(breadcrumb="1")
        yield PageMeta(breadcrumb="2")

    rec = PageRecord(path="/", title="G", fn=gen)
    caps: list[str] = []

    class SB:
        def caption(self, t: str) -> None:
            caps.append(t)

    st = SimpleNamespace(sidebar=SB())
    resolve_and_call_page(rec, st, app.get_client(), app, None)
    assert caps == ["1", "2"]


def test_parse_query_params_re_raises_when_empty_invalid() -> None:
    class Q(BaseModel):
        x: int

    st = SimpleNamespace(query_params={"x": "nope"}, error=lambda m: None)
    with pytest.raises(ValidationError):
        parse_query_params(st, Q, strict=False)


def test_parse_query_params_adapter_soft_raises() -> None:
    class M(BaseModel):
        x: int

    st = SimpleNamespace(query_params={"x": "bad"}, error=lambda m: None)
    with pytest.raises(ValidationError):
        parse_query_params_adapter(st, TypeAdapter(M), strict=False)


def test_query_dict_qp_none_and_bad_keys() -> None:
    assert _query_dict_from_st(SimpleNamespace(query_params=None)) == {}

    class BadQP:
        def keys(self):
            raise RuntimeError("no")

    assert _query_dict_from_st(SimpleNamespace(query_params=BadQP())) == {}

    class QP:
        def keys(self):
            return ["a"]

        def get(self, k):
            raise RuntimeError("no")

    assert _query_dict_from_st(SimpleNamespace(query_params=QP())) == {}


def test_session_read_into_validation_error() -> None:
    class M(BaseModel):
        a: int

    st = SimpleNamespace(session_state={"a": "bad"})
    sm = SessionModel(st)
    with pytest.raises(ValidationError):
        sm.read_into(M)


def test_hydrate_url_session_typed_missing_blob(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLUXLIT_TESTS", raising=False)
    monkeypatch.delenv("FLUXLIT_DISABLE_URL_SESSION", raising=False)
    store = InMemorySessionStore()

    class Blob(BaseModel):
        k: str = "v"

    sid = "ghost-id"
    st = SimpleNamespace(query_params={"fluxlit_sid": sid}, session_state={})
    out = hydrate_url_session_typed(st, store, Blob)
    assert out == (sid, None)


def test_hydrate_typed_when_tests_disable_url_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLUXLIT_TESTS", "1")
    store = InMemorySessionStore()

    class Blob(BaseModel):
        k: str = "v"

    st = SimpleNamespace(query_params={"fluxlit_sid": "x"}, session_state={})
    assert hydrate_url_session_typed(st, store, Blob) == (None, None)


def test_manifest_duplicate_dep_qualname() -> None:
    app = FluxLit()

    @app.page("/dup")
    def dup(
        st,
        client,
        _a=Depends(_manifest_dep),  # noqa: B008
        _b=Depends(_manifest_dep),  # noqa: B008
    ):
        del st, client, _a, _b

    man = build_page_manifest(app)
    deps = man["pages"][0]["dependencies"]
    assert len(deps) >= 1


def test_manifest_includes_int_annotation_string() -> None:
    app = FluxLit()

    @app.page("/i")
    def pi(st, client, x: int) -> None:
        del st, client, x

    man = build_page_manifest(app)
    assert "int" in man["pages"][0]["parameters"][-1]["annotation"]


def test_signature_varargs_and_injectables() -> None:
    def bad1(st, client, *a: int) -> None:
        del st, client, a

    def bad2(st, client, **kw: int) -> None:
        del st, client, kw

    for fn in (bad1, bad2):
        with pytest.raises(TypeError, match="must not use"):
            validate_strict_page_signature(fn)

    def ok_dep_default(st, client, x: int = Depends(_resolve_dep)) -> None:  # noqa: B008
        del st, client, x

    validate_strict_page_signature(ok_dep_default)


def test_signature_depends_default_only() -> None:
    def ok(st, client, x=Depends(_resolve_dep)) -> None:  # noqa: B008
        del st, client, x

    validate_strict_page_signature(ok)


def test_signature_missing_annotation_rejected() -> None:
    def bad(st, client, x) -> None:
        del st, client, x

    with pytest.raises(TypeError, match="Unknown page parameter"):
        validate_strict_page_signature(bad)


def test_generator_single_yield_returns_first(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FLUXLIT_EXPERIMENTAL_YIELD_PAGES", "1")
    app = FluxLit()

    def gen(st, client):
        yield PageMeta(breadcrumb="only")

    rec = PageRecord(path="/", title="G", fn=gen)
    caps: list[str] = []

    class SB:
        def caption(self, t: str) -> None:
            caps.append(t)

    st = SimpleNamespace(sidebar=SB())
    out = resolve_and_call_page(rec, st, app.get_client(), app, None)
    assert caps == ["only"]
    assert isinstance(out, PageMeta)


def test_signature_fluxlit_instance_param() -> None:
    validate_strict_page_signature(_ok_with_fluxlit_arg)


def test_register_strict_fluxlit_settings_param() -> None:
    app = FluxLit(settings=FluxlitSettings(strict_page_signatures=True))

    def ok(st, client, s: FluxlitSettings) -> None:
        del st, client, s

    register_streamlit_page(app, "/")(ok)


def test_query_class_description() -> None:
    assert Query(description="d").description == "d"


def test_register_strict_allows_header_param() -> None:
    app = FluxLit(settings=FluxlitSettings(strict_page_signatures=True))

    def h(st, client, x: Annotated[str | None, Header("X-Test")]) -> None:
        del st, client, x

    register_streamlit_page(app, "/")(h)


def test_signature_public_urls_and_session_store_and_api_client() -> None:
    for fn in (_sig_puburls, _sig_sessionstore, _sig_apiclient):
        validate_strict_page_signature(fn)


def test_resolve_page_kwargs_exact_api_client_annotation() -> None:
    app = FluxLit()
    c = app.get_client()
    kw = resolve_page_kwargs(_resolve_kw_apiclient, st=0, client=c, app=app, overrides=None)
    assert kw["x"] is c


def test_resolve_page_kwargs_injects_settings_urls_and_app() -> None:
    app = FluxLit()
    c = app.get_client()

    def fn(st, client, s: FluxlitSettings, u: FluxLitPublicUrls, a: FluxLit) -> None:
        del st, client, s, u, a

    kw = resolve_page_kwargs(fn, st=0, client=c, app=app, overrides=None)
    assert kw["s"] is app.settings and kw["u"] is app.urls and kw["a"] is app


def test_signature_rejects_generic_alias_type_param() -> None:
    def bad(st, client, x: list[int]) -> None:
        del st, client, x

    with pytest.raises(TypeError, match="Unknown page parameter"):
        validate_strict_page_signature(bad)


def test_resolve_page_kwargs_cookie_param() -> None:
    app = FluxLit()
    c = app.get_client()

    def fn(st, client, ck: Annotated[str | None, Cookie("sid")]) -> None:
        del st, client, ck

    kw = resolve_page_kwargs(fn, st=0, client=c, app=app, overrides=None)
    assert kw["ck"] is None


def test_resolve_page_kwargs_cookie_from_context_var() -> None:
    app = FluxLit()

    def fn(st, client, ck: Annotated[str | None, Cookie("sid")]) -> None:
        del st, client, ck

    tok = set_page_cookie_context({"sid": "from-ctx"})
    try:
        kw = resolve_page_kwargs(fn, st=0, client=app.get_client(), app=app, overrides=None)
        assert kw["ck"] == "from-ctx"
    finally:
        reset_page_cookie_context(tok)


def test_resolve_page_kwargs_cookie_from_streamlit_context() -> None:
    app = FluxLit()

    def fn(st, client, ck: Annotated[str | None, Cookie("sid")]) -> None:
        del st, client, ck

    cookies_obj = SimpleNamespace(
        get=lambda name, default=None: "abc" if str(name).lower() == "sid" else default,
        items=lambda: [("sid", "abc")],
    )
    st = SimpleNamespace(context=SimpleNamespace(cookies=cookies_obj))
    kw = resolve_page_kwargs(fn, st=st, client=app.get_client(), app=app, overrides=None)
    assert kw["ck"] == "abc"


def test_resolve_page_kwargs_cookie_context_var_beats_streamlit_context() -> None:
    app = FluxLit()

    def fn(st, client, ck: Annotated[str | None, Cookie("sid")]) -> None:
        del st, client, ck

    cookies_obj = SimpleNamespace(
        get=lambda name, default=None: "from-st" if str(name).lower() == "sid" else default,
        items=lambda: [],
    )
    st = SimpleNamespace(context=SimpleNamespace(cookies=cookies_obj))
    tok = set_page_cookie_context({"sid": "from-ctxvar"})
    try:
        kw = resolve_page_kwargs(fn, st=st, client=app.get_client(), app=app, overrides=None)
        assert kw["ck"] == "from-ctxvar"
    finally:
        reset_page_cookie_context(tok)


def test_resolve_page_kwargs_cookie_streamlit_items_when_get_misses() -> None:
    app = FluxLit()

    def fn(st, client, ck: Annotated[str | None, Cookie("sid")]) -> None:
        del st, client, ck

    class _Ck:
        def get(self, name: str, default: object = None) -> object:
            return default

        def items(self) -> list[tuple[str, str]]:
            return [("SID", "from-items")]

    st = SimpleNamespace(context=SimpleNamespace(cookies=_Ck()))
    kw = resolve_page_kwargs(fn, st=st, client=app.get_client(), app=app, overrides=None)
    assert kw["ck"] == "from-items"


def test_resolve_page_kwargs_cookie_streamlit_context_exception_returns_none() -> None:
    app = FluxLit()

    def fn(st, client, ck: Annotated[str | None, Cookie("sid")]) -> None:
        del st, client, ck

    class _Ctx:
        @property
        def cookies(self) -> object:
            raise RuntimeError("no cookies")

    st = SimpleNamespace(context=_Ctx())
    kw = resolve_page_kwargs(fn, st=st, client=app.get_client(), app=app, overrides=None)
    assert kw["ck"] is None


def test_resolve_page_kwargs_cookie_no_match_returns_none() -> None:
    app = FluxLit()

    def fn(st, client, ck: Annotated[str | None, Cookie("missing")]) -> None:
        del st, client, ck

    class _Ck:
        def get(self, name: str, default: object = None) -> object:
            return default

    st = SimpleNamespace(context=SimpleNamespace(cookies=_Ck()))
    kw = resolve_page_kwargs(fn, st=st, client=app.get_client(), app=app, overrides=None)
    assert kw["ck"] is None


def test_di_and_signature_strip_annotated_helpers() -> None:
    from fluxlit.pages.di import _strip_annotated as di_strip
    from fluxlit.pages.signature import _strip_annotated as sig_strip

    assert di_strip(int) is int
    assert di_strip(Annotated[str, "meta"]) is str
    assert sig_strip(int) is int
    assert sig_strip(Annotated[str, "meta"]) is str


def test_signature_has_header_cookie_false_for_plain_annotation() -> None:
    import inspect

    from fluxlit.pages.signature import _has_header_cookie

    def fn(st, client, x: int) -> None:
        del st, client, x

    sig = inspect.signature(fn)
    p = sig.parameters["x"]
    assert not _has_header_cookie(p, {"x": int}, "x")


def test_signature_depends_with_callable_detects_annotated() -> None:
    import inspect

    from fluxlit.pages.signature import _depends_with_callable

    def g(st, client, y: Annotated[int, Depends(_resolve_dep)]) -> None:
        del st, client, y

    hints = get_type_hints(g, include_extras=True)
    p = inspect.signature(g).parameters["y"]
    assert _depends_with_callable(p, hints, "y")


def test_signature_depends_with_callable_default_param() -> None:
    import inspect

    from fluxlit.pages.signature import _depends_with_callable

    def h(st, client, x=Depends(_resolve_dep)) -> None:  # noqa: B008
        del st, client, x

    hints = get_type_hints(h, include_extras=True)
    p = inspect.signature(h).parameters["x"]
    assert _depends_with_callable(p, hints, "x")


def test_is_injectable_type_feature_flags_and_fluxlit_subclass() -> None:
    from fluxlit.pages.signature import _is_injectable_type

    assert _is_injectable_type(FluxlitFeatureFlags)

    class SubApp(FluxLit):
        pass

    assert _is_injectable_type(SubApp)


def test_parse_query_params_adapter_strict() -> None:
    class M(BaseModel):
        x: int

    st = SimpleNamespace(query_params={"x": "bad"})
    with pytest.raises(ValidationError):
        parse_query_params_adapter(st, TypeAdapter(M), strict=True)
