"""URL-bound server session continuity (Phase 2 follow-on — no HTTP cookies).

Use an opaque query parameter (default ``fluxlit_sid``) plus a :class:`SessionStore`
implementation to survive **full browser reloads** without relying on the browser
cookie jar. The gateway already forwards path + query to Streamlit.

**Production:** replace :class:`InMemorySessionStore` with a shared store (Redis, etc.)
that implements the same protocol. In-memory is **single-process only** (typical
``fluxlit dev`` / one replica).

See the **URL session continuity** user guide for security (HTTPS, link leakage, TTL)
and multipage patterns.
"""

from __future__ import annotations

import os
import secrets
import time
from collections.abc import Mapping, MutableMapping
from typing import Protocol, cast, runtime_checkable

from fluxlit.config import JsonValue
from fluxlit.streamlit.facade import StreamlitSessionFacade


@runtime_checkable
class SessionStore(Protocol):
    """Server-side persistence for URL-bound session blobs (JSON-serializable dicts)."""

    def get(self, session_id: str) -> dict[str, JsonValue] | None:
        """Return the stored dict or ``None`` if missing/expired."""

    def set(
        self,
        session_id: str,
        data: dict[str, JsonValue],
        *,
        ttl_seconds: float | None = None,
    ) -> None:
        """Persist *data* for *session_id*; optional time-to-live in seconds."""

    def delete(self, session_id: str) -> None:
        """Remove *session_id* from the store if present."""


class InMemorySessionStore:
    """Process-local :class:`SessionStore` (dev / single replica).

    Not safe across multiple Uvicorn workers or horizontal replicas without a shared
    backend.
    """

    def __init__(
        self,
        *,
        max_entries: int = 5000,
        default_ttl_seconds: float | None = 86_400.0,
    ) -> None:
        self._max_entries = max(1, max_entries)
        self._default_ttl = default_ttl_seconds
        # session_id -> (payload, deadline_monotonic or None if no ttl)
        self._data: dict[str, tuple[dict[str, JsonValue], float | None]] = {}

    def _evict_expired(self) -> None:
        now = time.monotonic()
        dead = [k for k, (_, d) in self._data.items() if d is not None and d <= now]
        for k in dead:
            self._data.pop(k, None)

    def _trim_size(self) -> None:
        while len(self._data) > self._max_entries:
            # Dict iteration order: pop oldest insertion (not LRU by last access).
            self._data.pop(next(iter(self._data)))

    def get(self, session_id: str) -> dict[str, JsonValue] | None:
        self._evict_expired()
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
        """Persist *data* for *session_id*; optional time-to-live in seconds.

        TTL semantics: ``ttl_seconds`` is ``None`` → use ``default_ttl_seconds`` (which may
        itself be ``None`` for no expiry). A **positive** value sets a monotonic deadline.
        ``ttl_seconds`` of ``0`` does **not** mean "expire immediately"; it is treated like
        "no TTL window" for this write (same as a negative value would be if passed, though
        callers should use ``None`` for no expiry).
        """
        self._evict_expired()
        ttl = self._default_ttl if ttl_seconds is None else ttl_seconds
        deadline: float | None = None
        if ttl is not None and ttl > 0:
            deadline = time.monotonic() + float(ttl)
        self._data[session_id] = (dict(data), deadline)
        self._trim_size()

    def delete(self, session_id: str) -> None:
        self._data.pop(session_id, None)


def new_session_id() -> str:
    """Return a new URL-safe opaque session identifier (≥128 bits)."""
    return secrets.token_urlsafe(32)


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _url_session_disabled() -> bool:
    if _truthy_env("FLUXLIT_DISABLE_URL_SESSION"):
        return True
    return _truthy_env("FLUXLIT_TESTS") and not _truthy_env("FLUXLIT_FORCE_URL_SESSION_IN_TESTS")


