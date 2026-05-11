"""Streamlit process entrypoint (run via ``streamlit run`` from :mod:`fluxlit.runtime`).

Environment variables (set by the parent process):

- ``FLUXLIT_APP`` — import path ``module:attr`` resolving to a :class:`~fluxlit.app.FluxLit`.
- ``FLUXLIT_API_PREFIX`` — API mount path (e.g. ``/api``).
- ``FLUXLIT_INTERNAL_API_BASE`` — base URL for :class:`~fluxlit.client.ApiClient`.

At import time this module loads the app, configures Streamlit pages from ``.pages``,
and runs :func:`streamlit.navigation` (or shows a hint if no pages are registered).

Do not import this module in library code; it executes Streamlit UI on import.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

import streamlit as st

from fluxlit.runtime import load_fluxlit
from fluxlit.streamlit_page_config import build_set_page_config_kwargs

spec = os.environ.get("FLUXLIT_APP")
if not spec:
    st.error("FLUXLIT_APP is not set.")
    st.stop()

_fluxlit = load_fluxlit(spec)
st.set_page_config(
    **build_set_page_config_kwargs(
        settings_title=_fluxlit.settings.title,
        streamlit_page_config=_fluxlit.settings.streamlit_page_config,
    )
)
_client = _fluxlit.get_client()


def _bind_page(
    fn: Callable[[Any, Any], None],
    st_mod: Any,
    client: Any,
) -> Callable[[], None]:
    """Wrap a ``(st, client)`` page function as a zero-arg callable for :class:`streamlit.Page`."""

    def inner() -> None:
        fn(st_mod, client)

    return inner


_nav_pages = []
for _path, _title, _fn in _fluxlit.pages:
    _nav_pages.append(
        st.Page(
            _bind_page(_fn, st, _client),
            title=_title,
            url_path=_path.strip("/") or "home",
        )
    )

if not _nav_pages:
    st.title(_fluxlit.settings.title)
    st.info('Register UI with `@app.page("/")` on functions that accept `(st, client)`.')
else:
    st.navigation(_nav_pages).run()
