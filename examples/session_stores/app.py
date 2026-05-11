"""FluxLit app demonstrating external URL session stores."""

from __future__ import annotations

import os
from pathlib import Path

from examples.session_stores.sqlite_store import SQLiteSessionStore
from fluxlit import FluxLit
from fluxlit.url_session import (
    ensure_url_session,
    hydrate_url_session,
    persist_url_session,
)

app = FluxLit(title="FluxLit Session Store Demo")


def _store() -> SQLiteSessionStore:
    path = Path(os.environ.get("FLUXLIT_SESSION_SQLITE_PATH", "fluxlit-sessions.sqlite3"))
    return SQLiteSessionStore(path)


@app.page("/", title="Session Store")
def home(st, client) -> None:  # noqa: ARG001
    store = _store()
    sid = ensure_url_session(st, store, initial={"visits": 0})
    hydrate_url_session(st, store)

    visits = int(st.session_state.get("visits", 0)) + 1
    st.session_state["visits"] = visits
    persist_url_session(st, store)

    st.title("FluxLit URL Session Store")
    st.write(f"Session id: `{sid}`")
    st.write(f"Visits persisted for this URL session: {visits}")
