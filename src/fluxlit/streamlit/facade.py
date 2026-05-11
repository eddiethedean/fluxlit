"""Minimal typing surface for Streamlit modules passed into helpers (query + session_state)."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any, Protocol, TypeAlias

# Streamlit ``session_state`` may hold widgets or arbitrary user objects.
SessionStateValue: TypeAlias = Any


class StreamlitSessionFacade(Protocol):
    """Narrow view of ``streamlit`` (or AppTest doubles) for :mod:`fluxlit.url_session`."""

    query_params: Mapping[str, str | list[str] | None] | MutableMapping[str, str]
    session_state: MutableMapping[str, SessionStateValue]


__all__ = ["SessionStateValue", "StreamlitSessionFacade"]
