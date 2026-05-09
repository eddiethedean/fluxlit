"""Streamlit entrypoint driven by `FLUXLIT_APP=module:attr` (a `FluxLit` instance)."""

from __future__ import annotations

import importlib
import os
from collections.abc import Callable
from typing import Any

import streamlit as st

from fluxlit.app import FluxLit


def _load_fluxlit(spec: str) -> FluxLit:
    mod_name, sep, attr = spec.partition(":")
    if not sep or not attr:
        msg = "FLUXLIT_APP must look like 'my_module:app'"
        raise ValueError(msg)
    module = importlib.import_module(mod_name)
    obj = getattr(module, attr)
    if not isinstance(obj, FluxLit):
        msg = f"{spec} must resolve to a FluxLit instance"
        raise TypeError(msg)
    return obj


spec = os.environ.get("FLUXLIT_APP")
if not spec:
    st.error("FLUXLIT_APP is not set.")
    st.stop()

_fluxlit = _load_fluxlit(spec)
st.set_page_config(page_title=_fluxlit.settings.title)
_client = _fluxlit.get_client()
def _bind_page(
    fn: Callable[[Any, Any], None],
    st_mod: Any,
    client: Any,
) -> Callable[[], None]:
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
