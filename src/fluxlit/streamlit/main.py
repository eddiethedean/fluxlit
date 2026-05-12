"""Streamlit process entrypoint (run via ``streamlit run`` from :mod:`fluxlit.runtime`).

Environment variables (set by the parent process):

- ``FLUXLIT_APP`` — import path ``module:attr`` resolving to a :class:`~fluxlit.app.FluxLit`.
- ``FLUXLIT_API_PREFIX`` — API mount path (e.g. ``/api``).
- ``FLUXLIT_INTERNAL_API_BASE`` — base URL for :class:`~fluxlit.client.ApiClient`.

When multiple pages are registered, the entrypoint reads ``?page=`` (or the key used by
:func:`fluxlit.deep_links.match_nav_page`) before :func:`streamlit.navigation` so deep
links and :class:`streamlit.testing.v1.AppTest` can open a specific page by title, path,
or slug (see :mod:`fluxlit.testing` helpers).

Do not import this module in library code; it executes Streamlit UI on import.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any, cast

import streamlit as st

from fluxlit.deep_links import match_nav_page, query_params
from fluxlit.pages.records import PageRecord
from fluxlit.runtime import load_fluxlit
from fluxlit.streamlit.nav_order import navigation_sort_key
from fluxlit.streamlit.page_config import build_set_page_config_kwargs
from fluxlit.streamlit.page_runner import run_page_record


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
    nav_model = getattr(fluxlit_app, "_navigation_model", None)
    records = list(fluxlit_app.page_records)
    if nav_model is not None and nav_model.order:
        records = sorted(
            records,
            key=lambda r: navigation_sort_key(nav_model, r),
        )

    def _bind_page(
        rec: PageRecord,
        st_mod: Any,
        page_client: Any,
    ) -> Callable[[], None]:
        """Wrap a page record as a zero-arg callable for Streamlit."""

        def inner() -> None:
            run_page_record(rec, st_mod, page_client, fluxlit_app, None)

        return inner

    nav_pages = []
    for rec in records:
        slug = rec.path.strip("/") or "home"
        icon = rec.icon or (
            rec.page_meta.page_icon if rec.page_meta and rec.page_meta.page_icon else None
        )
        page_kw: dict[str, Any] = {
            "title": rec.title,
            "url_path": slug,
        }
        if icon:
            page_kw["icon"] = icon
        nav_pages.append(
            st.Page(
                _bind_page(rec, st, client),
                **page_kw,
            )
        )

    if not nav_pages:
        st.title(fluxlit_app.settings.title)
        st.info('Register UI with `@app.page("/")` on functions that accept `(st, client)`.')
    else:
        matched = match_nav_page(query_params(st), fluxlit_app.pages)
        if matched is not None:
            want_slug = matched[0].strip("/") or "home"
            for pg in nav_pages:
                if pg.url_path == want_slug:
                    st.switch_page(pg)
        st.navigation(nav_pages).run()


run_streamlit_entrypoint()
