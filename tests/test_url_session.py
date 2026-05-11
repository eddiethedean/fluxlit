"""Unit tests for :mod:`fluxlit.url_session` (store + hydrate helpers)."""

from __future__ import annotations

import time

from fluxlit.json_types import JsonValue
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


def test_ensure_mints_and_sets_query_param() -> None:
    st = _FakeSt()
    store = InMemorySessionStore(default_ttl_seconds=None)
    sid = ensure_url_session(st, store, param="fluxlit_sid", initial={"n": 0})
    assert st.query_params.get("fluxlit_sid") == sid
    assert store.get(sid) == {"n": 0}


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


def test_persist_skips_dunder_keys() -> None:
    class _SS:
        filtered_state = {"ok": 1, "__dunder": 2}

    st = _FakeSt()
    st.query_params["fluxlit_sid"] = "s"
    st.session_state = _SS()  # type: ignore[assignment]
    store = InMemorySessionStore(default_ttl_seconds=None)
    persist_url_session(st, store)
    assert store.get("s") == {"ok": 1}
