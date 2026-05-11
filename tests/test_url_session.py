"""Unit tests for :mod:`fluxlit.url_session` (store + hydrate helpers)."""

from __future__ import annotations

import time

from fluxlit.config import JsonValue
from fluxlit.url_session import (
    InMemorySessionStore,
    ensure_url_session,
    hydrate_url_session,
    new_session_id,
    persist_url_session,
)


class _FakeSt:
    def __init__(self) -> None:
        self.session_state: dict[str, JsonValue] = {}
        self.query_params: dict[str, str | list[str] | None] = {}


class _NoGetQueryParamsSt:
    def __init__(self) -> None:
        self.session_state: dict[str, JsonValue] = {}
        self.query_params = object()


class _ReadonlyQueryParamsSt:
    def __init__(self) -> None:
        self.session_state: dict[str, JsonValue] = {}
        self.query_params = object()


class _ExplodingSetQueryParams:
    def get(self, key: str) -> str | None:
        return None

    def __setitem__(self, key: str, value: str) -> None:
        raise RuntimeError("readonly")


class _ExplodingSetQueryParamsSt:
    def __init__(self) -> None:
        self.session_state: dict[str, JsonValue] = {}
        self.query_params = _ExplodingSetQueryParams()


class _NoneQueryParamsSt:
    def __init__(self) -> None:
        self.session_state: dict[str, JsonValue] = {}
        self.query_params = None


class _SetItemOnlyQueryParams:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def __setitem__(self, key: str, value: str) -> None:
        self.values[key] = value


class _SetItemOnlyQueryParamsSt:
    def __init__(self) -> None:
        self.session_state: dict[str, JsonValue] = {}
        self.query_params = _SetItemOnlyQueryParams()


def test_new_session_id_length_and_uniqueness() -> None:
    a = new_session_id()
    b = new_session_id()
    assert len(a) >= 32
    assert a != b


def test_in_memory_store_ttl_expires() -> None:
    store = InMemorySessionStore(default_ttl_seconds=0.05, max_entries=100)
    store.set("sid", {"x": 1}, ttl_seconds=0.05)
    assert store.get("sid") == {"x": 1}
    time.sleep(0.08)
    assert store.get("sid") is None


def test_in_memory_store_trims_oldest_entry() -> None:
    store = InMemorySessionStore(default_ttl_seconds=None, max_entries=1)
    store.set("a", {"x": 1})
    store.set("b", {"x": 2})
    assert store.get("a") is None
    assert store.get("b") == {"x": 2}


def test_in_memory_store_get_removes_expired_entry(monkeypatch) -> None:
    store = InMemorySessionStore(default_ttl_seconds=None)
    moments = iter([100.0, 200.0])
    monkeypatch.setattr("fluxlit.url_session.time.monotonic", lambda: next(moments))
    store._data["sid"] = ({"x": 1}, 150.0)  # noqa: SLF001
    assert store.get("sid") is None
    assert "sid" not in store._data  # noqa: SLF001


def test_in_memory_store_delete() -> None:
    store = InMemorySessionStore(default_ttl_seconds=None)
    store.set("a", {"k": "v"})
    store.delete("a")
    assert store.get("a") is None


def test_hydrate_merge_setdefault() -> None:
    store = InMemorySessionStore(default_ttl_seconds=None)
    store.set("s1", {"a": 1, "b": 2})
    st = _FakeSt()
    st.query_params["fluxlit_sid"] = "s1"
    st.session_state["b"] = 99
    assert hydrate_url_session(st, store, param="fluxlit_sid") == "s1"
    assert st.session_state["a"] == 1
    assert st.session_state["b"] == 99


def test_hydrate_missing_param_returns_none() -> None:
    st = _FakeSt()
    assert hydrate_url_session(st, InMemorySessionStore()) is None


def test_hydrate_param_without_store_entry_returns_sid() -> None:
    st = _FakeSt()
    st.query_params["fluxlit_sid"] = "orphan"
    assert hydrate_url_session(st, InMemorySessionStore()) == "orphan"


def test_hydrate_query_params_without_get_returns_none() -> None:
    st = _NoGetQueryParamsSt()
    assert hydrate_url_session(st, InMemorySessionStore()) is None


def test_hydrate_list_query_param_uses_first_value() -> None:
    store = InMemorySessionStore(default_ttl_seconds=None)
    store.set("s-list", {"a": 1})
    st = _FakeSt()
    st.query_params["fluxlit_sid"] = ["s-list", "other"]
    assert hydrate_url_session(st, store) == "s-list"
    assert st.session_state["a"] == 1


