"""Streamlit process entrypoint (run via ``streamlit run`` from :mod:`fluxlit.runtime`).

Environment variables (set by the parent process):

- ``FLUXLIT_APP`` — import path ``module:attr`` resolving to a :class:`~fluxlit.app.FluxLit`.
- ``FLUXLIT_API_PREFIX`` — API mount path (e.g. ``/api``).
- ``FLUXLIT_INTERNAL_API_BASE`` — base URL for :class:`~fluxlit.client.ApiClient`.

Do not import this module in library code; it executes Streamlit UI on import.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any, cast

import streamlit as st

from fluxlit.runtime import load_fluxlit
from fluxlit.streamlit.page_config import build_set_page_config_kwargs


def run_streamlit_entrypoint() -> None:
    spec = os.environ.get("FLUXLIT_APP")
    if not spec:
        st.error("FLUXLIT_APP is not set.")
        st.stop()

    fluxlit_app = load_fluxlit(spec)
    st.set_page_config(
        **cast(
            dict[str, Any],
            build_set_page_config_kwargs(
                settings_title=fluxlit_app.settings.title,
                streamlit_page_config=fluxlit_app.settings.streamlit_page_config,
            ),
        )
    )
    client = fluxlit_app.get_client()

    def _bind_page(
        fn: Callable[[Any, Any], None],
        st_mod: Any,
        page_client: Any,
    ) -> Callable[[], None]:
        """Wrap a ``(st, client)`` page function as a zero-arg callable for Streamlit."""

        def inner() -> None:
            fn(st_mod, page_client)

        return inner

    nav_pages = []
    for path, title, fn in fluxlit_app.pages:
        nav_pages.append(
            st.Page(
                _bind_page(fn, st, client),
                title=title,
                url_path=path.strip("/") or "home",
            )
        )

    if not nav_pages:
        st.title(fluxlit_app.settings.title)
        st.info('Register UI with `@app.page("/")` on functions that accept `(st, client)`.')
    else:
        st.navigation(nav_pages).run()


run_streamlit_entrypoint()
