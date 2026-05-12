"""FluxLit app demonstrating external URL session stores."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from examples.session_stores.sqlite_store import SQLiteSessionStore
from fluxlit import FluxLit
from fluxlit.client import ApiClient
from fluxlit.url_session import (
    ensure_url_session,
    hydrate_url_session_typed,
    persist_url_session,
)

app = FluxLit(title="FluxLit Session Store Demo")


class UrlSessionPayload(BaseModel):
    """Typed snapshot persisted in the URL-bound session store."""

    visits: int = Field(default=0, ge=0)


def _store() -> SQLiteSessionStore:
    path = Path(os.environ.get("FLUXLIT_SESSION_SQLITE_PATH", "fluxlit-sessions.sqlite3"))
    return SQLiteSessionStore(path)


@app.page("/", title="Session Store")
def home(st: Any, client: ApiClient) -> None:  # noqa: ARG001
    store = _store()
    sid = ensure_url_session(st, store, initial={"visits": 0})
    _, snap = hydrate_url_session_typed(st, store, UrlSessionPayload)
    visits = (snap.visits if snap is not None else 0) + 1
    st.session_state["visits"] = visits
    persist_url_session(st, store)

    st.title("FluxLit URL Session Store")
    st.write(f"Session id: `{sid}`")
    st.write(f"Visits persisted for this URL session: {visits}")