def test_hydrate_empty_list_query_param_returns_none() -> None:
    st = _FakeSt()
    st.query_params["fluxlit_sid"] = []
    assert hydrate_url_session(st, InMemorySessionStore()) is None


def test_hydrate_replace_mode_overwrites_existing_state() -> None:
    store = InMemorySessionStore(default_ttl_seconds=None)
    store.set("s1", {"a": 1})
    st = _FakeSt()
    st.query_params["fluxlit_sid"] = "s1"
    st.session_state["a"] = 99
    assert hydrate_url_session(st, store, merge=False) == "s1"
    assert st.session_state["a"] == 1


def test_ensure_mints_and_sets_query_param() -> None:
    st = _FakeSt()
    store = InMemorySessionStore(default_ttl_seconds=None)
    sid = ensure_url_session(st, store, param="fluxlit_sid", initial={"n": 0})
    assert st.query_params.get("fluxlit_sid") == sid
    assert store.get(sid) == {"n": 0}


def test_ensure_mints_when_query_params_readonly() -> None:
    st = _ReadonlyQueryParamsSt()
    store = InMemorySessionStore(default_ttl_seconds=None)
    sid = ensure_url_session(st, store, initial={"n": 1})
    assert store.get(sid) == {"n": 1}


def test_ensure_mints_when_query_params_none() -> None:
    st = _NoneQueryParamsSt()
    store = InMemorySessionStore(default_ttl_seconds=None)
    sid = ensure_url_session(st, store, initial={"n": 1})
    assert store.get(sid) == {"n": 1}


def test_ensure_sets_query_param_with_setitem_only_object() -> None:
    st = _SetItemOnlyQueryParamsSt()
    store = InMemorySessionStore(default_ttl_seconds=None)
    sid = ensure_url_session(st, store)
    assert st.query_params.values["fluxlit_sid"] == sid


def test_ensure_mints_when_query_param_assignment_raises() -> None:
    st = _ExplodingSetQueryParamsSt()
    store = InMemorySessionStore(default_ttl_seconds=None)
    sid = ensure_url_session(st, store, initial={"n": 1})
    assert store.get(sid) == {"n": 1}


def test_ensure_existing_merges_initial() -> None:
    st = _FakeSt()
    store = InMemorySessionStore(default_ttl_seconds=None)
    sid = ensure_url_session(st, store, param="fluxlit_sid", initial={"a": 1})
    ensure_url_session(st, store, param="fluxlit_sid", initial={"b": 2})
    blob = store.get(sid)
    assert blob == {"a": 1, "b": 2}


def test_persist_roundtrip_filtered_state_style() -> None:
    class _SS:
        filtered_state = {"wizard_step": 3, "__internal": 9}

    st = _FakeSt()
    st.query_params["fluxlit_sid"] = "s9"
    st.session_state = _SS()  # type: ignore[assignment]
    store = InMemorySessionStore(default_ttl_seconds=None)
    assert persist_url_session(st, store, param="fluxlit_sid") == "s9"
    assert store.get("s9") == {"wizard_step": 3}


def test_persist_missing_query_param_returns_none() -> None:
    st = _FakeSt()
    assert persist_url_session(st, InMemorySessionStore()) is None


def test_persist_iterable_session_state_without_filtered_state() -> None:
    st = _FakeSt()
    st.query_params["fluxlit_sid"] = "s"
    st.session_state["ok"] = 1
    store = InMemorySessionStore(default_ttl_seconds=None)
    assert persist_url_session(st, store) == "s"
    assert store.get("s") == {"ok": 1}


def test_persist_falls_back_to_empty_snapshot_on_state_error() -> None:
    class _BadState:
        def __iter__(self):
            raise RuntimeError("bad state")

    st = _FakeSt()
    st.query_params["fluxlit_sid"] = "s"
    st.session_state = _BadState()  # type: ignore[assignment]
    store = InMemorySessionStore(default_ttl_seconds=None)
    assert persist_url_session(st, store) == "s"
    assert store.get("s") == {}


def test_persist_skips_dunder_keys() -> None:
    class _SS:
        filtered_state = {"ok": 1, "__dunder": 2}

    st = _FakeSt()
    st.query_params["fluxlit_sid"] = "s"
    st.session_state = _SS()  # type: ignore[assignment]
    store = InMemorySessionStore(default_ttl_seconds=None)
    persist_url_session(st, store)
    assert store.get("s") == {"ok": 1}