def _query_param_get(st: StreamlitSessionFacade, param: str) -> str | None:
    qp = st.query_params
    if qp is None or not hasattr(qp, "get"):
        return None
    raw = qp.get(param)
    if raw is None:
        return None
    if isinstance(raw, list):
        return str(raw[0]) if raw else None
    return str(raw)


def _query_param_set(st: StreamlitSessionFacade, param: str, value: str) -> bool:
    """Best-effort assign *param* on ``st.query_params`` (Streamlit 1.30+)."""
    qp = st.query_params
    if qp is None:
        return False
    try:
        if isinstance(qp, MutableMapping):
            cast(MutableMapping[str, str], qp)[param] = value
            return True
        setitem = getattr(qp, "__setitem__", None)
        if callable(setitem):
            setitem(param, value)
            return True
        return False
    except Exception:
        return False


def hydrate_url_session(
    st: StreamlitSessionFacade,
    store: SessionStore,
    *,
    param: str = "fluxlit_sid",
    merge: bool = True,
) -> str | None:
    """If ``st.query_params[param]`` is set, load the store payload into ``st.session_state``.

    - **merge** (default): ``session_state.setdefault(k, v)`` for each key in the blob
      so in-flight widget state wins over stale store keys on first paint.
    - If the param is missing, returns ``None`` and does nothing.
    - If the param is present but the store has no entry, returns the **session id**
      without mutating ``session_state`` (caller may seed with :meth:`SessionStore.set`).

    Returns the session id string when the query param is present, else ``None``.
    """
    if _url_session_disabled():
        return None
    sid = _query_param_get(st, param)
    if not sid:
        return None
    blob = store.get(sid)
    if blob is None:
        return sid
    ss = st.session_state
    if merge:
        for k, v in blob.items():
            ss.setdefault(k, v)
    else:
        for k, v in blob.items():
            ss[k] = v
    return sid


def ensure_url_session(
    st: StreamlitSessionFacade,
    store: SessionStore,
    *,
    param: str = "fluxlit_sid",
    initial: Mapping[str, JsonValue] | None = None,
    ttl_seconds: float | None = None,
) -> str:
    """Ensure ``st.query_params[param]`` exists; mint id, seed store, set query param.

    Returns the session id (existing or new). If the query param cannot be set
    (read-only ``query_params``), still returns a new id and persists *initial* so
    callers can surface a warning or use client-side navigation.
    """
    if _url_session_disabled():
        return _query_param_get(st, param) or ""
    existing = _query_param_get(st, param)
    if existing:
        if initial:
            cur = store.get(existing)
            merged: dict[str, JsonValue] = dict(cur or {})
            merged.update(initial)
            store.set(existing, merged, ttl_seconds=ttl_seconds)
        return existing
    sid = new_session_id()
    store.set(sid, dict(initial or {}), ttl_seconds=ttl_seconds)
    _query_param_set(st, param, sid)
    return sid


def persist_url_session(
    st: StreamlitSessionFacade,
    store: SessionStore,
    *,
    param: str = "fluxlit_sid",
    ttl_seconds: float | None = None,
) -> str | None:
    """Write current ``st.session_state`` (shallow dict copy) to the store for ``param`` id.

    Returns the session id if the param is present, else ``None``.

    Values are copied best-effort; remote stores should JSON-encode—non-JSON-safe
    values may need app-side filtering before :meth:`SessionStore.set`.
    """
    if _url_session_disabled():
        return None
    sid = _query_param_get(st, param)
    if not sid:
        return None
    ss = st.session_state
    snap: dict[str, JsonValue] = {}
    try:
        fs = getattr(ss, "filtered_state", None)
        if isinstance(fs, Mapping):
            src = dict(fs)
        else:
            src = {str(k): ss[k] for k in ss}
        for k, v in src.items():
            if str(k).startswith("__"):
                continue
            snap[str(k)] = cast(JsonValue, v)
    except Exception:
        return sid
    store.set(sid, snap, ttl_seconds=ttl_seconds)
    return sid
