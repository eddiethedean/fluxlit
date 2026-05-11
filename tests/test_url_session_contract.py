"""Contract tests: external :class:`~fluxlit.url_session.SessionStore` implementations."""

from __future__ import annotations

import threading
import time

from fluxlit.config import JsonValue
from fluxlit.url_session import (
    SessionStore,
    hydrate_url_session,
    new_session_id,
    persist_url_session,
)


class DictSessionStore:
    """Thread-safe dict store (example ``SessionStore`` for Redis-like backends)."""

    def __init__(self, *, default_ttl_seconds: float | None = None) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, tuple[dict[str, JsonValue], float | None]] = {}
        self._default_ttl = default_ttl_seconds

    def get(self, session_id: str) -> dict[str, JsonValue] | None:
        with self._lock:
            ent = self._data.get(session_id)
            if not ent:
                return None
            payload, deadline = ent
            if deadline is not None and deadline <= time.monotonic():
                self._data.pop(session_id, None)
                return None
            return dict(payload)

    def set(
        self,
        session_id: str,
        data: dict[str, JsonValue],
        *,
        ttl_seconds: float | None = None,
    ) -> None:
        ttl = self._default_ttl if ttl_seconds is None else ttl_seconds
        deadline: float | None = None
        if ttl is not None and ttl > 0:
            deadline = time.monotonic() + float(ttl)
        with self._lock:
            self._data[session_id] = (dict(data), deadline)

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._data.pop(session_id, None)


def test_dict_session_store_satisfies_session_store_protocol() -> None:
    s: SessionStore = DictSessionStore(default_ttl_seconds=None)
    sid = new_session_id()
    s.set(sid, {"a": 1})
    assert s.get(sid) == {"a": 1}
    s.delete(sid)
    assert s.get(sid) is None


def test_hydrate_and_persist_with_dict_store() -> None:
    class _St:
        def __init__(self) -> None:
            self.session_state: dict[str, JsonValue] = {}
            self.query_params: dict[str, str | list[str] | None] = {}

    store = DictSessionStore(default_ttl_seconds=None)
    st = _St()
    sid = new_session_id()
    store.set(sid, {"counter": 42})
    st.query_params["fluxlit_sid"] = sid
    assert hydrate_url_session(st, store) == sid
    assert st.session_state["counter"] == 42
    st.session_state["counter"] = 99
    persist_url_session(st, store)
    assert store.get(sid) == {"counter": 99}
