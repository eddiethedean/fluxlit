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

import secrets
import time
from collections.abc import Mapping, MutableMapping
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class SessionStore(Protocol):
    """Server-side persistence for URL-bound session blobs (serializable dicts)."""

    def get(self, session_id: str) -> dict[str, Any] | None:
        """Return the stored dict or ``None`` if missing/expired."""

    def set(
        self,
        session_id: str,
        data: dict[str, Any],
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
        self._data: dict[str, tuple[dict[str, Any], float | None]] = {}

    def _evict_expired(self) -> None:
        now = time.monotonic()
        dead = [k for k, (_, d) in self._data.items() if d is not None and d <= now]
        for k in dead:
            self._data.pop(k, None)

    def _trim_size(self) -> None:
        while len(self._data) > self._max_entries:
            # Drop arbitrary oldest bucket: simple pop of first key
            self._data.pop(next(iter(self._data)))

    def get(self, session_id: str) -> dict[str, Any] | None:
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
        data: dict[str, Any],
        *,
        ttl_seconds: float | None = None,
    ) -> None:
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


def _query_param_get(st: Any, param: str) -> str | None:
    qp = getattr(st, "query_params", None)
    if qp is None or not hasattr(qp, "get"):
        return None
    raw = qp.get(param)
    if raw is None:
        return None
    if isinstance(raw, list):
        return str(raw[0]) if raw else None
    return str(raw)


def _query_param_set(st: Any, param: str, value: str) -> bool:
    """Best-effort assign *param* on ``st.query_params`` (Streamlit 1.30+)."""
    qp = getattr(st, "query_params", None)
    if qp is None:
        return False
    try:
        if isinstance(qp, MutableMapping):
            qp[param] = value
            return True
        qp.__setitem__(param, value)  # type: ignore[attr-defined]
        return True
    except Exception:
        return False


def hydrate_url_session(
    st: Any,
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
    sid = _query_param_get(st, param)
    if not sid:
        return None
    blob = store.get(sid)
    if blob is None:
        return sid
    ss = getattr(st, "session_state", None)
    if ss is None:
        return sid
    if merge:
        for k, v in blob.items():
            ss.setdefault(k, v)
    else:
        for k, v in blob.items():
            ss[k] = v
    return sid


def ensure_url_session(
    st: Any,
    store: SessionStore,
    *,
    param: str = "fluxlit_sid",
    initial: dict[str, Any] | None = None,
    ttl_seconds: float | None = None,
) -> str:
    """Ensure ``st.query_params[param]`` exists; mint id, seed store, set query param.

    Returns the session id (existing or new). If the query param cannot be set
    (read-only ``query_params``), still returns a new id and persists *initial* so
    callers can surface a warning or use client-side navigation.
    """
    existing = _query_param_get(st, param)
    if existing:
        if initial:
            cur = store.get(existing)
            merged = dict(cur or {})
            merged.update(initial)
            store.set(existing, merged, ttl_seconds=ttl_seconds)
        return existing
    sid = new_session_id()
    store.set(sid, dict(initial or {}), ttl_seconds=ttl_seconds)
    _query_param_set(st, param, sid)
    return sid


def persist_url_session(
    st: Any,
    store: SessionStore,
    *,
    param: str = "fluxlit_sid",
    ttl_seconds: float | None = None,
) -> str | None:
    """Write current ``st.session_state`` (shallow dict copy) to the store for ``param`` id.

    Returns the session id if the param is present, else ``None``.
    """
    sid = _query_param_get(st, param)
    if not sid:
        return None
    ss = getattr(st, "session_state", None)
    if ss is None:
        store.set(sid, {}, ttl_seconds=ttl_seconds)
        return sid
    # Shallow copy; values should be JSON-serializable if you plan remote stores.
    snap: dict[str, Any] = {}
    try:
        fs = getattr(ss, "filtered_state", None)
        if isinstance(fs, Mapping):
            src = dict(fs)
        else:
            src = {str(k): ss[k] for k in ss}  # type: ignore[arg-type]
        for k, v in src.items():
            if str(k).startswith("__"):
                continue
            snap[str(k)] = v
    except Exception:
        snap = {}
    store.set(sid, snap, ttl_seconds=ttl_seconds)
    return sid
