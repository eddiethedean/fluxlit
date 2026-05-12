"""Apply :class:`~fluxlit.pages.meta.PageMeta` to Streamlit (best-effort)."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from fluxlit.config import JsonValue
from fluxlit.pages.meta import PageMeta


def page_meta_to_set_page_config_kwargs(meta: PageMeta) -> dict[str, JsonValue]:
    """Build ``set_page_config`` kwargs from *meta* (non-``None`` fields only)."""
    raw: dict[str, JsonValue] = {}
    if meta.page_title is not None:
        raw["page_title"] = meta.page_title
    if meta.page_icon is not None:
        raw["page_icon"] = meta.page_icon
    if meta.layout is not None:
        raw["layout"] = meta.layout
    if meta.initial_sidebar_state is not None:
        raw["initial_sidebar_state"] = meta.initial_sidebar_state
    return raw


def try_set_page_config_first(st: Any, meta: PageMeta) -> None:
    """Call ``set_page_config`` when *meta* has keys; must be the first Streamlit command."""
    kw = page_meta_to_set_page_config_kwargs(meta)
    if not kw:
        return
    try:
        st.set_page_config(**kw)
    except Exception:
        return


def apply_returned_page_meta(st: Any, meta: PageMeta | None) -> None:
    """Post-run effects for returned metadata (sidebar breadcrumb, etc.)."""
    if meta is None:
        return
    if meta.breadcrumb:
        sb = getattr(st, "sidebar", None)
        cap = getattr(sb, "caption", None) if sb is not None else None
        if callable(cap):
            cap(meta.breadcrumb)


def coerce_page_return(st: Any, value: Any) -> PageMeta | None:
    """If *value* is a :class:`PageMeta` or dict, validate to ``PageMeta``; else ``None``."""
    if value is None:
        return None
    if isinstance(value, PageMeta):
        return value
    if isinstance(value, dict):
        try:
            return PageMeta.model_validate(value)
        except ValidationError as e:
            err = getattr(st, "error", None)
            if callable(err):
                err(f"Invalid page metadata: {e}")
            return None
    return None
